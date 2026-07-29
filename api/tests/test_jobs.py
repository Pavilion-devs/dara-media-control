from __future__ import annotations

import time
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient

import dara.main as main_module
from dara.jobs import LiveRunRecord, MemoryLiveRunStore
from dara.pipelines.still import StillPipelineOutput
from dara.policy import MemoryJobStore, PolicyEngine


class LiveRunStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_memory_store_round_trips_an_independent_record(self) -> None:
        store = MemoryLiveRunStore()
        original = LiveRunRecord(
            job_id="job_store",
            project_id="prj_test",
            prompt="A controlled still-image pipeline test",
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.010000"),
            worst_case_cost_usd=Decimal("0.030000"),
        )
        original.append_event("policy.allowed", "Allowed.")
        await store.put(original)
        restored = await store.get("demo", "job_store")

        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.events[0].seq, 1)
        original.events[0].message = "Changed locally."
        self.assertEqual(restored.events[0].message, "Allowed.")


class LiveRunEndpointTests(unittest.TestCase):
    def test_live_run_executes_in_background_and_persists_events(self) -> None:
        run_store = MemoryLiveRunStore()
        policy_store = MemoryJobStore()
        policy_engine = PolicyEngine(policy_store)

        async def fake_pipeline(**kwargs: object) -> StillPipelineOutput:
            on_event = kwargs["on_event"]
            assert callable(on_event)
            await on_event(
                {
                    "type": "pipeline.started",
                    "at": datetime.now(UTC),
                    "provider": "openai",
                    "model": "gpt-image-2",
                    "message": "Pipeline started.",
                }
            )
            return StillPipelineOutput(
                run_id="run_live_test",
                asset_id="ast_live_test",
                manifest_hash="a" * 64,
                source_sha256="b" * 64,
                published_sha256="c" * 64,
                published_content_address="dara/published/test.png",
                actual_cost_usd=Decimal("0.010000"),
                cost_basis="estimated",
                qa_score=0.91,
                qa_attempts=1,
                qa_issues=(),
            )

        with (
            patch.object(main_module, "live_run_store", run_store),
            patch.object(main_module, "store", policy_store),
            patch.object(main_module, "engine", policy_engine),
            patch.object(main_module, "run_still_pipeline", fake_pipeline),
            patch.dict(
                "os.environ",
                {
                    "DARA_API_TOKEN": "test-token",
                    "DARA_LIVE_GENERATION_ENABLED": "true",
                },
            ),
        ):
            with TestClient(main_module.app) as client:
                created = client.post(
                    "/v1/runs",
                    headers={"Authorization": "Bearer test-token"},
                    json={
                        "prompt": "A quiet editorial product photograph",
                        "aspect_ratio": "1:1",
                        "variants": 1,
                        "policy_id": "pol_standard",
                    },
                )
                self.assertEqual(created.status_code, 202)
                job_id = created.json()["job_id"]
                payload = created.json()
                for _ in range(20):
                    response = client.get(
                        f"/v1/runs/{job_id}",
                        headers={"Authorization": "Bearer test-token"},
                    )
                    payload = response.json()
                    if payload["status"] == "succeeded":
                        break
                    time.sleep(0.01)

        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["published_sha256"], "c" * 64)
        self.assertEqual(payload["actual_cost_usd"], "0.010000")
        self.assertEqual(payload["qa_status"], "passed")
        self.assertEqual(payload["qa_score"], 0.91)
        self.assertGreaterEqual(len(payload["events"]), 4)

    def test_live_run_is_disabled_fail_closed(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DARA_API_TOKEN": "test-token",
                "DARA_LIVE_GENERATION_ENABLED": "false",
            },
        ):
            with TestClient(main_module.app) as client:
                response = client.post(
                    "/v1/runs",
                    headers={"Authorization": "Bearer test-token"},
                    json={
                        "prompt": "A controlled live generation request",
                        "aspect_ratio": "1:1",
                    },
                )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"],
            "LIVE_GENERATION_DISABLED",
        )


if __name__ == "__main__":
    unittest.main()
