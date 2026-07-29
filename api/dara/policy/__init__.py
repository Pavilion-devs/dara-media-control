from __future__ import annotations

from .engine import PolicyEngine, ProviderCall, ReservationBook
from .estimator import PriceSource, estimate_run_cost
from .models import (
    CostEstimate,
    Decision,
    EnforcementPoint,
    JobRecord,
    PlannedStep,
    Policy,
    Price,
    RunPlan,
    Severity,
    StoredDecision,
    StoredViolation,
    Violation,
    ZERO,
    money,
)
from .repository import (
    B2JobStore,
    B2PolicyStore,
    JobStore,
    MemoryJobStore,
    MemoryPolicyStore,
    PolicyStore,
    job_storage_key,
    policy_storage_key,
)


def job_to_json(job: JobRecord) -> dict[str, object]:
    return job.model_dump(mode="json")


__all__ = [
    "B2JobStore",
    "B2PolicyStore",
    "CostEstimate",
    "Decision",
    "EnforcementPoint",
    "JobRecord",
    "JobStore",
    "MemoryJobStore",
    "MemoryPolicyStore",
    "PlannedStep",
    "Policy",
    "PolicyEngine",
    "PolicyStore",
    "Price",
    "PriceSource",
    "ProviderCall",
    "ReservationBook",
    "RunPlan",
    "Severity",
    "StoredDecision",
    "StoredViolation",
    "Violation",
    "ZERO",
    "estimate_run_cost",
    "job_storage_key",
    "job_to_json",
    "money",
    "policy_storage_key",
]
