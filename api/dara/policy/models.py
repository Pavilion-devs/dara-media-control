from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


ZERO = Decimal("0.000000")
MONEY_QUANTUM = Decimal("0.000001")


def money(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANTUM)


class Severity(StrEnum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


class EnforcementPoint(StrEnum):
    PRE_FLIGHT = "pre_flight"
    PRE_STEP = "pre_step"
    POST_STEP = "post_step"
    PRE_PUBLISH = "pre_publish"


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Price(FrozenModel):
    model: str
    per_unit_usd: Decimal | None

    @field_validator("per_unit_usd")
    @classmethod
    def normalize_price(cls, value: Decimal | None) -> Decimal | None:
        return money(value) if value is not None else None


class PlannedStep(FrozenModel):
    provider: str
    model: str
    modality: str
    units: int = Field(default=1, ge=1)


class RunPlan(FrozenModel):
    tenant_id: str
    job_id: str
    modality: str
    aspect_ratio: str
    variants: int = Field(ge=1)
    max_attempts: int = Field(ge=1)
    duration_s: Decimal | None = Field(default=None, ge=0)
    steps: tuple[PlannedStep, ...]


class Policy(FrozenModel):
    schema_version: int = 1
    policy_id: str
    tenant_id: str = "demo"
    name: str = ""
    description: str = ""
    allowed_providers: frozenset[str]
    denied_providers: frozenset[str] = frozenset()
    allowed_models: frozenset[str] = frozenset({"*"})
    denied_models: frozenset[str] = frozenset()
    allowed_modalities: frozenset[str]
    allowed_aspect_ratios: frozenset[str]
    max_steps: int = Field(ge=1)
    max_variants: int = Field(ge=1)
    max_attempts: int = Field(ge=1)
    max_duration_s: Decimal = Field(default=Decimal("10"), ge=0)
    max_cost_usd_per_step: Decimal = Field(ge=0)
    max_cost_usd_per_run: Decimal = Field(ge=0)
    max_cost_usd_per_day: Decimal = Field(ge=0)
    estimate_overrun_tolerance: Decimal = Field(
        default=Decimal("0.250000"),
        ge=0,
    )
    min_qa_score: float = Field(default=0.75, ge=0, le=1)
    require_qa: bool = True
    block_on_qa_failure: bool = False
    require_approval: bool = True
    embed_manifest: bool = True
    redact_prompt_on_share: bool = True
    strip_params_on_share: bool = True
    asset_retention_days: int = Field(default=365, ge=1)
    manifest_retention_days: int = Field(default=2555, ge=1)

    @field_validator(
        "max_cost_usd_per_step",
        "max_cost_usd_per_run",
        "max_cost_usd_per_day",
        "estimate_overrun_tolerance",
        "max_duration_s",
    )
    @classmethod
    def normalize_money(cls, value: Decimal) -> Decimal:
        return money(value)


class Violation(FrozenModel):
    code: str
    severity: Severity
    message: str
    field: str | None = None
    actual: str | None = None
    limit: str | None = None


class CostEstimate(FrozenModel):
    expected_usd: Decimal
    worst_case_usd: Decimal
    per_step_usd: tuple[Decimal | None, ...]
    unpriced_models: tuple[str, ...]


class Decision(FrozenModel):
    enforcement_point: EnforcementPoint
    outcome: Severity
    violations: tuple[Violation, ...] = ()
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    estimated_cost_usd: Decimal = ZERO
    saved_cost_usd: Decimal | None = None


StoredViolation = Violation
StoredDecision = Decision


class JobRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    tenant_id: str
    status: str
    estimated_cost_usd: Decimal
    reserved_cost_usd: Decimal
    actual_cost_usd: Decimal = ZERO
    policy_decisions: list[Decision] = Field(default_factory=list)
    error: str | None = None

    @field_validator(
        "estimated_cost_usd",
        "reserved_cost_usd",
        "actual_cost_usd",
    )
    @classmethod
    def normalize_job_money(cls, value: Decimal) -> Decimal:
        return money(value)
