from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

import dara.main as main_module
import dara.ledger as ledger_module
from dara.jobs import LiveRunRecord, RunAttempt
from dara.ledger import AccountingRecord, Ledger, write_accounting_record


class CaptureStorage:
    def __init__(self) -> None:
        self.key = ""
        self.data = b""

    def put_bytes(self, key: str, data: bytes, **kwargs: object) -> str:
        del kwargs
        self.key = key
        self.data = data
        return key


def ledger_for_rows(rows: list[dict[str, object]], path: Path) -> Ledger:
    pq.write_table(pa.Table.from_pylist(rows), path)
    ledger = Ledger.__new__(Ledger)
    ledger.connection = duckdb.connect(":memory:")
    ledger.lock = threading.Lock()
    safe_path = str(path).replace("'", "''")
    ledger.connection.execute(
        f"CREATE VIEW accounting AS SELECT * FROM read_parquet('{safe_path}')",
    )
    return ledger


class AccountingWriterTests(unittest.TestCase):
    def test_accounting_record_is_month_partitioned_parquet(self) -> None:
        storage = CaptureStorage()
        record = AccountingRecord(
            job_id="job_accounting",
            genblaze_run_id="run_accounting",
            tenant_id="demo",
            project_id="prj_test",
            policy_id="pol_standard",
            status="succeeded",
            cost_usd=Decimal("0.015000"),
            cost_basis="estimated",
            approved=True,
            qa_score=0.9,
            qa_attempts=1,
            asset_id="ast_test",
            created_at=datetime(2026, 7, 29, tzinfo=UTC),
        )
        write_accounting_record(storage, record)  # type: ignore[arg-type]

        self.assertEqual(
            storage.key,
            "dara/ledger/accounting/year=2026/month=07/job_accounting.parquet",
        )
        table = pq.read_table(pa.BufferReader(storage.data))
        self.assertEqual(table.to_pylist()[0]["job_id"], "job_accounting")
        self.assertEqual(table.to_pylist()[0]["cost_usd"], Decimal("0.015000"))

    def test_accounting_write_invalidates_the_live_dashboard_cache(self) -> None:
        storage = CaptureStorage()
        cached_ledger = Mock()
        record = AccountingRecord(
            job_id="job_cache_invalidation",
            tenant_id="demo",
            project_id="prj_test",
            policy_id="pol_standard",
            status="succeeded",
            cost_usd=Decimal("0.010000"),
            approved=True,
            created_at=datetime(2026, 8, 2, tzinfo=UTC),
        )

        with patch.object(ledger_module, "_ledger_instance", cached_ledger):
            write_accounting_record(storage, record)  # type: ignore[arg-type]

        cached_ledger.invalidate_cache.assert_called_once_with()

    def test_live_run_accounting_preserves_each_paid_qa_attempt(self) -> None:
        run = LiveRunRecord(
            job_id="job_attempts",
            project_id="prj_northwind_q3",
            prompt="A production still with a recorded QA revision",
            aspect_ratio="1:1",
            policy_id="pol_standard",
            expected_cost_usd=Decimal("0.030000"),
            worst_case_cost_usd=Decimal("0.090000"),
            actual_cost_usd=Decimal("0.055000"),
            cost_basis="estimated",
            status="succeeded",
            attempts=[
                RunAttempt(
                    attempt=1,
                    genblaze_run_id="run_rejected",
                    status="rejected",
                    provider="openai-dalle",
                    model="gpt-image-2",
                    cost_usd=Decimal("0.030000"),
                    cost_basis="estimated",
                ),
                RunAttempt(
                    attempt=2,
                    genblaze_run_id="run_approved",
                    parent_run_id="run_rejected",
                    status="approved",
                    provider="replicate",
                    model="black-forest-labs/flux-1.1-pro",
                    cost_usd=Decimal("0.025000"),
                    cost_basis="estimated",
                    asset_id="ast_approved",
                ),
            ],
        )
        run.append_event(
            "step.failover",
            "Primary failed and the provider-diverse fallback recovered.",
        )
        captured: list[AccountingRecord] = []

        def capture(_: object, record: AccountingRecord) -> str:
            captured.append(record)
            return record.job_id

        with (
            patch.object(main_module.DaraStorage, "from_env", return_value=object()),
            patch.object(main_module, "write_accounting_record", side_effect=capture),
        ):
            import asyncio

            asyncio.run(main_module.persist_accounting(run))

        self.assertEqual(len(captured), 2)
        self.assertEqual(sum(item.cost_usd or Decimal("0") for item in captured), Decimal("0.055000"))
        self.assertFalse(captured[0].approved)
        self.assertTrue(captured[1].approved)
        self.assertEqual(captured[1].provider, "replicate")
        self.assertEqual(sum(item.failover_count for item in captured), 1)


class LedgerQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        rows = [
            {
                "job_id": "job_pass",
                "tenant_id": "demo",
                "project_id": "prj_a",
                "policy_id": "pol_standard",
                "provider": "openai",
                "model": "gpt-image-2",
                "primary_model": "gpt-image-2",
                "failover_count": 1,
                "status": "succeeded",
                "cost_usd": Decimal("0.015000"),
                "saved_cost_usd": Decimal("0.000000"),
                "approved": True,
                "qa_attempts": 1,
                "asset_id": "ast_pass",
                "created_at": datetime(2026, 7, 20, tzinfo=UTC),
            },
            {
                "job_id": "job_fail",
                "tenant_id": "demo",
                "project_id": "prj_a",
                "policy_id": "pol_standard",
                "provider": "openai",
                "model": "gpt-image-2",
                "primary_model": "gpt-image-2",
                "failover_count": 0,
                "status": "failed",
                "cost_usd": Decimal("0.015000"),
                "saved_cost_usd": Decimal("0.000000"),
                "approved": False,
                "qa_attempts": 1,
                "asset_id": None,
                "created_at": datetime(2026, 7, 21, tzinfo=UTC),
            },
            {
                "job_id": "job_block",
                "tenant_id": "demo",
                "project_id": "prj_b",
                "policy_id": "pol_locked",
                "provider": "openai",
                "model": "gpt-image-2",
                "primary_model": "gpt-image-2",
                "failover_count": 0,
                "status": "blocked",
                "cost_usd": Decimal("0.000000"),
                "saved_cost_usd": Decimal("0.015000"),
                "approved": False,
                "qa_attempts": 0,
                "asset_id": None,
                "created_at": datetime(2026, 7, 22, tzinfo=UTC),
            },
        ]
        self.ledger = ledger_for_rows(
            rows,
            Path(self.temporary.name) / "accounting.parquet",
        )

    def tearDown(self) -> None:
        self.ledger.connection.close()
        self.temporary.cleanup()

    def test_summary_counts_waste_and_policy_savings(self) -> None:
        summary = self.ledger.summary(
            from_date=date(2026, 7, 1),
            to_date=date(2026, 7, 31),
        )
        self.assertEqual(summary["run_count"], 3)
        self.assertEqual(summary["approved_assets"], 1)
        self.assertEqual(summary["total_spend_usd"], "0.030000")
        self.assertEqual(summary["cost_per_approved_asset_usd"], "0.030000")
        self.assertEqual(summary["waste_ratio"], "0.500000")
        self.assertEqual(summary["spend_prevented_usd"], "0.015000")

    def test_queries_are_allowlisted_and_project_bound(self) -> None:
        result = self.ledger.query(
            "spend_by_project",
            from_date=date(2026, 7, 1),
            to_date=date(2026, 7, 31),
            project_id="prj_a",
        )
        self.assertEqual(result["rows"], [["prj_a", 2, 1, "0.030000"]])
        with self.assertRaises(ValueError):
            self.ledger.query(
                "SELECT * FROM accounting",
                from_date=date(2026, 7, 1),
                to_date=date(2026, 7, 31),
            )

    def test_spend_by_month_groups_timestamp_rows(self) -> None:
        result = self.ledger.query(
            "spend_by_month",
            from_date=date(2026, 7, 1),
            to_date=date(2026, 7, 31),
        )
        self.assertEqual(result["rows"], [["2026-07", 3, "0.030000"]])

    def test_failover_rate_is_allowlisted_and_derived_from_attempt_records(self) -> None:
        result = self.ledger.query(
            "failover_rate",
            from_date=date(2026, 7, 1),
            to_date=date(2026, 7, 31),
        )
        self.assertEqual(
            result["rows"],
            [["gpt-image-2", "gpt-image-2", "openai", 1, 3, "0.333333"]],
        )

    def test_dashboard_returns_all_views_from_one_grouped_result(self) -> None:
        dashboard = self.ledger.dashboard(
            from_date=date(2026, 7, 1),
            to_date=date(2026, 7, 31),
        )
        self.assertEqual(
            dashboard["summary"],
            {
                "run_count": 3,
                "approved_assets": 1,
                "total_spend_usd": "0.030000",
                "cost_per_approved_asset_usd": "0.030000",
                "waste_ratio": "0.500000",
                "spend_prevented_usd": "0.015000",
                "generated_at": dashboard["summary"]["generated_at"],
            },
        )
        self.assertEqual(
            dashboard["models"]["rows"],
            [["gpt-image-2", "openai", 3, "0.030000", "0.010000"]],
        )
        self.assertEqual(
            dashboard["projects"]["rows"],
            [
                ["prj_a", 2, 1, "0.030000"],
                ["prj_b", 1, 0, "0.000000"],
            ],
        )
        self.assertEqual(
            dashboard["months"]["rows"],
            [["2026-07", 3, "0.030000"]],
        )

    def test_dashboard_cache_is_scoped_by_project(self) -> None:
        all_projects = self.ledger.dashboard(
            from_date=date(2026, 7, 1),
            to_date=date(2026, 7, 31),
        )
        cached = self.ledger.dashboard(
            from_date=date(2026, 7, 1),
            to_date=date(2026, 7, 31),
        )
        project = self.ledger.dashboard(
            from_date=date(2026, 7, 1),
            to_date=date(2026, 7, 31),
            project_id="prj_a",
        )
        self.assertEqual(
            cached["summary"]["generated_at"],
            all_projects["summary"]["generated_at"],
        )
        self.assertEqual(project["summary"]["run_count"], 2)
        self.assertEqual(project["projects"]["rows"], [["prj_a", 2, 1, "0.030000"]])


