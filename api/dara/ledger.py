from __future__ import annotations

import os
import threading
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from io import BytesIO
from urllib.parse import urlparse

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict

from .storage import DaraStorage


class AccountingRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    genblaze_run_id: str | None = None
    tenant_id: str
    project_id: str
    policy_id: str
    provider: str = "openai"
    model: str = "gpt-image-2"
    modality: str = "image"
    status: str
    cost_usd: Decimal | None = None
    saved_cost_usd: Decimal = Decimal("0.000000")
    cost_basis: str = "unknown"
    approved: bool = False
    qa_score: float | None = None
    qa_attempts: int = 0
    asset_id: str | None = None
    created_at: datetime


def accounting_key(record: AccountingRecord) -> str:
    created = record.created_at.astimezone(UTC)
    return (
        f"dara/ledger/accounting/year={created.year:04d}/"
        f"month={created.month:02d}/{record.job_id}.parquet"
    )


def write_accounting_record(
    storage: DaraStorage,
    record: AccountingRecord,
) -> str:
    row = record.model_dump(mode="python")
    table = pa.Table.from_pylist([row])
    output = BytesIO()
    pq.write_table(table, output)
    return storage.put_bytes(
        accounting_key(record),
        output.getvalue(),
        content_type="application/vnd.apache.parquet",
        metadata={"job-id": record.job_id, "table": "accounting"},
    )


QUERY_SQL = {
    "spend_by_model": """
        SELECT model, provider, COUNT(*) AS runs,
               CAST(COALESCE(SUM(cost_usd), 0) AS DECIMAL(18,6)) AS total_usd,
               CAST(COALESCE(AVG(cost_usd), 0) AS DECIMAL(18,6)) AS mean_usd
        FROM accounting
        WHERE created_at >= ? AND created_at < ? AND (? IS NULL OR project_id = ?)
        GROUP BY model, provider ORDER BY total_usd DESC, model
    """,
    "spend_by_project": """
        SELECT project_id, COUNT(*) AS runs,
               COUNT(asset_id) AS approved_assets,
               CAST(COALESCE(SUM(cost_usd), 0) AS DECIMAL(18,6)) AS total_usd
        FROM accounting
        WHERE created_at >= ? AND created_at < ? AND (? IS NULL OR project_id = ?)
        GROUP BY project_id ORDER BY total_usd DESC, project_id
    """,
    "spend_by_month": """
        SELECT strftime(created_at, '%Y-%m') AS month, COUNT(*) AS runs,
               CAST(COALESCE(SUM(cost_usd), 0) AS DECIMAL(18,6)) AS total_usd
        FROM accounting
        WHERE created_at >= ? AND created_at < ? AND (? IS NULL OR project_id = ?)
        GROUP BY 1 ORDER BY 1
    """,
    "cost_per_approved_asset": """
        SELECT COUNT(*) AS runs, COUNT(*) FILTER (approved) AS approved_assets,
               CAST(COALESCE(SUM(cost_usd), 0) AS DECIMAL(18,6)) AS total_usd,
               CAST(COALESCE(SUM(cost_usd) / NULLIF(COUNT(*) FILTER (approved), 0), 0)
                    AS DECIMAL(18,6)) AS cost_per_approved_asset_usd
        FROM accounting
        WHERE created_at >= ? AND created_at < ? AND (? IS NULL OR project_id = ?)
    """,
    "waste_ratio": """
        SELECT CAST(COALESCE(
            SUM(cost_usd) FILTER (NOT approved) / NULLIF(SUM(cost_usd), 0), 0
        ) AS DECIMAL(18,6)) AS waste_ratio
        FROM accounting
        WHERE created_at >= ? AND created_at < ? AND (? IS NULL OR project_id = ?)
    """,
    "qa_pass_rate": """
        SELECT model, COUNT(*) AS runs,
               CAST(COALESCE(AVG(CASE WHEN approved THEN 1.0 ELSE 0.0 END), 0)
                    AS DECIMAL(18,6)) AS pass_rate,
               CAST(COALESCE(AVG(qa_attempts), 0) AS DECIMAL(18,6)) AS mean_attempts
        FROM accounting
        WHERE created_at >= ? AND created_at < ? AND (? IS NULL OR project_id = ?)
        GROUP BY model ORDER BY model
    """,
    "policy_savings": """
        SELECT policy_id, COUNT(*) FILTER (status = 'blocked') AS blocked_runs,
               CAST(COALESCE(SUM(saved_cost_usd), 0) AS DECIMAL(18,6)) AS saved_usd
        FROM accounting
        WHERE created_at >= ? AND created_at < ? AND (? IS NULL OR project_id = ?)
        GROUP BY policy_id ORDER BY saved_usd DESC, policy_id
    """,
}


