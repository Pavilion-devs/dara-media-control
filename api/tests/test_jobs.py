from __future__ import annotations

import asyncio
import time
import unittest
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from genblaze_core import Asset, Modality, Pipeline
from genblaze_core.testing import MockProvider

import dara.main as main_module
from dara.jobs import LiveRunRecord, MemoryLiveRunStore, RunAttempt
from dara.pipelines.still import StillPipelineOutput
from dara.policy import JobRecord, MemoryJobStore, PolicyEngine, money


def still_manifest(prompt: str = "A controlled still-image pipeline test"):
    asset = Asset(
        url="memory://candidate.png",
        media_type="image/png",
        sha256="a" * 64,
        size_bytes=128,
    )
    return (
        Pipeline("still-campaign", tenant_id="demo", project_id="prj_test")
        .step(
            MockProvider(name="openai", assets=[asset]),
            model="gpt-image-2",
            prompt=prompt,
            modality=Modality.IMAGE,
            size="1024x1024",
            quality="low",
            output_format="png",
            n=1,
        )
        .run(raise_on_failure=True)
        .manifest
    )


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

    async def test_attempts_are_upserted_into_a_parent_linked_version_tree(self) -> None:
        run = LiveRunRecord(
            job_id="job_versions",
            project_id="prj_test",
            prompt="A controlled still-image pipeline test",
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.010000"),
            worst_case_cost_usd=Decimal("0.030000"),
        )
        run.upsert_attempt(
            RunAttempt(
                attempt=1,
                genblaze_run_id="run_first",
                status="running",
            )
        )
        run.upsert_attempt(
            RunAttempt(
                attempt=1,
                genblaze_run_id="run_first",
                status="rejected",
                qa_score=0.54,
            )
        )
        run.upsert_attempt(
            RunAttempt(
                attempt=2,
                genblaze_run_id="run_second",
                parent_run_id="run_first",
                status="approved",
                qa_score=0.91,
            )
        )

        self.assertEqual(len(run.attempts), 2)
        self.assertEqual(run.attempts[0].status, "rejected")
        self.assertEqual(run.attempts[1].parent_run_id, "run_first")

    async def test_startup_reconciliation_fails_nonterminal_jobs_safely(self) -> None:
        run_store = MemoryLiveRunStore()
        policy_store = MemoryJobStore()
        policy_engine = PolicyEngine(policy_store)
        running = LiveRunRecord(
            job_id="job_orphaned",
            project_id="prj_test",
            prompt="A live job interrupted by a service restart",
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.015000"),
            worst_case_cost_usd=Decimal("0.045000"),
            status="running",
        )
        await run_store.put(running)
        await policy_store.put_job(
            JobRecord(
                job_id=running.job_id,
                tenant_id=running.tenant_id,
                status="running",
                estimated_cost_usd=money("0.015"),
                reserved_cost_usd=money("0.045"),
            )
        )

        with (
            patch.object(main_module, "live_run_store", run_store),
            patch.object(main_module, "store", policy_store),
            patch.object(main_module, "engine", policy_engine),
        ):
            count = await main_module.reconcile_orphaned_runs()

        restored = await run_store.get("demo", running.job_id)
        policy_job = await policy_store.get_job("demo", running.job_id)
        self.assertEqual(count, 1)
        assert restored is not None and policy_job is not None
        self.assertEqual(restored.status, "failed")
        self.assertEqual(restored.error_code, "ORPHANED")
        self.assertEqual(restored.events[-1].type, "run.orphaned")
        self.assertEqual(policy_job.reserved_cost_usd, money("0"))


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

        async def fake_accounting(_: LiveRunRecord) -> None:
            return None

        with (
            patch.object(main_module, "live_run_store", run_store),
            patch.object(main_module, "store", policy_store),
            patch.object(main_module, "engine", policy_engine),
            patch.object(main_module, "run_still_pipeline", fake_pipeline),
            patch.object(main_module, "persist_accounting", fake_accounting),
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

    def test_sse_stream_replays_events_and_terminal_snapshot(self) -> None:
        run_store = MemoryLiveRunStore()
        completed = LiveRunRecord(
            job_id="job_1234567890abcdef1234",
            project_id="prj_stream",
            prompt="A completed streamed still image job",
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.015000"),
            worst_case_cost_usd=Decimal("0.045000"),
            actual_cost_usd=Decimal("0.015000"),
            status="succeeded",
            qa_status="passed",
            qa_score=0.9,
            qa_attempts=1,
        )
        completed.append_event("run.completed", "The streamed run completed.")
        asyncio.run(run_store.put(completed))

        with (
            patch.object(main_module, "live_run_store", run_store),
            patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}),
        ):
            with TestClient(main_module.app) as client:
                with client.stream(
                    "GET",
                    f"/v1/runs/{completed.job_id}/events",
                    headers={"Authorization": "Bearer test-token"},
                ) as response:
                    body = "".join(response.iter_text())

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: run.event", body)
        self.assertIn("event: run.snapshot", body)
        self.assertIn('"status":"succeeded"', body)

    def test_regeneration_reconstructs_the_manifest_and_links_the_parent_job(self) -> None:
        run_store = MemoryLiveRunStore()
        manifest = still_manifest()
        original = LiveRunRecord(
            job_id="job_1234567890abcdef1234",
            project_id="prj_original",
            prompt="Editable UI text that must not be replayed",
            aspect_ratio="3:2",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.015000"),
            worst_case_cost_usd=Decimal("0.045000"),
            status="succeeded",
            genblaze_run_id=manifest.run.run_id,
            manifest_hash=manifest.canonical_hash,
        )
        asyncio.run(run_store.put(original))
        captured: dict[str, object] = {}

        async def fake_manifest(_: LiveRunRecord):
            return manifest

        async def fake_queue(
            request: main_module.LiveRunRequest,
            *,
            parent_job_id: str | None = None,
            source_manifest_hash: str | None = None,
        ) -> dict[str, object]:
            captured.update(
                request=request,
                parent_job_id=parent_job_id,
                source_manifest_hash=source_manifest_hash,
            )
            return {"job_id": "job_regenerated"}

        with (
            patch.object(main_module, "live_run_store", run_store),
            patch.object(main_module, "trusted_manifest_for", fake_manifest),
            patch.object(main_module, "queue_live_run", fake_queue),
            patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}),
        ):
            with TestClient(main_module.app) as client:
                response = client.post(
                    f"/v1/regenerate/{original.job_id}",
                    headers={"Authorization": "Bearer test-token"},
                )

        self.assertEqual(response.status_code, 202)
        request = captured["request"]
        assert isinstance(request, main_module.LiveRunRequest)
        self.assertEqual(request.prompt, manifest.run.steps[0].prompt)
        self.assertEqual(request.aspect_ratio, "1:1")
        self.assertEqual(captured["parent_job_id"], original.job_id)
        self.assertEqual(
            captured["source_manifest_hash"],
            manifest.canonical_hash,
        )

    def test_diff_requires_direct_lineage_and_reports_reproducible_conditions(
        self,
    ) -> None:
        run_store = MemoryLiveRunStore()
        original_manifest = still_manifest()
        regenerated_manifest = still_manifest()
        original = LiveRunRecord(
            job_id="job_1234567890abcdef1234",
            project_id="prj_test",
            prompt=str(original_manifest.run.steps[0].prompt),
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.015000"),
            worst_case_cost_usd=Decimal("0.045000"),
            actual_cost_usd=Decimal("0.015000"),
            status="succeeded",
            genblaze_run_id=original_manifest.run.run_id,
        )
        regenerated = original.model_copy(
            update={
                "job_id": "job_abcdef1234567890abcd",
                "parent_job_id": original.job_id,
                "genblaze_run_id": regenerated_manifest.run.run_id,
                "source_manifest_hash": original_manifest.canonical_hash,
                "attempts": [
                    RunAttempt(
                        attempt=1,
                        genblaze_run_id=regenerated_manifest.run.run_id,
                        parent_run_id=original_manifest.run.run_id,
                        status="approved",
                    )
                ],
            },
            deep=True,
        )
        asyncio.run(run_store.put(original))
        asyncio.run(run_store.put(regenerated))

        async def fake_manifest(run: LiveRunRecord):
            return (
                original_manifest
                if run.job_id == original.job_id
                else regenerated_manifest
            )

        with (
            patch.object(main_module, "live_run_store", run_store),
            patch.object(main_module, "trusted_manifest_for", fake_manifest),
            patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}),
        ):
            with TestClient(main_module.app) as client:
                response = client.get(
                    f"/v1/runs/{regenerated.job_id}/diff",
                    params={"against": original.job_id},
                    headers={"Authorization": "Bearer test-token"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["lineage_verified"])
        self.assertTrue(all(item["match"] for item in payload["parameters"]))
        self.assertIn("not guaranteed", payload["non_deterministic_note"])


if __name__ == "__main__":
    unittest.main()
