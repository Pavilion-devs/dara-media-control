from __future__ import annotations

import asyncio
import base64
import binascii
import ipaddress
import json
import logging
import os
import re
import secrets
import tempfile
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal

from genblaze_core import Manifest, Modality
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .policy import (
    B2JobStore,
    B2PolicyStore,
    CostEstimate,
    Decision,
    EnforcementPoint,
    JobRecord,
    JobStore,
    MemoryJobStore,
    MemoryPolicyStore,
    PlannedStep,
    Policy,
    PolicyEngine,
    PolicyStore,
    RunPlan,
    Severity,
    StoredDecision,
    job_to_json,
    money,
)
from .providers import (
    POLICY_REGISTRY,
    ROUTES,
    provider_name_for_model,
    route_reservation,
    unit_reservation,
)
from .jobs import (
    B2LiveRunStore,
    LiveRunRecord,
    LiveRunStore,
    MemoryLiveRunStore,
    RunAttempt,
    RunStatus,
)
from .ids import new_id
from .ledger import QUERY_SQL, AccountingRecord, get_ledger, write_accounting_record
from .projects import (
    B2ProjectStore,
    MemoryProjectStore,
    Project,
    ProjectCreate,
    ProjectStore,
    ProjectUpdate,
)
from .pipelines.still import (
    ASPECT_SIZES,
    PolicyGateRejectedError,
    QARejectedError,
    run_still_pipeline,
)
from .storage import DaraStorage, StorageUnavailableError
from .share import (
    PublicShare,
    ShareCreateRequest,
    ShareExpiredError,
    ShareIntegrityError,
    ShareNotFoundError,
    ShareService,
)
from .verify import (
    AssetRef,
    InvalidHashError,
    UnsupportedMediaError,
    VerificationResponse,
    Verifier,
    asset_ref_key,
    manifest_key,
)

logger = logging.getLogger("dara.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await seed_and_hydrate_policies()
        await seed_projects()
    except Exception:
        logger.exception("Policy startup hydration failed")
        raise
    try:
        orphaned = await reconcile_orphaned_runs()
        if orphaned:
            logger.warning("Reconciled %s orphaned live run(s) at startup", orphaned)
        restored = await hydrate_daily_spend_cap()
        logger.info("Restored today's live-spend commitment at $%.6f", restored)
    except Exception:
        logger.exception("Live-run startup reconciliation or spend hydration failed")
        raise
    yield


app = FastAPI(
    title="Dara API",
    version="0.1.0",
    description="Governance, provenance, and spend control for generated media.",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "DARA_ALLOWED_ORIGINS",
        "https://dara-media-control.asaborodaniel.chatgpt.site",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)


def env_with_legacy(primary: str, legacy: str, default: str) -> str:
    return os.getenv(primary) or os.getenv(legacy) or default


def active_tenant_id() -> str:
    return env_with_legacy("DARA_TENANT_ID", "KILN_TENANT_ID", "demo")


def build_job_store() -> JobStore:
    required = ("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_REGION")
    if all(os.getenv(name) for name in required):
        return B2JobStore(DaraStorage.from_env())
    return MemoryJobStore()


store = build_job_store()
engine = PolicyEngine(store)


def build_live_run_store() -> LiveRunStore:
    required = ("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_REGION")
    if all(os.getenv(name) for name in required):
        return B2LiveRunStore(DaraStorage.from_env())
    return MemoryLiveRunStore()


live_run_store = build_live_run_store()
live_tasks: set[asyncio.Task[None]] = set()
live_tasks_by_job: dict[str, asyncio.Task[None]] = {}


class DaraApiError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class VerifyRateLimiter:
    def __init__(self) -> None:
        self._attempts: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, client_id: str, *, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        with self._lock:
            attempts = self._attempts[client_id]
            while attempts and attempts[0] <= now - window_seconds:
                attempts.popleft()
            if len(attempts) >= limit:
                retry_after = max(1, int(window_seconds - (now - attempts[0])))
                raise DaraApiError(
                    429,
                    "RATE_LIMITED",
                    "Verification is temporarily rate-limited. Try again shortly.",
                    {"retry_after_s": retry_after},
                )
            attempts.append(now)


verify_rate_limiter = VerifyRateLimiter()


class PublicActionRateLimiter:
    def __init__(self) -> None:
        self._attempts: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(
        self,
        actor_id: str | None,
        *,
        action: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        if actor_id is None:
            return
        now = time.monotonic()
        key = f"{action}:{actor_id}"
        with self._lock:
            attempts = self._attempts[key]
            while attempts and attempts[0] <= now - window_seconds:
                attempts.popleft()
            if len(attempts) >= limit:
                retry_after = max(1, int(window_seconds - (now - attempts[0])))
                raise DaraApiError(
                    429,
                    "RATE_LIMITED",
                    "This public action is temporarily rate-limited. Try again shortly.",
                    {
                        "action": action,
                        "retry_after_s": retry_after,
                    },
                )
            attempts.append(now)


public_action_rate_limiter = PublicActionRateLimiter()
ANONYMOUS_ACTOR_PATTERN = re.compile(r"^anon_[0-9a-f]{32}$")


def trusted_anonymous_actor(value: str | None) -> str | None:
    if value is None or not ANONYMOUS_ACTOR_PATTERN.fullmatch(value):
        return None
    return value


def positive_env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def global_daily_spend_cap() -> Decimal:
    """Independent deployment ceiling applied to every live policy.

    Project policies may be stricter, but selecting a permissive policy must never
    raise the operator-owned public deployment limit.
    """
    raw = os.getenv("DARA_GLOBAL_DAILY_SPEND_CAP_USD", "5.000000")
    try:
        cap = money(raw)
    except Exception:
        logger.error(
            "Invalid DARA_GLOBAL_DAILY_SPEND_CAP_USD=%r; failing closed at $5/day",
            raw,
        )
        return money("5.000000")
    return cap if cap > 0 else money("5.000000")


def live_policy(policy: Policy) -> Policy:
    """Clamp a project policy to the deployment-wide live-spend ceiling."""
    cap = global_daily_spend_cap()
    if policy.max_cost_usd_per_day <= cap:
        return policy
    return policy.model_copy(update={"max_cost_usd_per_day": cap})


def enforce_public_action_limit(
    actor_header: str | None,
    *,
    action: str,
    limit_env: str,
    default_limit: int,
    window_seconds: int,
) -> str | None:
    actor_id = trusted_anonymous_actor(actor_header)
    public_action_rate_limiter.check(
        actor_id,
        action=action,
        limit=positive_env_int(limit_env, default_limit),
        window_seconds=window_seconds,
    )
    return actor_id


def verification_client_id(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    try:
        is_loopback = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        return peer
    forwarded = (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").partition(",")[0].strip()
    )
    if not forwarded:
        return peer
    try:
        return str(ipaddress.ip_address(forwarded))
    except ValueError:
        return peer


@lru_cache(maxsize=1)
def _default_verifier() -> Verifier:
    return Verifier(DaraStorage.from_env())


def get_verifier() -> Verifier:
    try:
        return _default_verifier()
    except StorageUnavailableError as exc:
        raise DaraApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "Dara's trusted storage is unavailable. Retry verification shortly.",
        ) from exc


@lru_cache(maxsize=1)
def get_share_service() -> ShareService:
    try:
        return ShareService(DaraStorage.from_env())
    except StorageUnavailableError as exc:
        raise DaraApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "Dara's trusted storage is unavailable. Retry sharing shortly.",
        ) from exc


def require_workspace_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = os.getenv("DARA_API_TOKEN")
    if not expected:
        raise DaraApiError(
            503,
            "WORKSPACE_AUTH_UNAVAILABLE",
            "Dara's private workspace API is not configured.",
        )
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, expected):
        raise DaraApiError(
            401,
            "UNAUTHORIZED",
            "A valid Dara workspace token is required.",
        )


