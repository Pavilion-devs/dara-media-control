from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Awaitable, Callable, Protocol

from .estimator import PriceSource, estimate_run_cost
from .models import (
    CostEstimate,
    Decision,
    EnforcementPoint,
    JobRecord,
    Policy,
    RunPlan,
    Severity,
    Violation,
    ZERO,
    money,
)
from .repository import JobStore


class ProviderCall(Protocol):
    def __call__(self, plan: RunPlan) -> Awaitable[Decimal]: ...


class ReservationBook:
    def __init__(self) -> None:
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._settled: defaultdict[tuple[str, date], Decimal] = defaultdict(
            lambda: ZERO
        )
        self._reservations: dict[str, tuple[str, date, Decimal]] = {}

    def _today(self) -> date:
        return datetime.now(UTC).date()

    async def within_lock(
        self,
        tenant_id: str,
        operation: Callable[[], Awaitable[Decision]],
    ) -> Decision:
        async with self._locks[tenant_id]:
            return await operation()

    def committed_today(self, tenant_id: str) -> Decimal:
        day = self._today()
        reserved = sum(
            amount
            for reservation_tenant, reservation_day, amount in self._reservations.values()
            if reservation_tenant == tenant_id and reservation_day == day
        )
        return money(self._settled[(tenant_id, day)] + reserved)

    def reserve(self, plan: RunPlan, amount: Decimal) -> None:
        self._reservations[plan.job_id] = (
            plan.tenant_id,
            self._today(),
            money(amount),
        )

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


def outcome_for(violations: list[Violation]) -> Severity:
    if any(item.severity is Severity.BLOCK for item in violations):
        return Severity.BLOCK
    if violations:
        return Severity.WARN
    return Severity.ALLOW


def decision(
    point: EnforcementPoint,
    violations: list[Violation],
    estimated_cost_usd: Decimal,
) -> Decision:
    outcome = outcome_for(violations)
    return Decision(
        enforcement_point=point,
        outcome=outcome,
        violations=tuple(violations),
        estimated_cost_usd=money(estimated_cost_usd),
        saved_cost_usd=(
            money(estimated_cost_usd) if outcome is Severity.BLOCK else None
        ),
    )