class LedgerEndpointTests(unittest.TestCase):
    def test_ledger_requires_auth_and_rejects_raw_sql(self) -> None:
        with patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}):
            with TestClient(main_module.app) as client:
                unauthorized = client.get("/v1/ledger/summary")
                unauthorized_dashboard = client.get("/v1/ledger/dashboard")
                rejected = client.get(
                    "/v1/ledger/query",
                    params={"q": "SELECT * FROM accounting"},
                    headers={"Authorization": "Bearer test-token"},
                )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(unauthorized_dashboard.status_code, 401)
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(
            rejected.json()["error"]["code"],
            "UNKNOWN_LEDGER_QUERY",
        )


class LedgerInitializationTests(unittest.TestCase):
    def setUp(self) -> None:
        ledger_module._ledger_instance = None
        ledger_module._ledger_retry_after = 0.0

    def tearDown(self) -> None:
        ledger_module._ledger_instance = None
        ledger_module._ledger_retry_after = 0.0

    def test_failed_initialization_cools_down_before_retrying_b2(self) -> None:
        recovered = object()
        with (
            patch.dict(
                "os.environ",
                {"DARA_LEDGER_INIT_RETRY_SECONDS": "5"},
            ),
            patch.object(
                ledger_module.time,
                "monotonic",
                side_effect=[100.0, 101.0, 106.0],
            ),
            patch.object(
                ledger_module,
                "Ledger",
                side_effect=[OSError("B2 cap exceeded"), recovered],
            ) as ledger_constructor,
        ):
            with self.assertRaisesRegex(OSError, "B2 cap exceeded"):
                ledger_module.get_ledger()
            with self.assertRaisesRegex(RuntimeError, "cooling down"):
                ledger_module.get_ledger()
            self.assertIs(ledger_module.get_ledger(), recovered)

        self.assertEqual(ledger_constructor.call_count, 2)


class LedgerQueryCooldownTests(unittest.TestCase):
    def test_failed_remote_query_cools_down_before_touching_b2_again(self) -> None:
        ledger = Ledger.__new__(Ledger)
        ledger.connection = Mock()
        ledger.connection.execute.side_effect = OSError("B2 cap exceeded")
        ledger.lock = threading.Lock()
        ledger._dashboard_cache = {}
        ledger._query_retry_after = 0.0

        with (
            patch.dict(
                "os.environ",
                {"DARA_LEDGER_QUERY_RETRY_SECONDS": "5"},
            ),
            patch.object(
                ledger_module.time,
                "monotonic",
                side_effect=[100.0, 101.0],
            ),
        ):
            with self.assertRaisesRegex(OSError, "B2 cap exceeded"):
                ledger.dashboard(
                    from_date=date(2026, 7, 1),
                    to_date=date(2026, 7, 31),
                )
            with self.assertRaisesRegex(RuntimeError, "cooling down"):
                ledger.dashboard(
                    from_date=date(2026, 7, 1),
                    to_date=date(2026, 7, 31),
                )

        self.assertEqual(ledger.connection.execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
