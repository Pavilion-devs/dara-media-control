from __future__ import annotations

import asyncio
import unittest
from decimal import Decimal

from fastapi.testclient import TestClient

from dara.main import app
from dara.policy import (
    B2JobStore,
    MemoryJobStore,
    PlannedStep,
    Policy,
    PolicyEngine,
    Price,
    ReservationBook,
    RunPlan,
    Severity,
    estimate_run_cost,
)
from dara.storage import DaraStorage


class DictBackend:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        del content_type, metadata
        self.objects[key] = bytes(data)
        return f"memory://{key}"

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def exists(self, key: str) -> bool:
        return key in self.objects

    def list(
        self,
        prefix: str = "",
        *,
        max_keys: int = 1000,
        continuation_token: str | None = None,
    ) -> object:
        raise NotImplementedError

    def get_url(self, key: str, *, expires_in: int = 3600) -> str:
        return f"memory://{key}?expires={expires_in}"


def standard_policy(**overrides: object) -> Policy:
    values: dict[str, object] = {
        "policy_id": "pol_standard",
        "allowed_providers": frozenset({"nvidia", "google", "replicate"}),
        "denied_models": frozenset({"veo-3"}),
        "allowed_modalities": frozenset({"image", "video", "audio"}),
        "allowed_aspect_ratios": frozenset({"1:1", "16:9", "9:16"}),
        "max_steps": 6,
        "max_variants": 4,
        "max_attempts": 3,
        "max_cost_usd_per_step": Decimal("0.500000"),
        "max_cost_usd_per_run": Decimal("2.000000"),
        "max_cost_usd_per_day": Decimal("10.000000"),
    }
    values.update(overrides)
    return Policy(**values)  # type: ignore[arg-type]


def image_plan(job_id: str = "job_01", variants: int = 3) -> RunPlan:
    return RunPlan(
        tenant_id="demo",
        job_id=job_id,
        modality="image",
        aspect_ratio="16:9",
        variants=variants,
        max_attempts=3,
        steps=(PlannedStep("replicate", "flux-1.1-pro", "image"),),
    )


PRICES = {
    "flux-1.1-pro": Price("flux-1.1-pro", Decimal("0.060000")),
}


class EstimateTests(unittest.TestCase):
    def test_worst_case_includes_variants_and_attempts(self) -> None:
        estimate = estimate_run_cost(image_plan(variants=3), PRICES)
        self.assertEqual(estimate.expected_usd, Decimal("0.180000"))
        self.assertEqual(estimate.worst_case_usd, Decimal("0.540000"))


class PolicyExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_b2_job_record_survives_store_reconstruction(self) -> None:
        backend = DictBackend()
        first_store = B2JobStore(DaraStorage(backend))
        engine = PolicyEngine(first_store)
        calls = 0

        async def provider(_: RunPlan) -> Decimal:
            nonlocal calls
            calls += 1
            return Decimal("0.180000")

        locked = standard_policy(max_cost_usd_per_run=Decimal("0.100000"))
        original = await engine.execute(locked, image_plan("job_durable"), PRICES, provider)
        reconstructed_store = B2JobStore(DaraStorage(backend))
        restored = await reconstructed_store.get_job("demo", "job_durable")

        self.assertEqual(calls, 0)
        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.status, "blocked")
        self.assertEqual(restored.actual_cost_usd, Decimal("0.000000"))
        self.assertEqual(
            restored.policy_decisions[0].violations[0].code,
            original.policy_decisions[0].violations[0].code,
        )

    async def test_blocked_job_is_persisted_and_makes_zero_provider_calls(self) -> None:
        store = MemoryJobStore()
        engine = PolicyEngine(store)
        calls = 0

        async def provider(_: RunPlan) -> Decimal:
            nonlocal calls
            calls += 1
            return Decimal("0.180000")

        locked = standard_policy(max_cost_usd_per_run=Decimal("0.100000"))
        job = await engine.execute(locked, image_plan(), PRICES, provider)

        self.assertEqual(job.status, "blocked")
        self.assertEqual(calls, 0)
        self.assertEqual(store.jobs[job.job_id].status, "blocked")
        self.assertEqual(
            job.policy_decisions[0].violations[0].code, "RUN_BUDGET_EXCEEDED"
        )
        self.assertEqual(job.actual_cost_usd, Decimal("0.000000"))

    async def test_valid_job_calls_provider_and_settles_exact_cost(self) -> None:
        store = MemoryJobStore()
        engine = PolicyEngine(store)
        calls = 0

        async def provider(_: RunPlan) -> Decimal:
            nonlocal calls
            calls += 1
            return Decimal("0.210000")

        job = await engine.execute(
            standard_policy(), image_plan(), PRICES, provider
        )
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(calls, 1)
        self.assertEqual(job.actual_cost_usd, Decimal("0.210000"))
        self.assertEqual(job.reserved_cost_usd, Decimal("0.000000"))

    async def test_unpriced_model_warns_but_does_not_block(self) -> None:
        store = MemoryJobStore()
        engine = PolicyEngine(store)
        plan = RunPlan(
            tenant_id="demo",
            job_id="job_unpriced",
            modality="image",
            aspect_ratio="1:1",
            variants=1,
            max_attempts=1,
            steps=(PlannedStep("replicate", "new-model", "image"),),
        )
        _, decision = await engine.admit(standard_policy(), plan, {})
        self.assertEqual(decision.outcome, Severity.WARN)
        self.assertEqual(decision.violations[0].code, "UNPRICED_MODEL")

    async def test_concurrent_admission_cannot_double_spend_daily_budget(self) -> None:
        engine = PolicyEngine(MemoryJobStore(), ReservationBook())
        policy = standard_policy(
            max_cost_usd_per_run=Decimal("1.000000"),
            max_cost_usd_per_day=Decimal("0.800000"),
        )
        prices = {
            "flux-1.1-pro": Price("flux-1.1-pro", Decimal("0.250000")),
        }
        decisions = await asyncio.gather(
            engine.admit(policy, image_plan("job_a", variants=1), prices),
            engine.admit(policy, image_plan("job_b", variants=1), prices),
        )
        outcomes = sorted(decision.outcome for _, decision in decisions)
        self.assertEqual(outcomes, [Severity.ALLOW, Severity.BLOCK])


class PolicyEndpointTests(unittest.TestCase):
    def test_blocked_job_returns_structured_409_and_zero_spend(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/v1/jobs?policy_id=pol_locked",
                json={
                    "tenant_id": "demo",
                    "job_id": "job_http_block",
                    "provider": "replicate",
                    "model": "flux-1.1-pro",
                    "modality": "image",
                    "aspect_ratio": "16:9",
                    "variants": 3,
                    "max_attempts": 3,
                    "step_count": 1,
                },
            )
        payload = response.json()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(payload["error"]["code"], "POLICY_BLOCKED")
        self.assertEqual(payload["error"]["details"]["spent_usd"], "0.000000")
        self.assertEqual(
            payload["error"]["details"]["job_id"],
            "job_http_block",
        )


if __name__ == "__main__":
    unittest.main()