def policy(
    policy_id: str,
    *,
    name: str,
    description: str,
    run_limit: str,
    daily_limit: str,
    allowed_modalities: frozenset[str] = frozenset({"image"}),
    allowed_ratios: frozenset[str] = frozenset({"1:1", "3:2", "2:3"}),
    require_approval: bool = True,
    block_on_qa_failure: bool = False,
) -> Policy:
    return Policy(
        policy_id=policy_id,
        name=name,
        description=description,
        allowed_providers=frozenset({"openai", "replicate"}),
        denied_models=frozenset(),
        allowed_modalities=allowed_modalities,
        allowed_aspect_ratios=allowed_ratios,
        max_steps=6,
        max_variants=4,
        max_attempts=3,
        max_cost_usd_per_step=money("0.500000"),
        max_cost_usd_per_run=money(run_limit),
        max_cost_usd_per_day=money(daily_limit),
        require_approval=require_approval,
        block_on_qa_failure=block_on_qa_failure,
    )


POLICIES = {
    "pol_permissive": policy(
        "pol_permissive",
        name="Permissive",
        description="High budgets with advisory QA for unrestricted exploration.",
        run_limit="20.000000",
        daily_limit="100.000000",
        require_approval=False,
    ),
    "pol_standard": policy(
        "pol_standard",
        name="Standard",
        description="Default guardrails for billable client work.",
        run_limit="2.000000",
        daily_limit="1.000000",
    ),
    "pol_locked": policy(
        "pol_locked",
        name="Locked down",
        description="Strict image-only controls with blocking QA.",
        run_limit="0.020000",
        daily_limit="1.000000",
        allowed_modalities=frozenset({"image"}),
        allowed_ratios=frozenset({"1:1"}),
        block_on_qa_failure=True,
    ),
}
SEEDED_POLICIES = tuple(POLICIES.values())


def build_policy_store() -> PolicyStore:
    required = ("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_REGION")
    if all(os.getenv(name) for name in required):
        return B2PolicyStore(DaraStorage.from_env())
    return MemoryPolicyStore(SEEDED_POLICIES)


policy_store = build_policy_store()


SEEDED_PROJECTS = (
    Project(
        project_id="prj_northwind_q3",
        name="Northwind — Q3 campaign",
        client="Northwind Foods",
        policy_id="pol_standard",
        tags=("campaign", "food"),
    ),
    Project(
        project_id="prj_atlas_brand",
        name="Atlas Hotels — Brand film",
        client="Atlas Hotels",
        policy_id="pol_standard",
        tags=("brand", "hospitality"),
    ),
    Project(
        project_id="prj_field_launch",
        name="Field Notes — Product launch",
        client="Field Notes",
        policy_id="pol_standard",
        tags=("launch", "product"),
    ),
)


def build_project_store() -> ProjectStore:
    required = ("B2_KEY_ID", "B2_APP_KEY", "B2_BUCKET", "B2_REGION")
    if all(os.getenv(name) for name in required):
        return B2ProjectStore(DaraStorage.from_env())
    return MemoryProjectStore(SEEDED_PROJECTS)


project_store = build_project_store()


async def seed_projects() -> None:
    tenant_id = active_tenant_id()
    for seeded in SEEDED_PROJECTS:
        if await project_store.get(tenant_id, seeded.project_id) is None:
            await project_store.put(seeded.model_copy(update={"tenant_id": tenant_id}))


async def seed_and_hydrate_policies() -> None:
    tenant_id = active_tenant_id()
    resolved: dict[str, Policy] = {}
    for seeded in SEEDED_POLICIES:
        persisted = await policy_store.get_policy(
            tenant_id,
            seeded.policy_id,
        )
        if persisted is None:
            await policy_store.put_policy(seeded)
            persisted = seeded
        elif persisted.allowed_providers == frozenset({"openai"}):
            persisted = persisted.model_copy(
                update={"allowed_providers": seeded.allowed_providers}
            )
            await policy_store.put_policy(persisted)
        resolved[persisted.policy_id] = persisted
    for persisted in await policy_store.list_policies(tenant_id):
        resolved[persisted.policy_id] = persisted
    POLICIES.clear()
    POLICIES.update(resolved)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: object) -> object:
    request_id = request.headers.get("X-Request-Id") or f"req_{secrets.token_hex(8)}"
    request.state.request_id = request_id
    response = await call_next(request)  # type: ignore[operator]
    response.headers["X-Request-Id"] = request_id
    return response


@app.exception_handler(DaraApiError)
async def dara_api_error_handler(
    request: Request,
    exc: DaraApiError,
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "request_id": getattr(request.state, "request_id", None),
            }
        },
    )


class SimulateRequest(BaseModel):
    tenant_id: str = "demo"
    job_id: str = "job_simulation"
    provider: str = "openai"
    model: str = "gpt-image-2"
    modality: str = "image"
    aspect_ratio: str = "1:1"
    variants: int = Field(default=3, ge=1, le=20)
    max_attempts: int = Field(default=3, ge=1, le=10)
    step_count: int = Field(default=1, ge=1, le=20)
    qa_enabled: bool = False
    prompt_expansion: bool = False

    def to_plan(self) -> RunPlan:
        steps: tuple[PlannedStep, ...] = ()
        if self.prompt_expansion:
            steps += (
                PlannedStep(
                    provider="openai",
                    model="gpt-4.1-mini",
                    modality="text",
                ),
            )
        steps += tuple(
            PlannedStep(
                provider=self.provider,
                model=self.model,
                modality=self.modality,
            )
            for _ in range(self.step_count)
        )
        if self.qa_enabled:
            steps += (
                PlannedStep(
                    provider="openai",
                    model="gpt-4.1-mini",
                    modality="image",
                ),
            )
        return RunPlan(
            tenant_id=self.tenant_id,
            job_id=self.job_id,
            modality=self.modality,
            aspect_ratio=self.aspect_ratio,
            variants=self.variants,
            max_attempts=self.max_attempts,
            steps=steps,
        )


class LiveRunRequest(BaseModel):
    project_id: str = Field(default="prj_northwind_q3", min_length=3, max_length=80)
    policy_id: str | None = None
    prompt: str = Field(min_length=8, max_length=4000)
    aspect_ratio: Literal["1:1", "3:2", "2:3"] = "1:1"
    variants: Literal[1] = 1


