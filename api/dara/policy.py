from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Awaitable, Callable, Protocol

from pydantic import BaseModel, ConfigDict

from .storage import DaraStorage

ZERO = Decimal("0.000000")
MONEY_QUANTUM = Decimal("0.000001")


def money(value: Decimal | str | int) -> Decimal:
    return Decimal(value).quantize(MONEY_QUANTUM)


class Severity(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class Price:
    model: str
    per_unit_usd: Decimal | None


@dataclass(frozen=True)
class PlannedStep:
    provider: str
    model: str
    modality: str
    units: int = 1


@dataclass(frozen=True)
class RunPlan:
    tenant_id: str
    job_id: str
    modality: str
    aspect_ratio: str
    variants: int
    max_attempts: int
    steps: tuple[PlannedStep, ...]


@dataclass(frozen=True)
class Policy:
    policy_id: str
    allowed_providers: frozenset[str]
    denied_models: frozenset[str]
    allowed_modalities: frozenset[str]
    allowed_aspect_ratios: frozenset[str]
    max_steps: int
    max_variants: int
    max_attempts: int
    max_cost_usd_per_step: Decimal
    max_cost_usd_per_run: Decimal
    max_cost_usd_per_day: Decimal


@dataclass(frozen=True)
class Violation:
    code: str
    severity: Severity
    message: str
    field: str | None = None
    actual: str | None = None
    limit: str | None = None


@dataclass(frozen=True)
class CostEstimate:
    expected_usd: Decimal
    worst_case_usd: Decimal
    per_step_usd: tuple[Decimal | None, ...]
    unpriced_models: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    enforcement_point: str
    outcome: Severity
    violations: tuple[Violation, ...]
    evaluated_at: datetime
    estimated_cost_usd: Decimal
    saved_cost_usd: Decimal | None


@dataclass
class JobRecord:
    job_id: str
    tenant_id: str
    status: str
    estimated_cost_usd: Decimal
    reserved_cost_usd: Decimal
    actual_cost_usd: Decimal = ZERO
    policy_decisions: list[Decision] = field(default_factory=list)
    error: str | None = None


class JobStore(Protocol):
    async def put_job(self, job: JobRecord) -> None: ...

    async def get_job(self, tenant_id: str, job_id: str) -> JobRecord | None: ...


class MemoryJobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, JobRecord] = {}

    async def put_job(self, job: JobRecord) -> None:
        self.jobs[job.job_id] = job

    async def get_job(self, tenant_id: str, job_id: str) -> JobRecord | None:
        job = self.jobs.get(job_id)
        return job if job is not None and job.tenant_id == tenant_id else None


class StoredViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Severity
    message: str
    field: str | None = None
    actual: str | None = None
    limit: str | None = None


class StoredDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enforcement_point: str
    outcome: Severity
    violations: list[StoredViolation]
    evaluated_at: datetime
    estimated_cost_usd: Decimal
    saved_cost_usd: Decimal | None = None


class StoredJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    job_id: str
    tenant_id: str
    status: str
    estimated_cost_usd: Decimal
    reserved_cost_usd: Decimal
    actual_cost_usd: Decimal
    policy_decisions: list[StoredDecision]
    error: str | None = None

    @classmethod
    def from_record(cls, job: JobRecord) -> StoredJob:
        return cls.model_validate(
            {
                "schema_version": 1,
                "job_id": job.job_id,
                "tenant_id": job.tenant_id,
                "status": job.status,
                "estimated_cost_usd": job.estimated_cost_usd,
                "reserved_cost_usd": job.reserved_cost_usd,
                "actual_cost_usd": job.actual_cost_usd,
                "policy_decisions": [asdict(item) for item in job.policy_decisions],
                "error": job.error,
            }
        )

    def to_record(self) -> JobRecord:
        decisions = [
            Decision(
                enforcement_point=item.enforcement_point,
                outcome=item.outcome,
                violations=tuple(
                    Violation(
                        code=violation.code,
                        severity=violation.severity,
                        message=violation.message,
                        field=violation.field,
                        actual=violation.actual,
                        limit=violation.limit,
                    )
                    for violation in item.violations
                ),
                evaluated_at=item.evaluated_at,
                estimated_cost_usd=money(item.estimated_cost_usd),
                saved_cost_usd=(
                    money(item.saved_cost_usd)
                    if item.saved_cost_usd is not None
                    else None
                ),
            )
            for item in self.policy_decisions
        ]
        return JobRecord(
            job_id=self.job_id,
            tenant_id=self.tenant_id,
            status=self.status,
            estimated_cost_usd=money(self.estimated_cost_usd),
            reserved_cost_usd=money(self.reserved_cost_usd),
            actual_cost_usd=money(self.actual_cost_usd),
            policy_decisions=decisions,
            error=self.error,
        )


