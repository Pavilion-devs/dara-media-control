from __future__ import annotations

import os
import threading
import time
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
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
    source_job_id: str | None = None
    genblaze_run_id: str | None = None
    tenant_id: str
    project_id: str
    policy_id: str
    provider: str = "openai"
    model: str = "gpt-image-2"
    modality: str = "image"
    primary_model: str | None = None
    failover_count: int = 0
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
        SELECT COUNT(*) AS runs,
               COUNT(DISTINCT asset_id) FILTER (approved) AS approved_assets,
               CAST(COALESCE(SUM(cost_usd), 0) AS DECIMAL(18,6)) AS total_usd,
               CAST(COALESCE(
                    SUM(cost_usd)
                    / NULLIF(COUNT(DISTINCT asset_id) FILTER (approved), 0), 0)
                    AS DECIMAL(18,6)) AS cost_per_approved_asset_usd
        FROM accounting
        WHERE created_at >= ? AND created_at < ? AND (? IS NULL OR project_id = ?)
    """,
    "failover_rate": """
        SELECT COALESCE(primary_model, model) AS primary_model,
               model AS resolved_model, provider,
               CAST(COALESCE(SUM(failover_count), 0) AS BIGINT) AS failovers,
               COUNT(*) AS attempts,
               CAST(COALESCE(SUM(failover_count) / NULLIF(COUNT(*), 0), 0)
                    AS DECIMAL(18,6)) AS failover_rate
        FROM accounting
        WHERE created_at >= ? AND created_at < ? AND (? IS NULL OR project_id = ?)
        GROUP BY 1, 2, 3
        HAVING SUM(failover_count) > 0
        ORDER BY failovers DESC, primary_model
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

DASHBOARD_SQL = """
    WITH filtered AS (
        SELECT *,
               strftime(created_at, '%Y-%m') AS accounting_month
        FROM accounting
        WHERE created_at >= ? AND created_at < ?
          AND (? IS NULL OR project_id = ?)
    )
    SELECT
        CASE
            WHEN GROUPING(model) = 0 THEN 'model'
            WHEN GROUPING(project_id) = 0 THEN 'project'
            WHEN GROUPING(accounting_month) = 0 THEN 'month'
            ELSE 'summary'
        END AS section,
        model,
        provider,
        project_id,
        accounting_month,
        COUNT(*) AS runs,
        COUNT(DISTINCT asset_id) FILTER (approved) AS approved_assets,
        COUNT(asset_id) AS published_assets,
        CAST(COALESCE(SUM(cost_usd), 0) AS DECIMAL(18,6)) AS total_usd,
        CAST(COALESCE(AVG(cost_usd), 0) AS DECIMAL(18,6)) AS mean_usd,
        CAST(
            COALESCE(
                SUM(cost_usd)
                / NULLIF(COUNT(DISTINCT asset_id) FILTER (approved), 0),
                0
            ) AS DECIMAL(18,6)
        ) AS cost_per_approved_asset_usd,
        CAST(
            COALESCE(
                SUM(cost_usd) FILTER (NOT approved) / NULLIF(SUM(cost_usd), 0),
                0
            ) AS DECIMAL(18,6)
        ) AS waste_ratio,
        CAST(COALESCE(SUM(saved_cost_usd), 0) AS DECIMAL(18,6)) AS saved_usd
    FROM filtered
    GROUP BY GROUPING SETS (
        (model, provider),
        (project_id),
        (accounting_month),
        ()
    )
    ORDER BY section, total_usd DESC, model, project_id, accounting_month
"""