def encode_run_cursor(run: LiveRunRecord) -> str:
    raw = json.dumps(
        [run.created_at.isoformat(), run.job_id],
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_run_cursor(value: str) -> tuple[datetime, str]:
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(value + padding)
        created_at_value, job_id = json.loads(decoded)
        created_at = datetime.fromisoformat(created_at_value)
        if created_at.tzinfo is None or not isinstance(job_id, str):
            raise ValueError
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as exc:
        raise DaraApiError(
            400,
            "INVALID_CURSOR",
            "The run-history cursor is invalid.",
        ) from exc
    return created_at, job_id


def get_policy(policy_id: str) -> Policy:
    resolved = POLICIES.get(policy_id)
    if resolved is None:
        raise DaraApiError(404, "POLICY_NOT_FOUND", "Policy not found.")
    return resolved


async def resolve_policy(project_id: str, requested_policy_id: str | None) -> Policy:
    if requested_policy_id is not None:
        return get_policy(requested_policy_id)
    project = await project_store.get(active_tenant_id(), project_id)
    return get_policy(project.policy_id if project is not None else "pol_standard")


def decision_payload(
    estimate: CostEstimate,
    decision: Decision,
) -> dict[str, object]:
    return {
        "estimate": estimate.model_dump(mode="json"),
        "decision": decision.model_dump(mode="json"),
    }


def policy_payload(value: Policy) -> dict[str, object]:
    payload = value.model_dump(mode="json")
    for key in (
        "allowed_providers",
        "denied_providers",
        "allowed_models",
        "denied_models",
        "allowed_modalities",
        "allowed_aspect_ratios",
    ):
        payload[key] = sorted(payload[key])
    return payload


async def live_run_payload(run: LiveRunRecord) -> dict[str, object]:
    payload = run.model_dump(mode="json", exclude={"actor_id"})
    payload["expected_cost_usd"] = f"{run.expected_cost_usd:.6f}"
    payload["worst_case_cost_usd"] = f"{run.worst_case_cost_usd:.6f}"
    payload["actual_cost_usd"] = (
        f"{run.actual_cost_usd:.6f}"
        if run.actual_cost_usd is not None
        else None
    )
    payload["asset_url"] = None
    if run.status == "succeeded" and run.published_content_address:
        try:
            payload["asset_url"] = await asyncio.to_thread(
                DaraStorage.from_env().presign,
                run.published_content_address,
                expires_in=900,
            )
        except StorageUnavailableError:
            payload["asset_url"] = None
    return payload


async def reconcile_orphaned_runs() -> int:
    tenant_id = active_tenant_id()
    runs = await live_run_store.list(tenant_id)
    orphaned = 0
    for run in runs:
        if run.status not in {"queued", "running", "publishing"}:
            continue
        orphaned += 1
        engine.reservations.release(run.job_id)
        run.status = "failed"
        run.error_code = "ORPHANED"
        run.error_message = (
            "Dara restarted before this job reached a terminal state. The job was "
            "failed safely, its budget reservation was released, and no automatic "
            "provider retry was started."
        )
        run.append_event(
            "run.orphaned",
            run.error_message,
            provider="dara",
            model="recovery/v1",
        )
        await live_run_store.put(run)
        policy_job = await store.get_job(run.tenant_id, run.job_id)
        if policy_job is not None:
            policy_job.status = "failed"
            policy_job.reserved_cost_usd = money("0")
            policy_job.error = run.error_message
            await store.put_job(policy_job)
    return orphaned


async def hydrate_daily_spend_cap() -> Decimal:
    """Rebuild today's admission total from durable B2 live-run records.

    Failed runs with no settled cost are charged their worst-case reservation
    when they reached provider execution. This is intentionally pessimistic:
    after a crash Dara must not silently forget spend that may have occurred.
    """
    tenant_id = active_tenant_id()
    today = datetime.now(UTC).date()
    runs = await live_run_store.list(tenant_id)
    committed = money("0")
    for run in runs:
        if run.created_at.astimezone(UTC).date() != today or run.status == "blocked":
            continue
        if run.actual_cost_usd is not None:
            committed = money(committed + run.actual_cost_usd)
            continue
        provider_started = any(
            event.type in {"run.started", "step.started", "step.submitted"}
            for event in run.events
        )
        if run.status == "failed" and provider_started:
            committed = money(committed + run.worst_case_cost_usd)
    engine.reservations.restore_settled(tenant_id, today, committed)
    return committed


async def persist_accounting(
    run: LiveRunRecord,
    *,
    collapse_to_run: bool = False,
) -> None:
    failovers = sum(event.type == "step.failover" for event in run.events)
    costed_attempts = [
        attempt for attempt in run.attempts if attempt.cost_usd is not None
    ]
    if costed_attempts and not collapse_to_run:
        records = [
            AccountingRecord(
                job_id=f"{run.job_id}-attempt-{attempt.attempt}",
                source_job_id=run.job_id,
                genblaze_run_id=attempt.genblaze_run_id,
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                policy_id=run.policy_id,
                provider=attempt.provider or "unknown",
                model=attempt.model or "unknown",
                primary_model="gpt-image-2",
                failover_count=failovers if index == 0 else 0,
                status=attempt.status,
                cost_usd=attempt.cost_usd,
                saved_cost_usd=money("0"),
                cost_basis=attempt.cost_basis,
                approved=attempt.status == "approved",
                qa_score=attempt.qa_score,
                qa_attempts=1,
                asset_id=attempt.asset_id if attempt.status == "approved" else None,
                created_at=attempt.created_at,
            )
            for index, attempt in enumerate(costed_attempts)
        ]
    else:
        resolved_attempt = run.attempts[-1] if run.attempts else None
        records = [
            AccountingRecord(
                job_id=run.job_id,
                source_job_id=run.job_id,
                genblaze_run_id=run.genblaze_run_id,
                tenant_id=run.tenant_id,
                project_id=run.project_id,
                policy_id=run.policy_id,
                provider=(resolved_attempt.provider if resolved_attempt else None)
                or "openai",
                model=(resolved_attempt.model if resolved_attempt else None)
                or "gpt-image-2",
                primary_model="gpt-image-2",
                failover_count=failovers,
                status=run.status,
                cost_usd=run.actual_cost_usd,
                saved_cost_usd=money("0"),
                cost_basis=run.cost_basis,
                approved=run.status == "succeeded",
                qa_score=run.qa_score,
                qa_attempts=run.qa_attempts,
                asset_id=run.asset_id,
                created_at=run.created_at,
            )
        ]
    storage = DaraStorage.from_env()
    for record in records:
        await asyncio.to_thread(write_accounting_record, storage, record)


async def record_policy_decisions(
    run: LiveRunRecord,
    decisions: tuple[Decision, ...],
) -> None:
    if not decisions:
        return
    policy_job = await store.get_job(run.tenant_id, run.job_id)
    for resolved in decisions:
        run.policy_decisions.append(StoredDecision.model_validate(resolved))
        run.append_event(
            f"policy.{resolved.outcome.value}",
            (
                resolved.violations[0].message
                if resolved.violations
                else (
                    f"{resolved.enforcement_point.value.replace('_', ' ').title()} "
                    "policy gate allowed."
                )
            ),
            provider="dara",
            model=f"policy/{resolved.enforcement_point.value}",
        )
        if policy_job is not None:
            policy_job.policy_decisions.append(resolved)
    if policy_job is not None:
        await store.put_job(policy_job)
    await live_run_store.put(run)


async def execute_live_still(job_id: str) -> None:
    tenant_id = active_tenant_id()
    run = await live_run_store.get(tenant_id, job_id)
    if run is None:
        return
    run.status = "running"
    run.append_event(
        "run.started",
        "The authenticated live job started.",
        provider="dara",
        model="still-campaign/v1",
    )
    await live_run_store.put(run)

    async def record_event(event: dict[str, object]) -> None:
        if event["type"] == "publish.started":
            run.status = "publishing"
        run.append_event(
            str(event["type"]),
            str(event["message"]),
            provider=(
                str(event["provider"])
                if event.get("provider") is not None
                else None
            ),
            model=(
                str(event["model"])
                if event.get("model") is not None
                else None
            ),
            at=(
                event["at"]
                if isinstance(event.get("at"), datetime)
                else datetime.now(UTC)
            ),
        )
        await live_run_store.put(run)

    async def record_attempt(attempt: dict[str, object]) -> None:
        run.upsert_attempt(RunAttempt.model_validate(attempt))
        await live_run_store.put(run)

    try:
        parent_manifest: Manifest | None = None
        if run.parent_job_id is not None:
            parent = await live_run_store.get(tenant_id, run.parent_job_id)
            if parent is None or parent.genblaze_run_id is None:
                raise RuntimeError(
                    "The regeneration parent no longer has a trusted run."
                )
            parent_manifest = await asyncio.to_thread(
                DaraStorage.from_env().get_json,
                manifest_key(parent.genblaze_run_id),
                Manifest,
            )
            if parent_manifest is None:
                raise RuntimeError(
                    "The regeneration parent manifest is missing from B2."
                )
        output = await run_still_pipeline(
            tenant_id=run.tenant_id,
            project_id=run.project_id,
            prompt=run.prompt,
            aspect_ratio=run.aspect_ratio,
            estimated_cost_usd=run.expected_cost_usd,
            expansion_cost_usd=(
                money("0")
                if run.prompt_is_expanded
                else unit_reservation("gpt-4.1-mini") or money("0")
            ),
            generation_cost_usd=(
                route_reservation(Modality.IMAGE)
            ),
            qa_cost_usd=(
                unit_reservation("gpt-4.1-mini") or money("0")
            ),
            expand_prompt_enabled=not run.prompt_is_expanded,
            policy=get_policy(run.policy_id),
            policy_engine=engine,
            on_event=record_event,
            on_attempt=record_attempt,
            parent_manifest=parent_manifest,
        )
        await record_policy_decisions(run, output.policy_decisions)
        run.status = "succeeded"
        run.genblaze_run_id = output.run_id
        run.asset_id = output.asset_id
        run.manifest_hash = output.manifest_hash
        run.source_sha256 = output.source_sha256
        run.published_sha256 = output.published_sha256
        run.published_content_address = output.published_content_address
        run.actual_cost_usd = output.actual_cost_usd
        run.cost_basis = output.cost_basis
        run.qa_status = "passed"
        run.qa_score = output.qa_score
        run.qa_attempts = output.qa_attempts
        run.qa_issues = list(output.qa_issues)
        run.append_event(
            "run.completed",
            "The live asset is approved and its trusted published hash is on record.",
            provider="dara",
            model="still-campaign/v1",
        )
        await persist_accounting(run)
        engine.reservations.settle(run.job_id, output.actual_cost_usd)
        policy_job = await store.get_job(run.tenant_id, run.job_id)
        if policy_job is not None:
            policy_job.status = "succeeded"
            policy_job.actual_cost_usd = output.actual_cost_usd
            policy_job.reserved_cost_usd = money("0")
            await store.put_job(policy_job)
        await live_run_store.put(run)
    except QARejectedError as exc:
        await record_policy_decisions(run, exc.policy_decisions)
        engine.reservations.settle(run.job_id, exc.actual_cost_usd)
        run.status = "failed"
        run.actual_cost_usd = exc.actual_cost_usd
        run.cost_basis = "estimated"
        run.qa_status = "failed"
        run.qa_score = exc.score
        run.qa_attempts = exc.attempts
        run.qa_issues = list(exc.issues)
        run.error_code = "QA_REJECTED"
        run.error_message = (
            "No candidate passed Dara's visual QA gate. Every attempt remains "
            "recorded in B2; the unapproved images were not published."
        )
        run.append_event(
            "run.failed",
            run.error_message,
            provider="dara",
            model="qa/v1",
        )
        await persist_accounting(run)
        policy_job = await store.get_job(run.tenant_id, run.job_id)
        if policy_job is not None:
            policy_job.status = "failed"
            policy_job.actual_cost_usd = exc.actual_cost_usd
            policy_job.reserved_cost_usd = money("0")
            policy_job.error = run.error_message
            await store.put_job(policy_job)
        await live_run_store.put(run)
    except PolicyGateRejectedError as exc:
        await record_policy_decisions(run, exc.decisions)
        engine.reservations.settle(run.job_id, exc.actual_cost_usd)
        run.status = "failed"
        run.actual_cost_usd = exc.actual_cost_usd
        run.cost_basis = "estimated"
        blocking = next(
            (
                violation
                for decision in exc.decisions
                for violation in decision.violations
                if violation.severity.value == "block"
            ),
            None,
        )
        run.error_code = "POLICY_BLOCKED"
        run.error_message = (
            blocking.message
            if blocking is not None
            else "A policy gate rejected the live run."
        )
        run.append_event(
            "run.failed",
            run.error_message,
            provider="dara",
            model="policy/v1",
        )
        await persist_accounting(run)
        policy_job = await store.get_job(run.tenant_id, run.job_id)
        if policy_job is not None:
            policy_job.status = "failed"
            policy_job.actual_cost_usd = exc.actual_cost_usd
            policy_job.reserved_cost_usd = money("0")
            policy_job.error = run.error_message
            await store.put_job(policy_job)
        await live_run_store.put(run)
    except Exception:
        logger.exception("Live still job %s failed", job_id)
        engine.reservations.release(run.job_id)
        run.status = "failed"
        run.error_code = "PROVIDER_ERROR"
        run.error_message = (
            "The live image job failed. No additional retry was started; "
            "the recorded events remain available."
        )
        run.append_event(
            "run.failed",
            run.error_message,
            provider="dara",
            model="still-campaign/v1",
        )
        await persist_accounting(run)
        policy_job = await store.get_job(run.tenant_id, run.job_id)
        if policy_job is not None:
            policy_job.status = "failed"
            policy_job.reserved_cost_usd = money("0")
            policy_job.error = run.error_message
            await store.put_job(policy_job)
        await live_run_store.put(run)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "dara-api",
        "versions": {
            "genblaze": version("genblaze"),
            "genblaze-core": version("genblaze-core"),
            "genblaze-s3": version("genblaze-s3"),
        },
    }


