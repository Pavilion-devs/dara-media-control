from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .policy import StoredDecision
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


class RunAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=1)
    genblaze_run_id: str
    parent_run_id: str | None = None
    status: Literal["running", "rejected", "approved", "failed"]
    prompt: str | None = None
    provider: str | None = None
    model: str | None = None
    qa_score: float | None = Field(default=None, ge=0, le=1)
    asset_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


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
    qa_status: Literal["not_run", "passed", "failed"] = "not_run"
    qa_score: float | None = None
    qa_attempts: int = 0
    qa_issues: list[str] = Field(default_factory=list)
    parent_job_id: str | None = None
    source_manifest_hash: str | None = None
    attempts: list[RunAttempt] = Field(default_factory=list)
    policy_decisions: list[StoredDecision] = Field(default_factory=list)
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

    def upsert_attempt(self, attempt: RunAttempt) -> None:
        for index, current in enumerate(self.attempts):
            if current.genblaze_run_id == attempt.genblaze_run_id:
                self.attempts[index] = attempt
                break
        else:
            self.attempts.append(attempt)
        self.attempts.sort(key=lambda item: item.attempt)
        self.updated_at = datetime.now(UTC)


class LiveRunStore(Protocol):
    async def put(self, run: LiveRunRecord) -> None: ...

    async def get(self, tenant_id: str, job_id: str) -> LiveRunRecord | None: ...

    async def list(self, tenant_id: str) -> list[LiveRunRecord]: ...


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

    async def list(self, tenant_id: str) -> list[LiveRunRecord]:
        prefix = f"dara/state/live-runs/{tenant_id}/"
        keys = await asyncio.to_thread(self.storage.list_prefix, prefix)
        records = await asyncio.gather(
            *(
                asyncio.to_thread(
                    self.storage.get_json,
                    key,
                    LiveRunRecord,
                )
                for key in keys
            )
        )
        return [record for record in records if record is not None]


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

    async def list(self, tenant_id: str) -> list[LiveRunRecord]:
        return [
            run.model_copy(deep=True)
            for run in self.runs.values()
            if run.tenant_id == tenant_id
        ]
