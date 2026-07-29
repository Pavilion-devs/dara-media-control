from __future__ import annotations

import asyncio
import os
import secrets
import tempfile
import time
from collections import defaultdict, deque
from dataclasses import asdict
from decimal import Decimal
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from threading import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .policy import (
    B2JobStore,
    JobStore,
    MemoryJobStore,
    PlannedStep,
    Policy,
    PolicyEngine,
    Price,
    RunPlan,
    job_to_json,
    money,
)
from .storage import DaraStorage, StorageUnavailableError
from .verify import (
    InvalidHashError,
    UnsupportedMediaError,
    VerificationResponse,
    Verifier,
)

app = FastAPI(
    title="Dara API",
    version="0.1.0",
    description="Governance, provenance, and spend control for generated media.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "DARA_ALLOWED_ORIGINS",
        "https://dara-media-control.asaborodaniel.chatgpt.site",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

def build_job_store() -> JobStore:
    required = ("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_REGION")
    if all(os.getenv(name) for name in required):
        return B2JobStore(DaraStorage.from_env())
    return MemoryJobStore()


store = build_job_store()
engine = PolicyEngine(store)


class DaraApiError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class VerifyRateLimiter:
    def __init__(self) -> None:
        self._attempts: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, client_id: str, *, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[client_id]
            while attempts and attempts[0] <= now - window_seconds:
                attempts.popleft()
            if len(attempts) >= limit:
                retry_after = max(1, int(window_seconds - (now - attempts[0])))
                raise DaraApiError(
                    429,
                    "RATE_LIMITED",
                    "Verification is temporarily rate-limited. Try again shortly.",
                    {"retry_after_s": retry_after},
                )
            attempts.append(now)


verify_rate_limiter = VerifyRateLimiter()


@lru_cache(maxsize=1)
def _default_verifier() -> Verifier:
    return Verifier(DaraStorage.from_env())


def get_verifier() -> Verifier:
    try:
        return _default_verifier()
    except StorageUnavailableError as exc:
        raise DaraApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "Dara's trusted storage is unavailable. Retry verification shortly.",
        ) from exc


def require_workspace_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = os.getenv("DARA_API_TOKEN")
    if not expected:
        raise DaraApiError(
            503,
            "WORKSPACE_AUTH_UNAVAILABLE",
            "Dara's private workspace API is not configured.",
        )
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, expected):
        raise DaraApiError(
            401,
            "UNAUTHORIZED",
            "A valid Dara workspace token is required.",
        )


def policy(
    policy_id: str,
    *,
    run_limit: str,
    daily_limit: str,
    allowed_modalities: frozenset[str] = frozenset({"image"}),
    allowed_ratios: frozenset[str] = frozenset({"1:1", "3:2", "2:3"}),
) -> Policy:
    return Policy(
        policy_id=policy_id,
        allowed_providers=frozenset({"openai"}),
        denied_models=frozenset(),
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
        run_limit="0.020000",
        daily_limit="1.000000",
        allowed_modalities=frozenset({"image"}),
        allowed_ratios=frozenset({"1:1"}),
    ),
}

