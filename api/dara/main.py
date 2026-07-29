from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from importlib.metadata import version

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .policy import (
    MemoryJobStore,
    PlannedStep,
    Policy,
    PolicyEngine,
    Price,
    RunPlan,
    job_to_json,
    money,
)

app = FastAPI(
    title="Dara API",
    version="0.1.0",
    description="Governance, provenance, and spend control for generated media.",
)

store = MemoryJobStore()
engine = PolicyEngine(store)


def policy(
    policy_id: str,
    *,
    run_limit: str,
    daily_limit: str,
    allowed_modalities: frozenset[str] = frozenset({"image", "video", "audio"}),
    allowed_ratios: frozenset[str] = frozenset({"1:1", "16:9", "9:16"}),
) -> Policy:
    return Policy(
        policy_id=policy_id,
        allowed_providers=frozenset({"nvidia", "google", "replicate", "elevenlabs"}),
        denied_models=frozenset({"sora-2", "veo-3"}),
        allowed_modalities=allowed_modalities,
        allowed_aspect_ratios=allowed_ratios,
        max_steps=6,
        max_variants=4,
        max_attempts=3,
        max_cost_usd_per_step=money("0.500000"),
        max_cost_usd_per_run=money(run_limit),
        max_cost_usd_per_day=money(daily_limit),
    )


POLICIES = {
    "pol_permissive": policy(
        "pol_permissive", run_limit="20.000000", daily_limit="100.000000"
    ),
    "pol_standard": policy(
        "pol_standard", run_limit="2.000000", daily_limit="10.000000"
    ),
    "pol_locked": policy(
        "pol_locked",
        run_limit="0.100000",
        daily_limit="1.000000",
        allowed_modalities=frozenset({"image"}),
        allowed_ratios=frozenset({"1:1"}),
    ),
}

MODEL_PRICES = {
    "flux-1.1-pro": Price("flux-1.1-pro", money("0.060000")),
    "sd3.5-large": Price("sd3.5-large", money("0.040000")),
    "gemini-2.5-flash": Price("gemini-2.5-flash", money("0.002000")),
}


class SimulateRequest(BaseModel):
    tenant_id: str = "demo"
    job_id: str = "job_simulation"
    provider: str = "replicate"
    model: str = "flux-1.1-pro"
    modality: str = "image"
    aspect_ratio: str = "16:9"
    variants: int = Field(default=3, ge=1, le=20)
    max_attempts: int = Field(default=3, ge=1, le=10)
    step_count: int = Field(default=1, ge=1, le=20)

    def to_plan(self) -> RunPlan:
        return RunPlan(
            tenant_id=self.tenant_id,
            job_id=self.job_id,
            modality=self.modality,
            aspect_ratio=self.aspect_ratio,
            variants=self.variants,
            max_attempts=self.max_attempts,
            steps=tuple(
                PlannedStep(self.provider, self.model, self.modality)
                for _ in range(self.step_count)
            ),
        )


def get_policy(policy_id: str) -> Policy:
    resolved = POLICIES.get(policy_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Policy not found.")
    return resolved


def decision_payload(estimate: object, decision: object) -> dict[str, object]:
    estimate_data = asdict(estimate)  # type: ignore[arg-type]
    decision_data = asdict(decision)  # type: ignore[arg-type]
    for key in ("expected_usd", "worst_case_usd"):
        estimate_data[key] = str(estimate_data[key])
    estimate_data["per_step_usd"] = [
        str(value) if value is not None else None
        for value in estimate_data["per_step_usd"]
    ]
    decision_data["estimated_cost_usd"] = str(decision_data["estimated_cost_usd"])
    if decision_data["saved_cost_usd"] is not None:
        decision_data["saved_cost_usd"] = str(decision_data["saved_cost_usd"])
    decision_data["evaluated_at"] = decision_data["evaluated_at"].isoformat()
    return {"estimate": estimate_data, "decision": decision_data}


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "dara-api",
        "versions": {
            "genblaze": version("genblaze"),
            "genblaze-core": version("genblaze-core"),
            "genblaze-s3": version("genblaze-s3"),
        },
    }


@app.post("/v1/policies/{policy_id}/simulate")
async def simulate(policy_id: str, request: SimulateRequest) -> dict[str, object]:
    estimate, decision = await engine.simulate(
        get_policy(policy_id), request.to_plan(), MODEL_PRICES
    )
    return decision_payload(estimate, decision)


@app.post("/v1/jobs")
async def create_demo_job(
    request: SimulateRequest, policy_id: str = "pol_standard"
) -> dict[str, object]:
    plan = request.to_plan()
    estimate, _ = await engine.simulate(get_policy(policy_id), plan, MODEL_PRICES)

    async def demo_provider(_: RunPlan) -> Decimal:
        return estimate.expected_usd

    job = await engine.execute(
        get_policy(policy_id), plan, MODEL_PRICES, demo_provider
    )
    return job_to_json(job)


@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    job = store.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job_to_json(job)
