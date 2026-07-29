from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .storage import DaraStorage


RunStatus = Literal[
    "queued",
    "running",
    "publishing",
    "succeeded",
    "failed",
    "blocked",
]


class RunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int
    type: str
    at: datetime
    provider: str | None = None
    model: str | None = None
    message: str


class LiveRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    job_id: str
    tenant_id: str = "demo"
    project_id: str
    pipeline_id: str = "still-campaign"
    mode: Literal["live"] = "live"
    status: RunStatus = "queued"
    prompt: str
    aspect_ratio: str
    variants: int = 1
    policy_id: str
    expected_cost_usd: Decimal
    worst_case_cost_usd: Decimal
    actual_cost_usd: Decimal | None = None
    cost_basis: Literal["known", "estimated", "unknown"] = "unknown"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    events: list[RunEvent] = Field(default_factory=list)
    genblaze_run_id: str | None = None
    asset_id: str | None = None
    manifest_hash: str | None = None
    source_sha256: str | None = None
    published_sha256: str | None = None
    published_content_address: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    def append_event(
        self,
        event_type: str,
        message: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        at: datetime | None = None,
    ) -> None:
        self.events.append(
            RunEvent(
                seq=len(self.events) + 1,
                type=event_type,
                at=at or datetime.now(UTC),
                provider=provider,
                model=model,
                message=message,
            )
        )
        self.updated_at = datetime.now(UTC)


class LiveRunStore(Protocol):
    async def put(self, run: LiveRunRecord) -> None: ...

    async def get(self, tenant_id: str, job_id: str) -> LiveRunRecord | None: ...


def live_run_key(tenant_id: str, job_id: str) -> str:
    return f"dara/state/live-runs/{tenant_id}/{job_id}.json"


class B2LiveRunStore:
    def __init__(self, storage: DaraStorage) -> None:
        self.storage = storage

    async def put(self, run: LiveRunRecord) -> None:
        await asyncio.to_thread(
            self.storage.put_json,
            live_run_key(run.tenant_id, run.job_id),
            run,
        )

    async def get(self, tenant_id: str, job_id: str) -> LiveRunRecord | None:
        return await asyncio.to_thread(
            self.storage.get_json,
            live_run_key(tenant_id, job_id),
            LiveRunRecord,
        )


class MemoryLiveRunStore:
    def __init__(self) -> None:
        self.runs: dict[str, LiveRunRecord] = {}

    async def put(self, run: LiveRunRecord) -> None:
        self.runs[run.job_id] = run.model_copy(deep=True)

    async def get(self, tenant_id: str, job_id: str) -> LiveRunRecord | None:
        run = self.runs.get(job_id)
        if run is None or run.tenant_id != tenant_id:
            return None
        return run.model_copy(deep=True)
