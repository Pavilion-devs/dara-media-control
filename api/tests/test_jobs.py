from __future__ import annotations

import asyncio
import time
import unittest
from datetime import UTC, datetime, timedelta
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

    async def test_startup_hydrates_settled_and_uncertain_spend_fail_closed(self) -> None:
        run_store = MemoryLiveRunStore()
        succeeded = LiveRunRecord(
            job_id="job_spend_succeeded",
            project_id="prj_test",
            prompt="A completed live generation",
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.200000"),
            worst_case_cost_usd=Decimal("0.400000"),
            actual_cost_usd=Decimal("0.200000"),
            status="succeeded",
        )
        uncertain = LiveRunRecord(
            job_id="job_spend_uncertain",
            project_id="prj_test",
            prompt="A provider run interrupted after it started",
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.100000"),
            worst_case_cost_usd=Decimal("0.300000"),
            status="failed",
        )
        uncertain.append_event("run.started", "Provider execution started.")
        old = succeeded.model_copy(
            update={
                "job_id": "job_spend_old",
                "created_at": datetime.now(UTC) - timedelta(days=1),
                "actual_cost_usd": Decimal("0.900000"),
            }
        )
        for run in (succeeded, uncertain, old):
            await run_store.put(run)

        restored_engine = PolicyEngine(MemoryJobStore())
        with (
            patch.object(main_module, "live_run_store", run_store),
            patch.object(main_module, "engine", restored_engine),
        ):
            committed = await main_module.hydrate_daily_spend_cap()

        self.assertEqual(committed, Decimal("0.500000"))
        self.assertEqual(
            restored_engine.reservations.committed_today("demo"),
            Decimal("0.500000"),
        )


class LiveRunEndpointTests(unittest.TestCase):
    def test_dara_configuration_names_override_legacy_kiln_aliases(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DARA_TENANT_ID": "dara-workspace",
                "KILN_TENANT_ID": "legacy-workspace",
            },
            clear=True,
        ):
            self.assertEqual(main_module.active_tenant_id(), "dara-workspace")
        with patch.dict(
            "os.environ",
            {"KILN_TENANT_ID": "legacy-workspace"},
            clear=True,
        ):
            self.assertEqual(main_module.active_tenant_id(), "legacy-workspace")

    def test_public_action_rate_limiter_is_scoped_by_anonymous_actor(self) -> None:
        limiter = main_module.PublicActionRateLimiter()
        actor = "anon_" + "c" * 32
        limiter.check(
            actor,
            action="generation",
            limit=1,
            window_seconds=60,
        )
        with self.assertRaises(main_module.DaraApiError) as raised:
            limiter.check(
                actor,
                action="generation",
                limit=1,
                window_seconds=60,
            )

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.code, "RATE_LIMITED")
        limiter.check(
            "anon_" + "d" * 32,
            action="generation",
            limit=1,
            window_seconds=60,
        )

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
                    headers={
                        "Authorization": "Bearer test-token",
                        "X-Dara-Actor": "anon_" + "b" * 32,
                    },
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

        stored = asyncio.run(run_store.get("demo", job_id))
        self.assertIsNotNone(stored)
        self.assertEqual(stored and stored.actor_id, "anon_" + "b" * 32)
        self.assertNotIn("actor_id", payload)
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["published_sha256"], "c" * 64)
        self.assertEqual(payload["actual_cost_usd"], "0.010000")
        self.assertEqual(payload["qa_status"], "passed")
        self.assertEqual(payload["qa_score"], 0.91)
        self.assertEqual(payload["policy_decisions"][0]["outcome"], "allow")
        self.assertEqual(
            payload["policy_decisions"][0]["enforcement_point"],
            "pre_flight",
        )
        self.assertGreaterEqual(len(payload["events"]), 4)

    def test_live_run_list_is_filtered_newest_first_and_cursor_paginated(
        self,
    ) -> None:
        run_store = MemoryLiveRunStore()
        base = LiveRunRecord(
            job_id="job_00000000000000000001",
            project_id="prj_alpha",
            prompt="A controlled live-history record",
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.020000"),
            worst_case_cost_usd=Decimal("0.060000"),
            status="succeeded",
            created_at=datetime(2026, 7, 28, 12, tzinfo=UTC),
            updated_at=datetime(2026, 7, 28, 12, tzinfo=UTC),
        )
        records = (
            base,
            base.model_copy(
                update={
                    "job_id": "job_00000000000000000002",
                    "project_id": "prj_beta",
                    "status": "blocked",
                    "created_at": datetime(2026, 7, 29, 12, tzinfo=UTC),
                    "updated_at": datetime(2026, 7, 29, 12, tzinfo=UTC),
                },
                deep=True,
            ),
            base.model_copy(
                update={
                    "job_id": "job_00000000000000000003",
                    "created_at": datetime(2026, 7, 30, 12, tzinfo=UTC),
                    "updated_at": datetime(2026, 7, 30, 12, tzinfo=UTC),
                },
                deep=True,
            ),
        )
        for record in records:
            asyncio.run(run_store.put(record))

        with (
            patch.object(main_module, "live_run_store", run_store),
            patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}),
            TestClient(main_module.app) as client,
        ):
            first = client.get(
                "/v1/runs?limit=2",
                headers={"Authorization": "Bearer test-token"},
            )
            cursor = first.json()["next_cursor"]
            second = client.get(
                f"/v1/runs?limit=2&cursor={cursor}",
                headers={"Authorization": "Bearer test-token"},
            )
            filtered = client.get(
                "/v1/runs?project_id=prj_alpha&status=succeeded",
                headers={"Authorization": "Bearer test-token"},
            )
            invalid = client.get(
                "/v1/runs?cursor=not-a-cursor",
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(
            [item["job_id"] for item in first.json()["items"]],
            [
                "job_00000000000000000003",
                "job_00000000000000000002",
            ],
        )
        self.assertIsInstance(cursor, str)
        self.assertEqual(
            [item["job_id"] for item in second.json()["items"]],
            ["job_00000000000000000001"],
        )
        self.assertIsNone(second.json()["next_cursor"])
        self.assertEqual(
            [item["job_id"] for item in filtered.json()["items"]],
            [
                "job_00000000000000000003",
                "job_00000000000000000001",
            ],
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "INVALID_CURSOR")

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
            actor_id: str | None = None,
            parent_job_id: str | None = None,
            source_manifest_hash: str | None = None,
            prompt_is_expanded: bool = False,
        ) -> dict[str, object]:
            captured.update(
                request=request,
                actor_id=actor_id,
                parent_job_id=parent_job_id,
                source_manifest_hash=source_manifest_hash,
                prompt_is_expanded=prompt_is_expanded,
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
                    headers={
                        "Authorization": "Bearer test-token",
                        "X-Dara-Actor": "anon_" + "a" * 32,
                    },
                )

        self.assertEqual(response.status_code, 202)
        request = captured["request"]
        assert isinstance(request, main_module.LiveRunRequest)
        self.assertEqual(request.prompt, manifest.run.steps[0].prompt)
        self.assertEqual(request.aspect_ratio, "1:1")
        self.assertEqual(captured["actor_id"], "anon_" + "a" * 32)
        self.assertEqual(captured["parent_job_id"], original.job_id)
        self.assertEqual(
            captured["source_manifest_hash"],
            manifest.canonical_hash,
        )
        self.assertIs(captured["prompt_is_expanded"], True)

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