@app.get("/healthz")
async def healthz() -> dict[str, object]:
    return {
        "ok": True,
        "b2": "configured" if os.getenv("B2_BUCKET") else "unconfigured",
        "genblaze_core": version("genblaze-core"),
        "providers": {
            "openai": (
                "configured" if os.getenv("OPENAI_API_KEY") else "unconfigured"
            ),
            "replicate": (
                "configured"
                if os.getenv("REPLICATE_API_TOKEN")
                else "unconfigured"
            ),
        },
        "demo_mode_available": True,
    }


@app.get("/v1/projects")
async def list_projects(
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    return {
        "items": [
            project.model_dump(mode="json")
            for project in await project_store.list(active_tenant_id())
        ]
    }


@app.post("/v1/projects", status_code=201)
async def create_project(
    request: ProjectCreate,
    _: Annotated[None, Depends(require_workspace_token)],
    actor_header: Annotated[str | None, Header(alias="X-Dara-Actor")] = None,
) -> dict[str, object]:
    enforce_public_action_limit(
        actor_header,
        action="project-mutation",
        limit_env="DARA_PROJECT_MUTATION_RATE_LIMIT_PER_HOUR",
        default_limit=10,
        window_seconds=3600,
    )
    get_policy(request.policy_id)
    project = Project(
        project_id=new_id("prj"),
        tenant_id=active_tenant_id(),
        **request.model_dump(),
    )
    await project_store.put(project)
    return project.model_dump(mode="json")


@app.get("/v1/projects/{project_id}")
async def read_project(
    project_id: str,
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    project = await project_store.get(active_tenant_id(), project_id)
    if project is None:
        raise DaraApiError(404, "NOT_FOUND", "Project not found.")
    return project.model_dump(mode="json")


@app.put("/v1/projects/{project_id}")
async def update_project(
    project_id: str,
    request: ProjectUpdate,
    _: Annotated[None, Depends(require_workspace_token)],
    actor_header: Annotated[str | None, Header(alias="X-Dara-Actor")] = None,
) -> dict[str, object]:
    enforce_public_action_limit(
        actor_header,
        action="project-mutation",
        limit_env="DARA_PROJECT_MUTATION_RATE_LIMIT_PER_HOUR",
        default_limit=10,
        window_seconds=3600,
    )
    current = await project_store.get(active_tenant_id(), project_id)
    if current is None:
        raise DaraApiError(404, "NOT_FOUND", "Project not found.")
    get_policy(request.policy_id)
    project = current.model_copy(update=request.model_dump())
    await project_store.put(project)
    return project.model_dump(mode="json")


async def asset_payload(asset_id: str) -> dict[str, object]:
    storage = DaraStorage.from_env()
    reference = await asyncio.to_thread(
        storage.get_json,
        asset_ref_key(asset_id),
        AssetRef,
    )
    if reference is None:
        raise DaraApiError(404, "NOT_FOUND", "Asset not found.")
    verification = None
    if reference.published_sha256 is not None:
        verification = await asyncio.to_thread(
            Verifier(storage).lookup_hash,
            reference.published_sha256,
        )
    download_key = (
        reference.published_content_address
        if reference.approved and reference.published_content_address
        else reference.source_content_address
    )
    asset_url = await asyncio.to_thread(
        storage.presign,
        download_key,
        expires_in=900,
    )
    return {
        "asset": reference.model_dump(mode="json"),
        "asset_url": asset_url,
        "verification": (
            verification.model_dump(mode="json") if verification is not None else None
        ),
    }


@app.get("/v1/assets/{asset_id}")
async def read_asset(
    asset_id: str,
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    try:
        return await asset_payload(asset_id)
    except StorageUnavailableError as exc:
        raise DaraApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "Dara's trusted asset store is temporarily unavailable.",
        ) from exc


@app.post("/v1/assets/{asset_id}/approve")
async def approve_asset(
    asset_id: str,
    _: Annotated[None, Depends(require_workspace_token)],
    actor_header: Annotated[str | None, Header(alias="X-Dara-Actor")] = None,
) -> dict[str, object]:
    enforce_public_action_limit(
        actor_header,
        action="asset-approval",
        limit_env="DARA_ASSET_APPROVAL_RATE_LIMIT_PER_HOUR",
        default_limit=20,
        window_seconds=3600,
    )
    payload = await asset_payload(asset_id)
    reference = AssetRef.model_validate(payload["asset"])
    if not reference.approved or reference.published_sha256 is None:
        raise DaraApiError(
            409,
            "ASSET_NOT_PUBLISHABLE",
            "This asset has no policy-approved published derivative. Approval occurs inside Dara's pre-publish pipeline gate.",
        )
    payload["approval"] = {
        "status": "already-approved",
        "message": "The pre-publish policy gate already approved this exact published hash.",
    }
    return payload


@app.get("/v1/models")
async def list_models() -> dict[str, object]:
    availability = (
        "configured"
        if os.getenv("OPENAI_API_KEY")
        else "unconfigured"
    )
    items: list[dict[str, object]] = []
    for route in ROUTES.values():
        item: dict[str, object] = {
            "provider": route.provider,
            "model": route.primary_model,
            "fallback_models": list(route.fallback_models),
            "modality": route.modality.value,
            "availability": availability,
            "reservation_usd": str(route.price_usd),
            "reservation_unit": route.price_unit,
            "pricing_basis": route.pricing_basis,
        }
        if route.modality.value == "image":
            item["reservation_per_image_usd"] = str(route.price_usd)
        items.append(item)
    items.append(
        {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "fallback_models": [],
            "modality": "vision-qa",
            "availability": availability,
            "reservation_per_evaluation_usd": str(
                unit_reservation("gpt-4.1-mini")
            ),
            "pricing_basis": "conservative structured vision evaluation",
        }
    )
    return {"items": items}


@app.get("/v1/policies")
async def list_policies(
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    tenant_id = active_tenant_id()
    values = await policy_store.list_policies(tenant_id)
    return {"items": [policy_payload(value) for value in values]}


@app.get("/v1/policies/{policy_id}")
async def read_policy(
    policy_id: str,
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    tenant_id = active_tenant_id()
    resolved = await policy_store.get_policy(tenant_id, policy_id)
    if resolved is None:
        raise DaraApiError(404, "POLICY_NOT_FOUND", "Policy not found.")
    return policy_payload(resolved)


def validate_policy_tenant(value: Policy) -> None:
    tenant_id = active_tenant_id()
    if value.tenant_id != tenant_id:
        raise DaraApiError(
            403,
            "TENANT_MISMATCH",
            "Policies can only be changed inside the active workspace.",
        )


@app.post("/v1/policies", status_code=201)
async def create_policy(
    value: Policy,
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    validate_policy_tenant(value)
    existing = await policy_store.get_policy(value.tenant_id, value.policy_id)
    if existing is not None:
        raise DaraApiError(
            409,
            "POLICY_EXISTS",
            "A policy with this identifier already exists.",
        )
    await policy_store.put_policy(value)
    POLICIES[value.policy_id] = value
    return policy_payload(value)


@app.put("/v1/policies/{policy_id}")
async def update_policy(
    policy_id: str,
    value: Policy,
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    validate_policy_tenant(value)
    if policy_id != value.policy_id:
        raise DaraApiError(
            400,
            "POLICY_ID_MISMATCH",
            "The path and document policy identifiers must match.",
        )
    existing = await policy_store.get_policy(value.tenant_id, policy_id)
    if existing is None:
        raise DaraApiError(404, "POLICY_NOT_FOUND", "Policy not found.")
    await policy_store.put_policy(value)
    POLICIES[value.policy_id] = value
    return policy_payload(value)


@app.get("/v1/ledger/summary")
async def ledger_summary(
    _: Annotated[None, Depends(require_workspace_token)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> dict[str, object]:
    resolved_to = to_date or datetime.now(UTC).date()
    resolved_from = from_date or resolved_to - timedelta(days=29)
    if resolved_from > resolved_to:
        raise DaraApiError(400, "INVALID_DATE_RANGE", "`from` must not follow `to`.")
    try:
        return await asyncio.to_thread(
            lambda: get_ledger().summary(
                from_date=resolved_from,
                to_date=resolved_to,
            )
        )
    except Exception as exc:
        logger.exception("Ledger summary query failed")
        raise DaraApiError(
            503,
            "LEDGER_UNAVAILABLE",
            "Dara's B2 ledger is temporarily unavailable.",
        ) from exc


@app.get("/v1/ledger/dashboard")
async def ledger_dashboard(
    _: Annotated[None, Depends(require_workspace_token)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    project_id: str | None = None,
) -> dict[str, object]:
    resolved_to = to_date or datetime.now(UTC).date()
    resolved_from = from_date or resolved_to - timedelta(days=29)
    if resolved_from > resolved_to:
        raise DaraApiError(400, "INVALID_DATE_RANGE", "`from` must not follow `to`.")
    try:
        return await asyncio.to_thread(
            lambda: get_ledger().dashboard(
                from_date=resolved_from,
                to_date=resolved_to,
                project_id=project_id,
            )
        )
    except Exception as exc:
        logger.exception("Ledger dashboard query failed")
        raise DaraApiError(
            503,
            "LEDGER_UNAVAILABLE",
            "Dara's B2 ledger is temporarily unavailable.",
        ) from exc


@app.get("/v1/ledger/query")
async def ledger_query(
    _: Annotated[None, Depends(require_workspace_token)],
    q: str,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    project_id: str | None = None,
) -> dict[str, object]:
    resolved_to = to_date or datetime.now(UTC).date()
    resolved_from = from_date or resolved_to - timedelta(days=29)
    if resolved_from > resolved_to:
        raise DaraApiError(400, "INVALID_DATE_RANGE", "`from` must not follow `to`.")
    if q not in QUERY_SQL:
        raise DaraApiError(
            400,
            "UNKNOWN_LEDGER_QUERY",
            "The requested ledger query is not allowlisted.",
        )
    try:
        return await asyncio.to_thread(
            lambda: get_ledger().query(
                q,
                from_date=resolved_from,
                to_date=resolved_to,
                project_id=project_id,
            )
        )
    except ValueError as exc:
        raise DaraApiError(
            400,
            "UNKNOWN_LEDGER_QUERY",
            "The requested ledger query is not allowlisted.",
        ) from exc
    except Exception as exc:
        logger.exception("Ledger query %s failed", q)
        raise DaraApiError(
            503,
            "LEDGER_UNAVAILABLE",
            "Dara's B2 ledger is temporarily unavailable.",
        ) from exc


async def queue_live_run(
    request: LiveRunRequest,
    *,
    actor_id: str | None = None,
    parent_job_id: str | None = None,
    source_manifest_hash: str | None = None,
    prompt_is_expanded: bool = False,
) -> dict[str, object]:
    if os.getenv("DARA_LIVE_GENERATION_ENABLED", "false").lower() != "true":
        raise DaraApiError(
            503,
            "LIVE_GENERATION_DISABLED",
            "Live generation is temporarily disabled. Demo replay remains available.",
        )
    actor_id = enforce_public_action_limit(
        actor_id,
        action="generation",
        limit_env="DARA_GENERATION_RATE_LIMIT_PER_HOUR",
        default_limit=6,
        window_seconds=3600,
    )

    tenant_id = active_tenant_id()
    resolved_policy = await resolve_policy(request.project_id, request.policy_id)
    job_id = new_id("job")
    image_route = ROUTES[Modality.IMAGE]
    plan = RunPlan(
        tenant_id=tenant_id,
        job_id=job_id,
        modality="image",
        aspect_ratio=request.aspect_ratio,
        variants=request.variants,
        max_attempts=3,
        steps=(
            (
                PlannedStep(
                    provider="openai",
                    model="gpt-4.1-mini",
                    modality="text",
                ),
            )
            if not prompt_is_expanded
            else ()
        )
        + (
            PlannedStep(
                provider=provider_name_for_model(image_route.primary_model),
                model=image_route.primary_model,
                modality="image",
            ),
            *(
                PlannedStep(
                    provider=provider_name_for_model(model),
                    model=model,
                    modality="image",
                )
                for model in image_route.fallback_models
            ),
            PlannedStep(
                provider="openai",
                model="gpt-4.1-mini",
                modality="image",
            ),
        ),
    )
    estimate, decision = await engine.admit(
        live_policy(resolved_policy),
        plan,
        POLICY_REGISTRY,
    )
    blocked = decision.outcome.value == "block"
    policy_job = JobRecord(
        job_id=job_id,
        tenant_id=tenant_id,
        status="blocked" if blocked else "queued",
        estimated_cost_usd=estimate.expected_usd,
        reserved_cost_usd=money("0") if blocked else estimate.worst_case_usd,
        policy_decisions=[decision],
        error=(
            decision.violations[0].message
            if blocked and decision.violations
            else None
        ),
    )
    await store.put_job(policy_job)

    if blocked:
        blocked_run = LiveRunRecord(
            job_id=job_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            project_id=request.project_id,
            prompt=request.prompt,
            prompt_is_expanded=prompt_is_expanded,
            aspect_ratio=request.aspect_ratio,
            variants=request.variants,
            policy_id=resolved_policy.policy_id,
            expected_cost_usd=estimate.expected_usd,
            worst_case_cost_usd=estimate.worst_case_usd,
            actual_cost_usd=money("0"),
            cost_basis="known",
            status="blocked",
            parent_job_id=parent_job_id,
            source_manifest_hash=source_manifest_hash,
            policy_decisions=[StoredDecision.model_validate(decision)],
            error_code="POLICY_BLOCKED",
            error_message=policy_job.error,
        )
        blocked_run.append_event(
            "policy.blocked",
            (
                policy_job.error
                or "This run was blocked before any provider call. Nothing was spent."
            ),
            provider="dara",
            model="policy/v1",
        )
        await live_run_store.put(blocked_run)
        await asyncio.to_thread(
            write_accounting_record,
            DaraStorage.from_env(),
            AccountingRecord(
                job_id=job_id,
                tenant_id=tenant_id,
                project_id=request.project_id,
            policy_id=resolved_policy.policy_id,
                status="blocked",
                cost_usd=money("0"),
                saved_cost_usd=estimate.expected_usd,
                cost_basis="known",
                approved=False,
                created_at=datetime.now(UTC),
            ),
        )
        raise DaraApiError(
            409,
            "POLICY_BLOCKED",
            (
                policy_job.error
                or "This live run was blocked before any provider call. Nothing was spent."
            ),
            {
                "job_id": job_id,
                "estimate": {
                    "expected_usd": str(estimate.expected_usd),
                    "worst_case_usd": str(estimate.worst_case_usd),
                },
                "violations": [
                    violation.model_dump(mode="json")
                    for violation in decision.violations
                ],
                "spent_usd": "0.000000",
            },
        )

    live_run = LiveRunRecord(
        job_id=job_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
        project_id=request.project_id,
        prompt=request.prompt,
        prompt_is_expanded=prompt_is_expanded,
        aspect_ratio=request.aspect_ratio,
        variants=request.variants,
        policy_id=resolved_policy.policy_id,
        expected_cost_usd=estimate.expected_usd,
        worst_case_cost_usd=estimate.worst_case_usd,
        parent_job_id=parent_job_id,
        source_manifest_hash=source_manifest_hash,
        policy_decisions=[StoredDecision.model_validate(decision)],
    )
    live_run.append_event(
        "policy.allowed",
        (
            f"Pre-flight allowed. Dara reserved "
            f"${estimate.worst_case_usd:.6f} before the provider call."
        ),
        provider="dara",
        model="policy/v1",
    )
    await live_run_store.put(live_run)
    task = asyncio.create_task(execute_live_still(job_id))
    live_tasks.add(task)
    live_tasks_by_job[job_id] = task

    def release_task(completed: asyncio.Task[None]) -> None:
        live_tasks.discard(completed)
        live_tasks_by_job.pop(job_id, None)

    task.add_done_callback(release_task)
    return await live_run_payload(live_run)


@app.post("/v1/runs", status_code=202)
async def create_live_run(
    request: LiveRunRequest,
    _: Annotated[None, Depends(require_workspace_token)],
    actor_header: Annotated[str | None, Header(alias="X-Dara-Actor")] = None,
) -> dict[str, object]:
    actor_id = trusted_anonymous_actor(actor_header)
    return await queue_live_run(request, actor_id=actor_id)


@app.get("/v1/runs")
async def list_live_runs(
    _: Annotated[None, Depends(require_workspace_token)],
    project_id: str | None = None,
    status: RunStatus | None = None,
    pipeline_id: str | None = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    if from_date is not None and to_date is not None and from_date > to_date:
        raise DaraApiError(400, "INVALID_DATE_RANGE", "`from` must not follow `to`.")
    runs = await live_run_store.list(active_tenant_id())
    filtered = [
        run
        for run in runs
        if (project_id is None or run.project_id == project_id)
        and (status is None or run.status == status)
        and (pipeline_id is None or run.pipeline_id == pipeline_id)
        and (from_date is None or run.created_at.astimezone(UTC).date() >= from_date)
        and (to_date is None or run.created_at.astimezone(UTC).date() <= to_date)
    ]
    filtered.sort(
        key=lambda run: (run.created_at, run.job_id),
        reverse=True,
    )
    if cursor is not None:
        cursor_key = decode_run_cursor(cursor)
        filtered = [
            run
            for run in filtered
            if (run.created_at, run.job_id) < cursor_key
        ]
    page = filtered[:limit]
    return {
        "items": await asyncio.gather(*(live_run_payload(run) for run in page)),
        "next_cursor": (
            encode_run_cursor(page[-1])
            if len(filtered) > limit and page
            else None
        ),
    }


@app.get("/v1/runs/{job_id}")
async def read_live_run(
    job_id: str,
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    tenant_id = active_tenant_id()
    run = await live_run_store.get(tenant_id, job_id)
    if run is None:
        raise DaraApiError(404, "NOT_FOUND", "Live run not found.")
    return await live_run_payload(run)


@app.post("/v1/runs/{job_id}/cancel")
async def cancel_live_run(
    job_id: str,
    _: Annotated[None, Depends(require_workspace_token)],
    actor_header: Annotated[str | None, Header(alias="X-Dara-Actor")] = None,
) -> dict[str, object]:
    enforce_public_action_limit(
        actor_header,
        action="cancel",
        limit_env="DARA_CANCEL_RATE_LIMIT_PER_HOUR",
        default_limit=20,
        window_seconds=3600,
    )
    tenant_id = active_tenant_id()
    run = await live_run_store.get(tenant_id, job_id)
    if run is None:
        raise DaraApiError(404, "NOT_FOUND", "Live run not found.")
    if run.status not in {"queued", "running", "publishing"}:
        raise DaraApiError(
            409,
            "RUN_NOT_CANCELLABLE",
            f"A {run.status} run cannot be cancelled.",
        )
    task = live_tasks_by_job.pop(job_id, None)
    provider_may_have_started = run.status in {"running", "publishing"}
    if task is not None:
        task.cancel()
    if provider_may_have_started:
        engine.reservations.settle(job_id, run.worst_case_cost_usd)
        run.actual_cost_usd = run.worst_case_cost_usd
        run.cost_basis = "estimated"
    else:
        engine.reservations.release(job_id)
        run.actual_cost_usd = money("0")
        run.cost_basis = "known"
    run.status = "cancelled"
    run.error_code = "CANCELLED"
    run.error_message = (
        "Cancellation was requested after provider work may have started. "
        "Dara conservatively accounted the full reservation; recorded attempts remain available."
        if provider_may_have_started
        else "The queued run was cancelled before provider work started. Nothing was spent."
    )
    run.append_event(
        "run.cancelled",
        run.error_message,
        provider="dara",
        model="control-plane/v1",
    )
    await live_run_store.put(run)
    await persist_accounting(run, collapse_to_run=True)
    policy_job = await store.get_job(tenant_id, job_id)
    if policy_job is not None:
        policy_job.status = "cancelled"
        policy_job.actual_cost_usd = run.actual_cost_usd
        policy_job.reserved_cost_usd = money("0")
        policy_job.error = run.error_message
        await store.put_job(policy_job)
    return await live_run_payload(run)


async def trusted_manifest_for(run: LiveRunRecord) -> Manifest:
    if run.genblaze_run_id is None:
        raise DaraApiError(
            409,
            "RUN_NOT_REGENERATABLE",
            "This job has no completed Genblaze run to regenerate.",
        )
    manifest = await asyncio.to_thread(
        DaraStorage.from_env().get_json,
        manifest_key(run.genblaze_run_id),
        Manifest,
    )
    if manifest is None or not manifest.verify_hash() or not manifest.verify():
        raise DaraApiError(
            409,
            "MANIFEST_UNTRUSTED",
            "The trusted manifest is missing or failed its integrity checks.",
        )
    return manifest


@app.post("/v1/regenerate/{job_id}", status_code=202)
async def regenerate_live_run(
    job_id: str,
    _: Annotated[None, Depends(require_workspace_token)],
    actor_header: Annotated[str | None, Header(alias="X-Dara-Actor")] = None,
) -> dict[str, object]:
    actor_id = trusted_anonymous_actor(actor_header)
    tenant_id = active_tenant_id()
    original = await live_run_store.get(tenant_id, job_id)
    if original is None:
        raise DaraApiError(404, "NOT_FOUND", "Live run not found.")
    if original.pipeline_id != "still-campaign":
        raise DaraApiError(
            409,
            "RUN_NOT_REGENERATABLE",
            "Only the still-campaign pipeline can be regenerated in this release.",
        )
    manifest = await trusted_manifest_for(original)
    if not manifest.run.steps:
        raise DaraApiError(
            409,
            "MANIFEST_UNSUPPORTED",
            "The trusted manifest has no generation step to reconstruct.",
        )
    step = manifest.run.steps[0]
    size = step.params.get("size")
    aspect_ratio = next(
        (ratio for ratio, candidate in ASPECT_SIZES.items() if candidate == size),
        None,
    )
    if (
        step.provider not in {"openai", "openai-dalle"}
        or step.model != "gpt-image-2"
        or step.prompt is None
        or aspect_ratio is None
        or step.params.get("n", 1) != 1
    ):
        raise DaraApiError(
            409,
            "MANIFEST_UNSUPPORTED",
            "This manifest cannot be safely reconstructed by the live still pipeline.",
        )
    request = LiveRunRequest(
        project_id=manifest.run.project_id or original.project_id,
        policy_id=original.policy_id,
        prompt=step.prompt,
        aspect_ratio=aspect_ratio,
        variants=1,
    )
    return await queue_live_run(
        request,
        actor_id=actor_id,
        parent_job_id=original.job_id,
        source_manifest_hash=manifest.canonical_hash,
        prompt_is_expanded=True,
    )


@app.get("/v1/runs/{job_id}/diff")
async def diff_live_runs(
    job_id: str,
    against: str,
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    tenant_id = active_tenant_id()
    current, other = await asyncio.gather(
        live_run_store.get(tenant_id, job_id),
        live_run_store.get(tenant_id, against),
    )
    if current is None or other is None:
        raise DaraApiError(404, "NOT_FOUND", "One of the requested jobs was not found.")
    if current.parent_job_id == other.job_id:
        original, regenerated = other, current
    elif other.parent_job_id == current.job_id:
        original, regenerated = current, other
    else:
        raise DaraApiError(
            400,
            "RUNS_NOT_RELATED",
            "The requested jobs are not a direct regeneration pair.",
        )

    original_manifest, regenerated_manifest = await asyncio.gather(
        trusted_manifest_for(original),
        trusted_manifest_for(regenerated),
    )
    original_step = original_manifest.run.steps[0]
    regenerated_step = regenerated_manifest.run.steps[0]
    original_payload, regenerated_payload = await asyncio.gather(
        live_run_payload(original),
        live_run_payload(regenerated),
    )
    parameter_pairs = (
        ("Prompt", original_step.prompt, regenerated.prompt),
        ("Aspect ratio", original.aspect_ratio, regenerated.aspect_ratio),
        ("Variants", original.variants, regenerated.variants),
        ("Provider", original_step.provider, regenerated_step.provider),
        ("Model", original_step.model, regenerated_step.model),
        ("Size", original_step.params.get("size"), regenerated_step.params.get("size")),
        (
            "Quality",
            original_step.params.get("quality"),
            regenerated_step.params.get("quality"),
        ),
        (
            "Output format",
            original_step.params.get("output_format"),
            regenerated_step.params.get("output_format"),
        ),
    )
    return {
        "original": original_payload,
        "regenerated": regenerated_payload,
        "parameters": [
            {
                "name": name,
                "original": left,
                "regenerated": right,
                "match": left == right,
            }
            for name, left, right in parameter_pairs
        ],
        "source_manifest_hash": regenerated.source_manifest_hash,
        "lineage_verified": (
            regenerated.parent_job_id == original.job_id
            and bool(regenerated.attempts)
            and regenerated.attempts[0].parent_run_id
            == original.genblaze_run_id
        ),
        "non_deterministic_note": (
            "Dara reproduces the recorded generation conditions and lineage. "
            "Media models are not guaranteed to return identical bytes."
        ),
    }


@app.get("/v1/runs/{job_id}/events")
async def stream_live_run_events(
    request: Request,
    job_id: str,
    _: Annotated[None, Depends(require_workspace_token)],
    last_event_id: Annotated[
        str | None,
        Header(alias="Last-Event-ID"),
    ] = None,
) -> StreamingResponse:
    tenant_id = active_tenant_id()
    try:
        starting_seq = max(0, int(last_event_id or "0"))
    except ValueError:
        starting_seq = 0

    async def event_stream():
        last_seq = starting_seq
        last_updated: datetime | None = None
        while True:
            if await request.is_disconnected():
                return
            run = await live_run_store.get(tenant_id, job_id)
            if run is None:
                error = json.dumps(
                    {"code": "NOT_FOUND", "message": "Live run not found."},
                    separators=(",", ":"),
                )
                yield f"event: run.error\ndata: {error}\n\n"
                return

            for event in run.events:
                if event.seq <= last_seq:
                    continue
                data = event.model_dump_json()
                yield f"id: {event.seq}\nevent: run.event\ndata: {data}\n\n"
                last_seq = event.seq

            if last_updated is None or run.updated_at > last_updated:
                snapshot = json.dumps(
                    await live_run_payload(run),
                    separators=(",", ":"),
                )
                yield f"event: run.snapshot\ndata: {snapshot}\n\n"
                last_updated = run.updated_at

            if run.status in {"succeeded", "failed", "blocked", "cancelled"}:
                return
            yield ": keepalive\n\n"
            await asyncio.sleep(0.8)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/v1/shares", status_code=201)
async def create_share(
    request: ShareCreateRequest,
    _: Annotated[None, Depends(require_workspace_token)],
    service: Annotated[ShareService, Depends(get_share_service)],
    actor_header: Annotated[str | None, Header(alias="X-Dara-Actor")] = None,
) -> dict[str, object]:
    actor_id = enforce_public_action_limit(
        actor_header,
        action="share",
        limit_env="DARA_SHARE_RATE_LIMIT_PER_HOUR",
        default_limit=20,
        window_seconds=3600,
    )
    tenant_id = active_tenant_id()
    run = await live_run_store.get(tenant_id, request.job_id)
    if run is None:
        raise DaraApiError(404, "NOT_FOUND", "Completed run not found.")
    policy_decision = engine.evaluate(
        EnforcementPoint.PRE_PUBLISH,
        get_policy(run.policy_id),
        approved=run.status == "succeeded",
        manifest_embedded=True,
        sharing=True,
        redacted=True,
    )
    if policy_decision.outcome is Severity.BLOCK:
        raise DaraApiError(
            409,
            "POLICY_BLOCKED",
            policy_decision.violations[0].message,
            {
                "violations": [
                    violation.model_dump(mode="json")
                    for violation in policy_decision.violations
                ]
            },
        )
    try:
        record = await asyncio.to_thread(
            service.create,
            run,
            asset_ids=request.asset_ids,
            expires_in_days=request.expires_in_days,
            actor_id=actor_id,
        )
    except ShareIntegrityError as exc:
        raise DaraApiError(409, "SHARE_NOT_READY", str(exc)) from exc
    except StorageUnavailableError as exc:
        raise DaraApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "Dara's trusted storage is unavailable. Retry sharing shortly.",
        ) from exc
    app_url = os.getenv(
        "DARA_PUBLIC_APP_URL",
        "https://dara-media-control.asaborodaniel.chatgpt.site",
    ).rstrip("/")
    return {
        "token": record.token,
        "url": f"{app_url}/share/{record.token}",
        "expires_at": record.expires_at,
    }


@app.get("/v1/share/{token}", response_model=PublicShare)
async def read_public_share(
    token: str,
    service: Annotated[ShareService, Depends(get_share_service)],
) -> PublicShare:
    try:
        return await asyncio.to_thread(service.read_public, token)
    except ShareNotFoundError as exc:
        raise DaraApiError(404, "SHARE_NOT_FOUND", "Share not found.") from exc
    except ShareExpiredError as exc:
        raise DaraApiError(410, "SHARE_EXPIRED", str(exc)) from exc
    except ShareIntegrityError as exc:
        raise DaraApiError(
            409,
            "SHARE_INTEGRITY_FAILED",
            str(exc),
        ) from exc
    except StorageUnavailableError as exc:
        raise DaraApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "Dara's trusted storage is unavailable. Retry this share shortly.",
        ) from exc


@app.post("/v1/verify", response_model=VerificationResponse)
async def verify_upload(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    verifier: Annotated[Verifier, Depends(get_verifier)],
) -> VerificationResponse:
    client_id = verification_client_id(request)
    limit = int(
        env_with_legacy(
            "DARA_VERIFY_RATE_LIMIT_PER_MIN",
            "KILN_VERIFY_RATE_LIMIT_PER_MIN",
            "10",
        )
    )
    verify_rate_limiter.check(f"upload:{client_id}", limit=limit)
    max_bytes = (
        int(env_with_legacy("DARA_MAX_UPLOAD_MB", "KILN_MAX_UPLOAD_MB", "100"))
        * 1024
        * 1024
    )
    suffix = Path(file.filename or "upload").suffix
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="dara-verify-",
            suffix=suffix,
            delete=False,
        ) as destination:
            temporary_path = Path(destination.name)
            size = 0
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise DaraApiError(
                        413,
                        "FILE_TOO_LARGE",
                        f"This file exceeds Dara's {max_bytes // (1024 * 1024)} MB verification limit.",
                    )
                destination.write(chunk)
        return await asyncio.to_thread(verifier.verify_path, temporary_path)
    except UnsupportedMediaError as exc:
        raise DaraApiError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            str(exc),
        ) from exc
    except StorageUnavailableError as exc:
        raise DaraApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "Dara's trusted storage is unavailable. Retry verification shortly.",
        ) from exc
    finally:
        await file.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@app.get("/v1/verify/{sha256}", response_model=VerificationResponse)
async def verify_hash(
    request: Request,
    sha256: str,
    verifier: Annotated[Verifier, Depends(get_verifier)],
) -> VerificationResponse:
    client_id = verification_client_id(request)
    limit = int(
        env_with_legacy(
            "DARA_VERIFY_HASH_RATE_LIMIT_PER_MIN",
            "KILN_VERIFY_HASH_RATE_LIMIT_PER_MIN",
            "30",
        )
    )
    verify_rate_limiter.check(f"hash:{client_id}", limit=limit)
    try:
        return await asyncio.to_thread(verifier.lookup_hash, sha256)
    except InvalidHashError as exc:
        raise DaraApiError(400, "INVALID_REQUEST", str(exc)) from exc
    except StorageUnavailableError as exc:
        raise DaraApiError(
            503,
            "STORAGE_UNAVAILABLE",
            "Dara's trusted storage is unavailable. Retry verification shortly.",
        ) from exc


@app.post("/v1/policies/{policy_id}/simulate")
async def simulate(
    policy_id: str,
    request: SimulateRequest,
    _: Annotated[None, Depends(require_workspace_token)],
    actor_header: Annotated[str | None, Header(alias="X-Dara-Actor")] = None,
) -> dict[str, object]:
    actor_id = enforce_public_action_limit(
        actor_header,
        action="policy-simulation",
        limit_env="DARA_POLICY_SIMULATION_RATE_LIMIT_PER_MINUTE",
        default_limit=60,
        window_seconds=60,
    )
    logger.info("Policy simulation actor=%s policy=%s", actor_id, policy_id)
    estimate, decision = await engine.simulate(
        get_policy(policy_id),
        request.to_plan(),
        POLICY_REGISTRY,
    )
    return decision_payload(estimate, decision)


@app.post("/v1/jobs")
async def create_demo_job(
    request: SimulateRequest,
    _: Annotated[None, Depends(require_workspace_token)],
    policy_id: str = "pol_standard",
) -> dict[str, object]:
    plan = request.to_plan()
    estimate, _ = await engine.simulate(
        get_policy(policy_id),
        plan,
        POLICY_REGISTRY,
    )

    async def demo_provider(_: RunPlan) -> Decimal:
        return estimate.expected_usd

    job = await engine.execute(
        get_policy(policy_id),
        plan,
        POLICY_REGISTRY,
        demo_provider,
    )
    if job.status == "blocked":
        raise DaraApiError(
            409,
            "POLICY_BLOCKED",
            (
                job.error
                or "This run was blocked before any provider call. Nothing was spent."
            ),
            {
                "job_id": job.job_id,
                "estimate": {
                    "expected_usd": str(estimate.expected_usd),
                    "worst_case_usd": str(estimate.worst_case_usd),
                },
                "violations": [
                    violation.model_dump(mode="json")
                    for decision in job.policy_decisions
                    for violation in decision.violations
                ],
                "spent_usd": "0.000000",
            },
        )
    return job_to_json(job)


@app.get("/v1/jobs/{job_id}")
async def get_job(
    job_id: str,
    _: Annotated[None, Depends(require_workspace_token)],
) -> dict[str, object]:
    tenant_id = active_tenant_id()
    job = await store.get_job(tenant_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job_to_json(job)