MODEL_PRICES = {
    # Conservative policy reservation for one low-quality image. OpenAI bills
    # GPT Image 2 by image tokens, so the settled ledger will use actual usage.
    "gpt-image-2": Price("gpt-image-2", money("0.010000")),
}


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: object) -> object:
    request_id = request.headers.get("X-Request-Id") or f"req_{secrets.token_hex(8)}"
    request.state.request_id = request_id
    response = await call_next(request)  # type: ignore[operator]
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(DaraApiError)
async def dara_api_error_handler(
    request: Request,
    exc: DaraApiError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


class SimulateRequest(BaseModel):
    tenant_id: str = "demo"
    job_id: str = "job_simulation"
    provider: str = "openai"
    model: str = "gpt-image-2"
    modality: str = "image"
    aspect_ratio: str = "1:1"
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


def policy_payload(value: Policy) -> dict[str, object]:
    payload = asdict(value)
    for key in (
        "allowed_providers",
        "denied_models",
        "allowed_modalities",
        "allowed_aspect_ratios",
    ):
        payload[key] = sorted(payload[key])
    for key in (
        "max_cost_usd_per_step",
        "max_cost_usd_per_run",
        "max_cost_usd_per_day",
    ):
        payload[key] = str(payload[key])
    return payload


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


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    return {
        "ok": True,
        "b2": "configured" if os.getenv("B2_BUCKET") else "unconfigured",
        "genblaze_core": version("genblaze-core"),
        "providers": {
            "openai": "configured" if os.getenv("OPENAI_API_KEY") else "unconfigured"
        },
        "demo_mode_available": True,
    }


@app.get("/v1/models")
async def list_models() -> dict[str, object]:
    return {
        "items": [
            {
                "provider": "openai",
                "model": "gpt-image-2",
                "modality": "image",
                "availability": (
                    "configured"
                    if os.getenv("OPENAI_API_KEY")
                    else "unconfigured"
                ),
                "reservation_per_image_usd": str(
                    MODEL_PRICES["gpt-image-2"].per_unit_usd
                ),
                "pricing_basis": "conservative low-quality policy reservation",
            }
        ]
    }


@app.get("/v1/policies")
async def list_policies() -> dict[str, object]:
    return {"items": [policy_payload(value) for value in POLICIES.values()]}


@app.get("/v1/policies/{policy_id}")
async def read_policy(policy_id: str) -> dict[str, object]:
    return policy_payload(get_policy(policy_id))


@app.post("/v1/verify", response_model=VerificationResponse)
async def verify_upload(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    verifier: Annotated[Verifier, Depends(get_verifier)],
) -> VerificationResponse:
    client_id = request.client.host if request.client else "unknown"
    limit = int(os.getenv("KILN_VERIFY_RATE_LIMIT_PER_MIN", "10"))
    verify_rate_limiter.check(client_id, limit=limit)
    max_bytes = int(os.getenv("KILN_MAX_UPLOAD_MB", "100")) * 1024 * 1024
    suffix = Path(file.filename or "upload").suffix
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="dara-verify-",
            suffix=suffix,
            delete=False,
        ) as destination:
            temporary_path = Path(destination.name)
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise DaraApiError(
                        413,
                        "FILE_TOO_LARGE",
                        f"This file exceeds Dara's {max_bytes // (1024 * 1024)} MB verification limit.",
                    )
                destination.write(chunk)
        return await asyncio.to_thread(verifier.verify_path, temporary_path)
    except UnsupportedMediaError as exc:
        raise DaraApiError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            str(exc),
        ) from exc
    except StorageUnavailableError as exc:
        raise DaraApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "Dara's trusted storage is unavailable. Retry verification shortly.",
        ) from exc
    finally:
        await file.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@app.get("/v1/verify/{sha256}", response_model=VerificationResponse)
async def verify_hash(
    sha256: str,
    verifier: Annotated[Verifier, Depends(get_verifier)],
) -> VerificationResponse:
    try:
        return await asyncio.to_thread(verifier.lookup_hash, sha256)
    except InvalidHashError as exc:
        raise DaraApiError(400, "INVALID_REQUEST", str(exc)) from exc
    except StorageUnavailableError as exc:
        raise DaraApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "Dara's trusted storage is unavailable. Retry verification shortly.",
        ) from exc


@app.post("/v1/policies/{policy_id}/simulate")
async def simulate(policy_id: str, request: SimulateRequest) -> dict[str, object]:
    estimate, decision = await engine.simulate(
        get_policy(policy_id), request.to_plan(), MODEL_PRICES
    )
    return decision_payload(estimate, decision)


@app.post("/v1/jobs")
async def create_demo_job(
    request: SimulateRequest,
    _: Annotated[None, Depends(require_workspace_token)],
    policy_id: str = "pol_standard",
) -> dict[str, object]:
    plan = request.to_plan()
    estimate, _ = await engine.simulate(get_policy(policy_id), plan, MODEL_PRICES)

    async def demo_provider(_: RunPlan) -> Decimal:
        return estimate.expected_usd

    job = await engine.execute(
        get_policy(policy_id), plan, MODEL_PRICES, demo_provider
    )
    if job.status == "blocked":
        raise DaraApiError(
            409,
            "POLICY_BLOCKED",
            (
                job.error
                or "This run was blocked before any provider call. Nothing was spent."
            ),
            {
                "job_id": job.job_id,
                "estimate": {
                    "expected_usd": str(estimate.expected_usd),
                    "worst_case_usd": str(estimate.worst_case_usd),
                },
                "violations": [
                    asdict(violation)
                    for decision in job.policy_decisions
                    for violation in decision.violations
                ],
                "spent_usd": "0.000000",
            },
        )
    return job_to_json(job)


@app.get("/v1/jobs/{job_id}")
async def get_job(
    job_id: str,
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    tenant_id = os.getenv("KILN_TENANT_ID", "demo")
    job = await store.get_job(tenant_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job_to_json(job)