class Ledger:
    def __init__(self) -> None:
        self.connection = duckdb.connect(":memory:")
        self.lock = threading.Lock()
        self._configure_b2()

    def _configure_b2(self) -> None:
        endpoint_value = os.getenv("B2_ENDPOINT") or (
            f"https://s3.{os.environ['B2_REGION']}.backblazeb2.com"
        )
        parsed = urlparse(endpoint_value)
        endpoint = parsed.netloc or parsed.path
        self.connection.execute("INSTALL httpfs")
        self.connection.execute("LOAD httpfs")
        self.connection.execute(
            """
            CREATE OR REPLACE SECRET dara_b2 (
                TYPE s3, PROVIDER config, KEY_ID ?, SECRET ?, REGION ?,
                ENDPOINT ?, URL_STYLE 'path', USE_SSL true
            )
            """,
            [
                os.environ["B2_KEY_ID"],
                os.environ["B2_APP_KEY"],
                os.environ["B2_REGION"],
                endpoint,
            ],
        )
        source = (
            f"s3://{os.environ['B2_BUCKET']}/dara/ledger/accounting/"
            "year=*/month=*/*.parquet"
        )
        self.connection.execute(
            f"CREATE OR REPLACE VIEW accounting AS "
            f"SELECT * FROM read_parquet('{source}', hive_partitioning=true)"
        )

    def query(
        self,
        query_id: str,
        *,
        from_date: date,
        to_date: date,
        project_id: str | None = None,
    ) -> dict[str, object]:
        sql = QUERY_SQL.get(query_id)
        if sql is None:
            raise ValueError("Unknown ledger query.")
        start = datetime.combine(from_date, datetime.min.time(), tzinfo=UTC)
        end = datetime.combine(
            to_date + timedelta(days=1),
            datetime.min.time(),
            tzinfo=UTC,
        )
        params = [start, end, project_id, project_id]
        with self.lock:
            cursor = self.connection.execute(sql, params)
            columns = [item[0] for item in cursor.description]
            rows = [
                [
                    f"{value:.6f}" if isinstance(value, Decimal) else value
                    for value in row
                ]
                for row in cursor.fetchall()
            ]
        return {
            "query": query_id,
            "columns": columns,
            "rows": rows,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def summary(self, *, from_date: date, to_date: date) -> dict[str, object]:
        cost = self.query(
            "cost_per_approved_asset",
            from_date=from_date,
            to_date=to_date,
        )["rows"][0]
        waste = self.query(
            "waste_ratio",
            from_date=from_date,
            to_date=to_date,
        )["rows"][0]
        savings_rows = self.query(
            "policy_savings",
            from_date=from_date,
            to_date=to_date,
        )["rows"]
        saved = sum(Decimal(row[2]) for row in savings_rows)
        return {
            "run_count": cost[0],
            "approved_assets": cost[1],
            "total_spend_usd": cost[2],
            "cost_per_approved_asset_usd": cost[3],
            "waste_ratio": waste[0],
            "spend_prevented_usd": f"{saved:.6f}",
            "generated_at": datetime.now(UTC).isoformat(),
        }


@lru_cache(maxsize=1)
def get_ledger() -> Ledger:
    return Ledger()