class Ledger:
    def __init__(self) -> None:
        self.connection = duckdb.connect(":memory:")
        self.lock = threading.Lock()
        self._query_retry_after = 0.0
        self._dashboard_cache: dict[
            tuple[date, date, str | None],
            tuple[float, dict[str, object]],
        ] = {}
        self._configure_b2()

    def _begin_remote_query(self) -> float:
        now = time.monotonic()
        if now < getattr(self, "_query_retry_after", 0.0):
            raise RuntimeError("Ledger queries are cooling down after a B2 failure.")
        return now

    def _record_remote_query_failure(self, failed_at: float) -> None:
        retry_seconds = max(
            1,
            int(os.getenv("DARA_LEDGER_QUERY_RETRY_SECONDS", "300")),
        )
        self._query_retry_after = failed_at + retry_seconds

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
            f"SELECT * FROM read_parquet('{source}', hive_partitioning=true, union_by_name=true)"
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
            query_started_at = self._begin_remote_query()
            try:
                cursor = self.connection.execute(sql, params)
                columns = [item[0] for item in cursor.description]
                rows = [
                    [
                        f"{value:.6f}" if isinstance(value, Decimal) else value
                        for value in row
                    ]
                    for row in cursor.fetchall()
                ]
            except Exception:
                self._record_remote_query_failure(query_started_at)
                raise
        return {
            "query": query_id,
            "columns": columns,
            "rows": rows,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def summary(self, *, from_date: date, to_date: date) -> dict[str, object]:
        return self.dashboard(
            from_date=from_date,
            to_date=to_date,
        )["summary"]

    def dashboard(
        self,
        *,
        from_date: date,
        to_date: date,
        project_id: str | None = None,
    ) -> dict[str, object]:
        start = datetime.combine(from_date, datetime.min.time(), tzinfo=UTC)
        end = datetime.combine(
            to_date + timedelta(days=1),
            datetime.min.time(),
            tzinfo=UTC,
        )
        params = [start, end, project_id, project_id]
        cache_key = (from_date, to_date, project_id)
        cache_ttl_seconds = max(
            0,
            int(os.getenv("DARA_LEDGER_CACHE_SECONDS", "60")),
        )
        with self.lock:
            dashboard_cache = getattr(self, "_dashboard_cache", {})
            self._dashboard_cache = dashboard_cache
            cached = dashboard_cache.get(cache_key)
            if cached and time.monotonic() - cached[0] < cache_ttl_seconds:
                return deepcopy(cached[1])

            query_started_at = self._begin_remote_query()
            try:
                cursor = self.connection.execute(DASHBOARD_SQL, params)
                rows = cursor.fetchall()
            except Exception:
                self._record_remote_query_failure(query_started_at)
                raise

            generated_at = datetime.now(UTC).isoformat()
            summary: dict[str, object] | None = None
            model_rows: list[list[object]] = []
            project_rows: list[list[object]] = []
            month_rows: list[list[object]] = []
            for row in rows:
                (
                    section,
                    model,
                    provider,
                    row_project_id,
                    month,
                    runs,
                    approved_assets,
                    published_assets,
                    total_usd,
                    mean_usd,
                    cost_per_approved_asset_usd,
                    waste_ratio,
                    saved_usd,
                ) = row
                if section == "summary":
                    summary = {
                        "run_count": runs,
                        "approved_assets": approved_assets,
                        "total_spend_usd": f"{total_usd:.6f}",
                        "cost_per_approved_asset_usd": (
                            f"{cost_per_approved_asset_usd:.6f}"
                        ),
                        "waste_ratio": f"{waste_ratio:.6f}",
                        "spend_prevented_usd": f"{saved_usd:.6f}",
                        "generated_at": generated_at,
                    }
                elif section == "model":
                    model_rows.append(
                        [
                            model,
                            provider,
                            runs,
                            f"{total_usd:.6f}",
                            f"{mean_usd:.6f}",
                        ]
                    )
                elif section == "project":
                    project_rows.append(
                        [
                            row_project_id,
                            runs,
                            published_assets,
                            f"{total_usd:.6f}",
                        ]
                    )
                elif section == "month":
                    month_rows.append([month, runs, f"{total_usd:.6f}"])

            if summary is None:
                raise RuntimeError("Ledger dashboard summary was not produced.")

            result: dict[str, object] = {
                "summary": summary,
                "models": {
                    "query": "spend_by_model",
                    "columns": ["model", "provider", "runs", "total_usd", "mean_usd"],
                    "rows": model_rows,
                    "generated_at": generated_at,
                },
                "projects": {
                    "query": "spend_by_project",
                    "columns": [
                        "project_id",
                        "runs",
                        "approved_assets",
                        "total_usd",
                    ],
                    "rows": project_rows,
                    "generated_at": generated_at,
                },
                "months": {
                    "query": "spend_by_month",
                    "columns": ["month", "runs", "total_usd"],
                    "rows": month_rows,
                    "generated_at": generated_at,
                },
            }
            dashboard_cache[cache_key] = (time.monotonic(), deepcopy(result))
            return result


_ledger_instance: Ledger | None = None
_ledger_init_lock = threading.Lock()
_ledger_retry_after = 0.0


def get_ledger() -> Ledger:
    global _ledger_instance, _ledger_retry_after
    if _ledger_instance is None:
        with _ledger_init_lock:
            if _ledger_instance is None:
                now = time.monotonic()
                if now < _ledger_retry_after:
                    raise RuntimeError(
                        "Ledger initialization is cooling down after a B2 failure."
                    )
                try:
                    ledger = Ledger()
                except Exception:
                    retry_seconds = max(
                        1,
                        int(os.getenv("DARA_LEDGER_INIT_RETRY_SECONDS", "300")),
                    )
                    _ledger_retry_after = now + retry_seconds
                    raise
                _ledger_instance = ledger
                _ledger_retry_after = 0.0
    return _ledger_instance