def job_storage_key(tenant_id: str, job_id: str) -> str:
    return f"dara/state/jobs/{tenant_id}/{job_id}.json"


class B2JobStore:
    """One-object-per-job durable store; the engine remains stateless."""

    def __init__(self, storage: DaraStorage) -> None:
        self.storage = storage

    async def put_job(self, job: JobRecord) -> None:
        await asyncio.to_thread(
            self.storage.put_json,
            job_storage_key(job.tenant_id, job.job_id),
            StoredJob.from_record(job),
        )

    async def get_job(self, tenant_id: str, job_id: str) -> JobRecord | None:
        stored = await asyncio.to_thread(
            self.storage.get_json,
            job_storage_key(tenant_id, job_id),
            StoredJob,
        )
        return stored.to_record() if stored is not None else None


class ProviderCall(Protocol):
    def __call__(self, plan: RunPlan) -> Awaitable[Decimal]: ...


def estimate_run_cost(
    plan: RunPlan, prices: dict[str, Price]
) -> CostEstimate:
    per_step: list[Decimal | None] = []
    unpriced: list[str] = []
    expected = ZERO

    for step in plan.steps:
        price = prices.get(step.model)
        if price is None or price.per_unit_usd is None:
            per_step.append(None)
            unpriced.append(step.model)
            continue
        step_cost = money(price.per_unit_usd * step.units * plan.variants)
        per_step.append(step_cost)
        expected += step_cost

    expected = money(expected)
    return CostEstimate(
        expected_usd=expected,
        worst_case_usd=money(expected * plan.max_attempts),
        per_step_usd=tuple(per_step),
        unpriced_models=tuple(dict.fromkeys(unpriced)),
    )


class ReservationBook:
    """Single-process atomic admission accounting, partitioned by tenant and UTC day."""

    def __init__(self) -> None:
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._settled: defaultdict[tuple[str, date], Decimal] = defaultdict(lambda: ZERO)
        self._reservations: dict[str, tuple[str, date, Decimal]] = {}

    def _today(self) -> date:
        return datetime.now(UTC).date()

    async def within_lock(
        self, tenant_id: str, operation: Callable[[], Awaitable[Decision]]
    ) -> Decision:
        async with self._locks[tenant_id]:
            return await operation()

    def committed_today(self, tenant_id: str) -> Decimal:
        day = self._today()
        reserved = sum(
            amount
            for _, (reservation_tenant, reservation_day, amount) in self._reservations.items()
            if reservation_tenant == tenant_id and reservation_day == day
        )
        return money(self._settled[(tenant_id, day)] + reserved)

    def reserve(self, plan: RunPlan, amount: Decimal) -> None:
        self._reservations[plan.job_id] = (plan.tenant_id, self._today(), money(amount))

    def settle(self, job_id: str, actual_cost: Decimal) -> None:
        reservation = self._reservations.pop(job_id, None)
        if reservation is None:
            return
        tenant_id, day, _ = reservation
        self._settled[(tenant_id, day)] = money(
            self._settled[(tenant_id, day)] + actual_cost
        )

    def release(self, job_id: str) -> None:
        self._reservations.pop(job_id, None)