class PolicyEngine:
    def __init__(
        self,
        store: JobStore,
        reservations: ReservationBook | None = None,
    ) -> None:
        self.store = store
        self.reservations = reservations or ReservationBook()

    def evaluate(
        self,
        point: EnforcementPoint,
        policy: Policy,
        *,
        plan: RunPlan | None = None,
        estimate: CostEstimate | None = None,
        committed_today: Decimal = ZERO,
        actual_cost: Decimal = ZERO,
        step_cost: Decimal | None = None,
        qa_score: float | None = None,
        attempts: int = 0,
        approved: bool = False,
        manifest_embedded: bool = False,
        sharing: bool = False,
        redacted: bool = False,
    ) -> Decision:
        violations: list[Violation] = []
        estimated = estimate.worst_case_usd if estimate is not None else ZERO
        if point is EnforcementPoint.PRE_FLIGHT:
            if plan is None or estimate is None:
                raise ValueError("pre_flight requires plan and estimate")
            violations.extend(self._pre_flight(policy, plan, estimate, committed_today))
        elif point is EnforcementPoint.PRE_STEP:
            if step_cost is not None and actual_cost + step_cost > policy.max_cost_usd_per_run:
                violations.append(
                    Violation(
                        code="RUN_BUDGET_EXCEEDED",
                        severity=Severity.BLOCK,
                        message="This step would push actual spend above the run budget.",
                        field="budget.max_cost_usd_per_run",
                        actual=str(money(actual_cost + step_cost)),
                        limit=str(policy.max_cost_usd_per_run),
                    )
                )
            if estimate is not None and actual_cost > (
                estimate.expected_usd
                * (Decimal(1) + policy.estimate_overrun_tolerance)
            ):
                violations.append(
                    Violation(
                        code="ESTIMATE_DRIFT",
                        severity=Severity.WARN,
                        message="Actual spend has drifted beyond the policy tolerance.",
                        field="budget.estimate_overrun_tolerance",
                        actual=str(money(actual_cost)),
                        limit=str(
                            money(
                                estimate.expected_usd
                                * (
                                    Decimal(1)
                                    + policy.estimate_overrun_tolerance
                                )
                            )
                        ),
                    )
                )
        elif point is EnforcementPoint.POST_STEP:
            if (
                policy.require_qa
                and qa_score is not None
                and qa_score < policy.min_qa_score
            ):
                violations.append(
                    Violation(
                        code="QA_BELOW_THRESHOLD",
                        severity=(
                            Severity.BLOCK
                            if policy.block_on_qa_failure
                            else Severity.WARN
                        ),
                        message="The generated candidate scored below the policy QA threshold.",
                        field="quality.min_qa_score",
                        actual=f"{qa_score:.3f}",
                        limit=f"{policy.min_qa_score:.3f}",
                    )
                )
                if attempts >= policy.max_attempts:
                    violations.append(
                        Violation(
                            code="MAX_ATTEMPTS_REACHED",
                            severity=Severity.BLOCK,
                            message="The QA loop exhausted the policy attempt limit.",
                            field="shape.max_attempts",
                            actual=str(attempts),
                            limit=str(policy.max_attempts),
                        )
                    )
        elif point is EnforcementPoint.PRE_PUBLISH:
            if policy.require_approval and not approved:
                violations.append(
                    Violation(
                        code="APPROVAL_REQUIRED",
                        severity=Severity.BLOCK,
                        message="Policy approval is required before publication.",
                        field="publish.require_approval",
                    )
                )
            if policy.embed_manifest and not manifest_embedded:
                violations.append(
                    Violation(
                        code="MANIFEST_NOT_EMBEDDED",
                        severity=Severity.BLOCK,
                        message="The prepared deliverable does not contain its manifest.",
                        field="publish.embed_manifest",
                    )
                )
            if (
                sharing
                and (
                    policy.redact_prompt_on_share
                    or policy.strip_params_on_share
                )
                and not redacted
            ):
                violations.append(
                    Violation(
                        code="REDACTION_REQUIRED",
                        severity=Severity.BLOCK,
                        message="The share derivative must be redacted before publication.",
                        field="publish.redact_prompt_on_share",
                    )
                )
        return decision(point, violations, estimated)

    def _pre_flight(
        self,
        policy: Policy,
        plan: RunPlan,
        estimate: CostEstimate,
        committed_today: Decimal,
    ) -> list[Violation]:
        violations: list[Violation] = []
        for step in plan.steps:
            if (
                step.provider not in policy.allowed_providers
                or step.provider in policy.denied_providers
            ):
                violations.append(
                    Violation(
                        code="PROVIDER_NOT_ALLOWED",
                        severity=Severity.BLOCK,
                        message=f"{step.provider} is not allowed by this policy.",
                        field="providers.allowed",
                        actual=step.provider,
                    )
                )
            if (
                step.model in policy.denied_models
                or (
                    "*" not in policy.allowed_models
                    and step.model not in policy.allowed_models
                )
            ):
                violations.append(
                    Violation(
                        code="MODEL_DENIED",
                        severity=Severity.BLOCK,
                        message=f"{step.model} is denied by this policy.",
                        field="models.denied",
                        actual=step.model,
                    )
                )
        checks = (
            (
                len(plan.steps) > policy.max_steps,
                "TOO_MANY_STEPS",
                "shape.max_steps",
                len(plan.steps),
                policy.max_steps,
            ),
            (
                plan.variants > policy.max_variants,
                "TOO_MANY_VARIANTS",
                "shape.max_variants",
                plan.variants,
                policy.max_variants,
            ),
            (
                plan.max_attempts > policy.max_attempts,
                "MAX_ATTEMPTS_REACHED",
                "shape.max_attempts",
                plan.max_attempts,
                policy.max_attempts,
            ),
        )
        for failed, code, field, actual, limit in checks:
            if failed:
                violations.append(
                    Violation(
                        code=code,
                        severity=Severity.BLOCK,
                        message=f"{field} exceeds this policy.",
                        field=field,
                        actual=str(actual),
                        limit=str(limit),
                    )
                )
        if plan.modality not in policy.allowed_modalities:
            violations.append(
                Violation(
                    code="MODALITY_NOT_ALLOWED",
                    severity=Severity.BLOCK,
                    message=(
                        f"{plan.modality} generation is not allowed by this policy."
                    ),
                    field="shape.allowed_modalities",
                    actual=plan.modality,
                )
            )
        if plan.aspect_ratio not in policy.allowed_aspect_ratios:
            violations.append(
                Violation(
                    code="ASPECT_RATIO_NOT_ALLOWED",
                    severity=Severity.BLOCK,
                    message=f"{plan.aspect_ratio} is not allowed by this policy.",
                    field="shape.allowed_aspect_ratios",
                    actual=plan.aspect_ratio,
                )
            )
        if (
            plan.duration_s is not None
            and plan.duration_s > policy.max_duration_s
        ):
            violations.append(
                Violation(
                    code="DURATION_EXCEEDED",
                    severity=Severity.BLOCK,
                    message="The requested duration exceeds this policy.",
                    field="shape.max_duration_s",
                    actual=str(plan.duration_s),
                    limit=str(policy.max_duration_s),
                )
            )
        for step_cost in estimate.per_step_usd:
            if step_cost is not None and step_cost > policy.max_cost_usd_per_step:
                violations.append(
                    Violation(
                        code="STEP_BUDGET_EXCEEDED",
                        severity=Severity.BLOCK,
                        message="A planned step exceeds the per-step budget.",
                        field="budget.max_cost_usd_per_step",
                        actual=str(step_cost),
                        limit=str(policy.max_cost_usd_per_step),
                    )
                )
        if estimate.worst_case_usd > policy.max_cost_usd_per_run:
            violations.append(
                Violation(
                    code="RUN_BUDGET_EXCEEDED",
                    severity=Severity.BLOCK,
                    message="The worst-case reservation exceeds the run budget.",
                    field="budget.max_cost_usd_per_run",
                    actual=str(estimate.worst_case_usd),
                    limit=str(policy.max_cost_usd_per_run),
                )
            )
        if committed_today + estimate.worst_case_usd > policy.max_cost_usd_per_day:
            violations.append(
                Violation(
                    code="DAILY_BUDGET_EXCEEDED",
                    severity=Severity.BLOCK,
                    message=(
                        "Settled spend plus active reservations would exceed the "
                        "daily limit."
                    ),
                    field="budget.max_cost_usd_per_day",
                    actual=str(money(committed_today + estimate.worst_case_usd)),
                    limit=str(policy.max_cost_usd_per_day),
                )
            )
        for model in estimate.unpriced_models:
            violations.append(
                Violation(
                    code="UNPRICED_MODEL",
                    severity=Severity.WARN,
                    message=(
                        f"{model} has no registry price; cost will be marked unknown."
                    ),
                    field="models.pricing",
                    actual=model,
                )
            )
        return violations

    async def simulate(
        self,
        policy: Policy,
        plan: RunPlan,
        prices: PriceSource,
    ) -> tuple[CostEstimate, Decision]:
        estimate = estimate_run_cost(plan, prices)
        return estimate, self.evaluate(EnforcementPoint.PRE_FLIGHT, policy, plan=plan, estimate=estimate)

    async def admit(
        self,
        policy: Policy,
        plan: RunPlan,
        prices: PriceSource,
    ) -> tuple[CostEstimate, Decision]:
        estimate = estimate_run_cost(plan, prices)

        async def evaluate_and_reserve() -> Decision:
            result = self.evaluate(
                EnforcementPoint.PRE_FLIGHT,
                policy,
                plan=plan,
                estimate=estimate,
                committed_today=self.reservations.committed_today(
                    plan.tenant_id
                ),
            )
            if result.outcome is not Severity.BLOCK:
                self.reservations.reserve(plan, estimate.worst_case_usd)
            return result
        return estimate, await self.reservations.within_lock(plan.tenant_id, evaluate_and_reserve)

    async def execute(
        self,
        policy: Policy,
        plan: RunPlan,
        prices: PriceSource,
        call_provider: ProviderCall,
    ) -> JobRecord:
        estimate, admitted = await self.admit(policy, plan, prices)
        blocked = admitted.outcome is Severity.BLOCK
        job = JobRecord(
            job_id=plan.job_id,
            tenant_id=plan.tenant_id,
            status="blocked" if blocked else "running",
            estimated_cost_usd=estimate.expected_usd,
            reserved_cost_usd=ZERO if blocked else estimate.worst_case_usd,
            policy_decisions=[admitted],
            error=(
                admitted.violations[0].message
                if blocked and admitted.violations
                else None
            ),
        )
        await self.store.put_job(job)
        if blocked:
            return job
        try:
            actual = money(await call_provider(plan))
            self.reservations.settle(plan.job_id, actual)
            job.status = "succeeded"
            job.actual_cost_usd = actual
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
