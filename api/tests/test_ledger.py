from __future__ import annotations

import tempfile
import threading
import unittest
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from fastapi.testclient import TestClient

import dara.main as main_module
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


class LedgerEndpointTests(unittest.TestCase):
    def test_ledger_requires_auth_and_rejects_raw_sql(self) -> None:
        with patch.dict("os.environ", {"DARA_API_TOKEN": "test-token"}):
            with TestClient(main_module.app) as client:
                unauthorized = client.get("/v1/ledger/summary")
                rejected = client.get(
                    "/v1/ledger/query",
                    params={"q": "SELECT * FROM accounting"},
                    headers={"Authorization": "Bearer test-token"},
                )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(
            rejected.json()["error"]["code"],
            "UNKNOWN_LEDGER_QUERY",
        )


if __name__ == "__main__":
    unittest.main()