class PolicyEngine:
    def __init__(self, store: JobStore, reservations: ReservationBook | None = None) -> None:
        self.store = store
        self.reservations = reservations or ReservationBook()

    async def simulate(
        self, policy: Policy, plan: RunPlan, prices: dict[str, Price]
    ) -> tuple[CostEstimate, Decision]:
        estimate = estimate_run_cost(plan, prices)
        decision = self._evaluate(
            policy, plan, estimate, committed_today=ZERO
        )
        return estimate, decision

    async def admit(
        self, policy: Policy, plan: RunPlan, prices: dict[str, Price]
    ) -> tuple[CostEstimate, Decision]:
        estimate = estimate_run_cost(plan, prices)

        async def evaluate_and_reserve() -> Decision:
            decision = self._evaluate(
                policy,
                plan,
                estimate,
                committed_today=self.reservations.committed_today(plan.tenant_id),
            )
            if decision.outcome is not Severity.BLOCK:
                self.reservations.reserve(plan, estimate.worst_case_usd)
            return decision

        decision = await self.reservations.within_lock(
            plan.tenant_id, evaluate_and_reserve
        )
        return estimate, decision

    async def execute(
        self,
        policy: Policy,
        plan: RunPlan,
        prices: dict[str, Price],
        call_provider: ProviderCall,
    ) -> JobRecord:
        estimate, decision = await self.admit(policy, plan, prices)
        blocked = decision.outcome is Severity.BLOCK
        job = JobRecord(
            job_id=plan.job_id,
            tenant_id=plan.tenant_id,
            status="blocked" if blocked else "running",
            estimated_cost_usd=estimate.expected_usd,
            reserved_cost_usd=ZERO if blocked else estimate.worst_case_usd,
            policy_decisions=[decision],
            error=decision.violations[0].message if blocked and decision.violations else None,
        )
        await self.store.put_job(job)

        if blocked:
            return job

        try:
            actual_cost = money(await call_provider(plan))
            self.reservations.settle(plan.job_id, actual_cost)
            job.status = "succeeded"
            job.actual_cost_usd = actual_cost
            job.reserved_cost_usd = ZERO
            await self.store.put_job(job)
            return job
        except Exception:
            self.reservations.release(plan.job_id)
            job.status = "failed"
            job.reserved_cost_usd = ZERO
            job.error = "Provider execution failed; inspect the recorded step events."
            await self.store.put_job(job)
            raise

    def _evaluate(
        self,
        policy: Policy,
        plan: RunPlan,
        estimate: CostEstimate,
        committed_today: Decimal,
    ) -> Decision:
        violations: list[Violation] = []

        for step in plan.steps:
            if step.provider not in policy.allowed_providers:
                violations.append(
                    Violation(
                        "PROVIDER_NOT_ALLOWED",
                        Severity.BLOCK,
                        f"{step.provider} is not allowed by this policy.",
                        "providers.allowed",
                        step.provider,
                    )
                )
            if step.model in policy.denied_models:
                violations.append(
                    Violation(
                        "MODEL_DENIED",
                        Severity.BLOCK,
                        f"{step.model} is denied by this policy.",
                        "models.denied",
                        step.model,
                    )
                )

        if len(plan.steps) > policy.max_steps:
            violations.append(
                Violation(
                    "TOO_MANY_STEPS",
                    Severity.BLOCK,
                    f"This plan has {len(plan.steps)} steps; the policy allows {policy.max_steps}.",
                    "shape.max_steps",
                    str(len(plan.steps)),
                    str(policy.max_steps),
                )
            )
        if plan.modality not in policy.allowed_modalities:
            violations.append(
                Violation(
                    "MODALITY_NOT_ALLOWED",
                    Severity.BLOCK,
                    f"{plan.modality} generation is not allowed by this policy.",
                    "shape.allowed_modalities",
                    plan.modality,
                )
            )
        if plan.aspect_ratio not in policy.allowed_aspect_ratios:
            violations.append(
                Violation(
                    "ASPECT_RATIO_NOT_ALLOWED",
                    Severity.BLOCK,
                    f"{plan.aspect_ratio} is not allowed by this policy.",
                    "shape.allowed_aspect_ratios",
                    plan.aspect_ratio,
                )
            )
        if plan.variants > policy.max_variants:
            violations.append(
                Violation(
                    "TOO_MANY_VARIANTS",
                    Severity.BLOCK,
                    f"This brief requests {plan.variants} variants; the policy allows {policy.max_variants}.",
                    "shape.max_variants",
                    str(plan.variants),
                    str(policy.max_variants),
                )
            )
        if plan.max_attempts > policy.max_attempts:
            violations.append(
                Violation(
                    "MAX_ATTEMPTS_REACHED",
                    Severity.BLOCK,
                    f"This plan reserves {plan.max_attempts} attempts; the policy allows {policy.max_attempts}.",
                    "shape.max_attempts",
                    str(plan.max_attempts),
                    str(policy.max_attempts),
                )
            )

        for step_cost in estimate.per_step_usd:
            if step_cost is not None and step_cost > policy.max_cost_usd_per_step:
                violations.append(
                    Violation(
                        "STEP_BUDGET_EXCEEDED",
                        Severity.BLOCK,
                        f"A planned step costs {step_cost}; the per-step limit is {policy.max_cost_usd_per_step}.",
                        "budget.max_cost_usd_per_step",
                        str(step_cost),
                        str(policy.max_cost_usd_per_step),
                    )
                )

        if estimate.worst_case_usd > policy.max_cost_usd_per_run:
            violations.append(
                Violation(
                    "RUN_BUDGET_EXCEEDED",
                    Severity.BLOCK,
                    f"This run reserves {estimate.worst_case_usd}; the run limit is {policy.max_cost_usd_per_run}.",
                    "budget.max_cost_usd_per_run",
                    str(estimate.worst_case_usd),
                    str(policy.max_cost_usd_per_run),
                )
            )
        if committed_today + estimate.worst_case_usd > policy.max_cost_usd_per_day:
            violations.append(
                Violation(
                    "DAILY_BUDGET_EXCEEDED",
                    Severity.BLOCK,
                    "Settled spend plus active reservations would exceed the daily limit.",
                    "budget.max_cost_usd_per_day",
                    str(money(committed_today + estimate.worst_case_usd)),
                    str(policy.max_cost_usd_per_day),
                )
            )
        for model in estimate.unpriced_models:
            violations.append(
                Violation(
                    "UNPRICED_MODEL",
                    Severity.WARN,
                    f"{model} has no registry price; cost reporting will be marked unknown.",
                    "models.pricing",
                    model,
                )
            )

        outcome = (
            Severity.BLOCK
            if any(item.severity is Severity.BLOCK for item in violations)
            else Severity.WARN
            if violations
            else Severity.ALLOW
        )
        return Decision(
            enforcement_point="pre_flight",
            outcome=outcome,
            violations=tuple(violations),
            evaluated_at=datetime.now(UTC),
            estimated_cost_usd=estimate.worst_case_usd,
            saved_cost_usd=estimate.worst_case_usd if outcome is Severity.BLOCK else None,
        )


def job_to_json(job: JobRecord) -> dict[str, object]:
    payload = asdict(job)
    for key in ("estimated_cost_usd", "reserved_cost_usd", "actual_cost_usd"):
        payload[key] = str(payload[key])
    for decision in payload["policy_decisions"]:
        decision["estimated_cost_usd"] = str(decision["estimated_cost_usd"])
        if decision["saved_cost_usd"] is not None:
            decision["saved_cost_usd"] = str(decision["saved_cost_usd"])
        decision["evaluated_at"] = decision["evaluated_at"].isoformat()
    return payload
