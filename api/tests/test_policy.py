from __future__ import annotations

import asyncio
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from genblaze_core import ModelRegistry
from genblaze_core.providers.pricing import per_unit
from pydantic import ValidationError

import dara.main as main_module
from dara.main import app
from dara.policy import (
    B2JobStore,
    B2PolicyStore,
    EnforcementPoint,
    MemoryJobStore,
    MemoryPolicyStore,
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
        del max_keys, continuation_token
        return SimpleNamespace(
            entries=[
                SimpleNamespace(key=key)
                for key in sorted(self.objects)
                if key.startswith(prefix)
            ]
        )

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
        steps=(
            PlannedStep(
                provider="replicate",
                model="flux-1.1-pro",
                modality="image",
            ),
        ),
    )


PRICES = {
    "flux-1.1-pro": Price(
        model="flux-1.1-pro",
        per_unit_usd=Decimal("0.060000"),
    ),
}


class EstimateTests(unittest.TestCase):
    def test_worst_case_includes_variants_and_attempts(self) -> None:
        estimate = estimate_run_cost(image_plan(variants=3), PRICES)
        self.assertEqual(estimate.expected_usd, Decimal("0.180000"))
        self.assertEqual(estimate.worst_case_usd, Decimal("0.540000"))

    def test_model_registry_pricing_is_used_without_provider_calls(self) -> None:
        registry = ModelRegistry()
        registry.register_pricing("flux-1.1-pro", per_unit(0.06))

        estimate = estimate_run_cost(image_plan(variants=3), registry)

        self.assertEqual(estimate.expected_usd, Decimal("0.180000"))
        self.assertEqual(estimate.worst_case_usd, Decimal("0.540000"))
        self.assertEqual(estimate.unpriced_models, ())


class PolicyModelTests(unittest.TestCase):
    def test_policy_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            standard_policy(unguarded_extension=True)

    def test_policy_money_is_normalized_to_six_places(self) -> None:
        resolved = standard_policy(max_cost_usd_per_run=Decimal("2"))
        self.assertEqual(resolved.max_cost_usd_per_run, Decimal("2.000000"))


class EnforcementPointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine(MemoryJobStore())

    def test_pre_flight_reports_all_shape_and_allowlist_codes(self) -> None:
        plan = RunPlan(
            tenant_id="demo",
            job_id="job_invalid",
            modality="video",
            aspect_ratio="4:3",
            variants=5,
            max_attempts=4,
            duration_s=Decimal("12"),
            steps=(
                PlannedStep(
                    provider="unknown",
                    model="veo-3",
                    modality="video",
                ),
            )
            * 7,
        )
        estimate = estimate_run_cost(plan, {})
        result = self.engine.evaluate(
            EnforcementPoint.PRE_FLIGHT,
            standard_policy(
                allowed_modalities=frozenset({"image"}),
                allowed_aspect_ratios=frozenset({"1:1"}),
                max_duration_s=Decimal("10"),
            ),
            plan=plan,
            estimate=estimate,
        )
        codes = {violation.code for violation in result.violations}
        self.assertTrue(
            {
                "PROVIDER_NOT_ALLOWED",
                "MODEL_DENIED",
                "TOO_MANY_STEPS",
                "MODALITY_NOT_ALLOWED",
                "ASPECT_RATIO_NOT_ALLOWED",
                "DURATION_EXCEEDED",
                "TOO_MANY_VARIANTS",
                "MAX_ATTEMPTS_REACHED",
                "UNPRICED_MODEL",
            }.issubset(codes)
        )

    def test_pre_step_blocks_budget_and_warns_on_estimate_drift(self) -> None:
        estimate = estimate_run_cost(image_plan(variants=1), PRICES)
        result = self.engine.evaluate(
            EnforcementPoint.PRE_STEP,
            standard_policy(max_cost_usd_per_run=Decimal("0.100000")),
            estimate=estimate,
            actual_cost=Decimal("0.090000"),
            step_cost=Decimal("0.060000"),
        )
        self.assertEqual(result.outcome, Severity.BLOCK)
        self.assertEqual(
            {violation.code for violation in result.violations},
            {"RUN_BUDGET_EXCEEDED", "ESTIMATE_DRIFT"},
        )

    def test_post_step_applies_qa_and_attempt_limits(self) -> None:
        result = self.engine.evaluate(
            EnforcementPoint.POST_STEP,
            standard_policy(
                block_on_qa_failure=False,
                min_qa_score=0.8,
                max_attempts=2,
            ),
            qa_score=0.4,
            attempts=2,
        )
        self.assertEqual(result.outcome, Severity.BLOCK)
        self.assertEqual(
            [violation.code for violation in result.violations],
            ["QA_BELOW_THRESHOLD", "MAX_ATTEMPTS_REACHED"],
        )

    def test_pre_publish_checks_actual_candidate_state(self) -> None:
        result = self.engine.evaluate(
            EnforcementPoint.PRE_PUBLISH,
            standard_policy(),
            approved=False,
            manifest_embedded=False,
            sharing=True,
            redacted=False,
        )
        self.assertEqual(result.outcome, Severity.BLOCK)
        self.assertEqual(
            {violation.code for violation in result.violations},
            {
                "APPROVAL_REQUIRED",
                "MANIFEST_NOT_EMBEDDED",
                "REDACTION_REQUIRED",
            },
        )


class PolicyStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_b2_policy_crud_survives_store_reconstruction(self) -> None:
        backend = DictBackend()
        store = B2PolicyStore(DaraStorage(backend))
        configured = standard_policy(
            policy_id="pol_client",
            name="Client policy",
        )

        await store.put_policy(configured)
        reconstructed = B2PolicyStore(DaraStorage(backend))

        self.assertEqual(
            await reconstructed.get_policy("demo", "pol_client"),
            configured,
        )
        self.assertEqual(
            await reconstructed.list_policies("demo"),
            [configured],
        )

    async def test_memory_policy_store_is_tenant_scoped(self) -> None:
        store = MemoryPolicyStore((standard_policy(),))
        self.assertIsNotNone(
            await store.get_policy("demo", "pol_standard")
        )
        self.assertIsNone(
            await store.get_policy("other", "pol_standard")
        )


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
            steps=(
                PlannedStep(
                    provider="replicate",
                    model="new-model",
                    modality="image",
                ),
            ),
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
            "flux-1.1-pro": Price(
                model="flux-1.1-pro",
                per_unit_usd=Decimal("0.250000"),
            ),
        }
        decisions = await asyncio.gather(
            engine.admit(policy, image_plan("job_a", variants=1), prices),
            engine.admit(policy, image_plan("job_b", variants=1), prices),
        )
        outcomes = sorted(decision.outcome for _, decision in decisions)
        self.assertEqual(outcomes, [Severity.ALLOW, Severity.BLOCK])


class PolicyEndpointTests(unittest.TestCase):
    def test_authenticated_policy_crud_persists_updates(self) -> None:
        policies = tuple(main_module.POLICIES.values())
        isolated_store = MemoryPolicyStore(policies)
        created = standard_policy(
            policy_id="pol_client",
            name="Client policy",
        )
        with (
            patch.object(main_module, "policy_store", isolated_store),
            patch.dict(
                main_module.POLICIES,
                {item.policy_id: item for item in policies},
                clear=True,
            ),
            patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}),
            TestClient(app) as client,
        ):
            response = client.post(
                "/v1/policies",
                headers={"Authorization": "Bearer test-token"},
                json=created.model_dump(mode="json"),
            )
            self.assertEqual(response.status_code, 201)

            updated = created.model_copy(
                update={"description": "Updated durable policy."}
            )
            response = client.put(
                "/v1/policies/pol_client",
                headers={"Authorization": "Bearer test-token"},
                json=updated.model_dump(mode="json"),
            )
            self.assertEqual(response.status_code, 200)

            response = client.get(
                "/v1/policies/pol_client",
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["description"],
            "Updated durable policy.",
        )

    def test_blocked_job_returns_structured_409_and_zero_spend(self) -> None:
        with patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}):
            with TestClient(app) as client:
                response = client.post(
                    "/v1/jobs?policy_id=pol_locked",
                    headers={"Authorization": "Bearer test-token"},
                    json={
                        "tenant_id": "demo",
                        "job_id": "job_http_block",
                        "provider": "openai",
                        "model": "gpt-image-2",
                        "modality": "image",
                        "aspect_ratio": "1:1",
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

    def test_job_mutation_requires_workspace_token(self) -> None:
        with patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}):
            with TestClient(app) as client:
                response = client.post("/v1/jobs", json={})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "UNAUTHORIZED")

    def test_model_registry_reports_deployed_openai_pipeline(self) -> None:
        with TestClient(app) as client:
            response = client.get("/v1/models")

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["provider"], "openai")
        self.assertEqual(item["model"], "gpt-image-2")
        self.assertEqual(item["reservation_per_image_usd"], "0.010000")

    def test_seeded_policies_use_supported_image_shapes(self) -> None:
        with (
            patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}),
            TestClient(app) as client,
        ):
            response = client.get(
                "/v1/policies",
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(response.status_code, 200)
        policies = response.json()["items"]
        self.assertEqual(len(policies), 3)
        self.assertTrue(
            all(policy["allowed_providers"] == ["openai"] for policy in policies)
        )
        self.assertIn(
            "3:2",
            next(
                policy
                for policy in policies
                if policy["policy_id"] == "pol_standard"
            )["allowed_aspect_ratios"],
        )


if __name__ == "__main__":
    unittest.main()
