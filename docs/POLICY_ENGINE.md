# POLICY ENGINE

The differentiator. Most hackathon entries generate media; this one refuses to generate
media that violates a declared constraint, and it refuses **before spending money**.

## Principle

A policy is a declarative document attached to a project. The engine evaluates it at four
points in a run's lifecycle. The first evaluation happens after the pipeline is planned
but before any provider is contacted, using cost estimates derived from the Genblaze
`ModelRegistry`. A run that would breach budget never becomes an API call.

Everything the engine decides is recorded. Governance you cannot audit is decoration.

## Policy document

```jsonc
{
  "schema_version": 1,
  "policy_id": "pol_standard",
  "tenant_id": "demo",
  "name": "Standard client work",
  "description": "Default guardrails for billable client projects.",

  "providers": {
    "allowed": ["openai", "google", "replicate", "elevenlabs"],
    "denied": []
  },
  "models": {
    "allowed": ["*"],
    "denied": ["sora-2", "veo-3"],
    "note": "Premium video models require an explicit exception policy."
  },

  "budget": {
    "max_cost_usd_per_step": "0.500000",
    "max_cost_usd_per_run": "2.000000",
    "max_cost_usd_per_day": "10.000000",
    "estimate_overrun_tolerance": "0.250000"
  },

  "shape": {
    "max_steps": 6,
    "max_attempts": 3,
    "allowed_modalities": ["image", "video", "audio"],
    "allowed_aspect_ratios": ["1:1", "16:9", "9:16"],
    "max_duration_s": 10,
    "max_variants": 4
  },

  "quality": {
    "min_qa_score": 0.75,
    "require_qa": true,
    "block_on_qa_failure": false
  },

  "publish": {
    "require_approval": true,
    "embed_manifest": true,
    "redact_prompt_on_share": true,
    "strip_params_on_share": true
  },

  "retention": {
    "asset_days": 365,
    "manifest_days": 2555
  }
}
```

Manifests outlive assets deliberately — the record of what was made is cheap to keep and
is the thing an audit actually needs.

## Enforcement points

### 1. `PRE_FLIGHT` — before any provider call

The important one. Inputs: the planned pipeline spec, the resolved policy, today's
settled tenant spend, and outstanding worst-case reservations.

Checks:

| Check | Code | Severity |
|---|---|---|
| Every provider is on the allowlist | `PROVIDER_NOT_ALLOWED` | block |
| No model is on the denylist | `MODEL_DENIED` | block |
| Step count within `max_steps` | `TOO_MANY_STEPS` | block |
| Modality permitted | `MODALITY_NOT_ALLOWED` | block |
| Aspect ratio permitted | `ASPECT_RATIO_NOT_ALLOWED` | block |
| Duration within `max_duration_s` | `DURATION_EXCEEDED` | block |
| Variant count within `max_variants` | `TOO_MANY_VARIANTS` | block |
| Estimated run cost ≤ `max_cost_usd_per_run` | `RUN_BUDGET_EXCEEDED` | block |
| Estimated step cost ≤ `max_cost_usd_per_step` | `STEP_BUDGET_EXCEEDED` | block |
| Today's spend + estimate ≤ `max_cost_usd_per_day` | `DAILY_BUDGET_EXCEEDED` | block |
| Any model has no registry pricing | `UNPRICED_MODEL` | warn |

`UNPRICED_MODEL` is a warning, not a block. Genblaze passes unknown models through with
`cost_usd=None` by design so new models work without an SDK release. Blocking on it
would punish the SDK's best feature. Warn, surface it in the UI, and record it.

For live execution, evaluate and reserve atomically within a per-tenant `asyncio.Lock`.
Reserve `worst_case_usd` before releasing the lock; on completion, replace the reservation
with actual cost and set the job's `reserved_cost_usd` to zero. Store the reservation on
the B2 job record so startup reconciliation can recover or release it. This prevents two
concurrent runs on the documented single API instance
from both passing against the same remaining daily budget. Demo simulations evaluate
without reserving. A future multi-instance deployment needs an external coordinator or
transactional reservation service.

### 2. `PRE_STEP` — before each step executes

Inputs: accumulated **actual** cost so far, the step about to run.

| Check | Code | Severity |
|---|---|---|
| Actual + this step's estimate ≤ run budget | `RUN_BUDGET_EXCEEDED` | block |
| Actual exceeds estimate by more than `estimate_overrun_tolerance` | `ESTIMATE_DRIFT` | warn |

`ESTIMATE_DRIFT` is worth implementing for its own sake: it tells you the registry
pricing is wrong, which is exactly the kind of concrete finding that makes a good
Genblaze issue.

### 3. `POST_STEP` — after a step produces output

| Check | Code | Severity |
|---|---|---|
| QA score ≥ `min_qa_score` | `QA_BELOW_THRESHOLD` | warn or block per `block_on_qa_failure` |
| Attempts within `max_attempts` | `MAX_ATTEMPTS_REACHED` | block |

A `QA_BELOW_THRESHOLD` warning is what triggers the revision loop. Only when attempts are
exhausted does the run finish unapproved.

### 4. `PRE_PUBLISH` — after preparing a local candidate, before external publish

| Check | Code | Severity |
|---|---|---|
| Approval present when `require_approval` | `APPROVAL_REQUIRED` | block |
| Manifest embedded when `embed_manifest` | `MANIFEST_NOT_EMBEDDED` | block |
| Redaction applied when sharing | `REDACTION_REQUIRED` | block |

Redaction uses Genblaze's `EmbedPolicy` pointer mode. The sidecar contains only schema
version, the trusted canonical manifest hash, and an opaque share URI; prompt and params
are never copied into the token-scoped object or returned publicly. Dara locally checks
that exact three-field shape and canonical-hash binding, then hashes the isolated shared
bytes before the policy gate allows upload. This follows the SDK's verifiable pointer
contract instead of fabricating a full redacted manifest whose old hash could not verify.

## Types

```python
class Severity(StrEnum):
    ALLOW = "allow"
    WARN  = "warn"
    BLOCK = "block"

class Violation(BaseModel):
    code: str
    severity: Severity
    message: str            # written for a human, not a logfile
    field: str | None       # dotted path into the policy, e.g. "budget.max_cost_usd_per_run"
    actual: Decimal | str | None
    limit: Decimal | str | None

class Decision(BaseModel):
    enforcement_point: Literal["pre_flight","pre_step","post_step","pre_publish"]
    outcome: Severity
    violations: list[Violation]
    evaluated_at: datetime
    estimated_cost_usd: Decimal | None
    saved_cost_usd: Decimal | None   # set on block: what the run would have cost
```

`saved_cost_usd` exists so the ledger can report total spend prevented. That aggregate is
the best single number in the demo — "this policy has blocked 4 runs and saved $37" is
concrete in a way that feature lists are not.

## Cost estimation

```python
def estimate_run_cost(spec: PipelineSpec, registry: ModelRegistry) -> CostEstimate:
    """
    Sum per-step estimates from ModelRegistry pricing before any call is made.

    Per-step:
      image → per_unit price × variants
      video → per_unit or per_second × duration × variants
      audio → per_second × duration, or per_character for TTS
      chat  → token estimate × rate (small; do not over-engineer)

    Multiply the whole estimate by max_attempts to get worst_case_usd — a QA loop that
    retries three times costs three times as much, and a budget check that ignores this
    is not a budget check.

    Returns CostEstimate(
        expected_usd, worst_case_usd, per_step=[...], unpriced_models=[...]
    )
    """
```

Check `worst_case_usd` against the run budget, not `expected_usd`. Show the user both.
Use `Decimal` for every estimate, limit, reservation, and actual-cost calculation;
policy documents and API responses serialise money as six-place decimal strings.

## Seeded policies

Ship three so the demo can switch between them live.

| id | Character | Purpose in the demo |
|---|---|---|
| `pol_permissive` | High budgets, all models, QA advisory | Shows the system out of the way |
| `pol_standard` | Real guardrails, premium video denied, approval required | The default |
| `pol_locked` | $0.10/run, images only, 1:1 only, QA blocking | Guarantees a visible block on camera |

`pol_locked` exists for the demo. Switch to it, submit the same brief that just succeeded,
and watch it get rejected with a clear reason and zero spend. That is the twenty seconds
that sells production readiness.

## Testing

Unit tests, no network:

- Each violation code fires on a crafted input and does not fire on a valid one.
- A blocked run makes zero provider calls — assert with a mock that records invocations.
- A blocked run is persisted with status `blocked` and a policy ledger event, but creates
  no spend reservation.
- `worst_case_usd` correctly multiplies by `max_attempts`.
- `UNPRICED_MODEL` warns and does not block.
- Daily budget accumulates across runs within a tenant and resets at UTC midnight.
- Two concurrent admissions cannot both spend the same remaining daily budget; test the
  per-tenant reservation lock and completion reconciliation.
- Policy resolution: project policy overrides tenant default; missing policy falls back
  to `pol_standard` and records that it did.

The "blocked run makes zero provider calls" test is the one to write first and mention in
the README. It is the mechanical proof of the product's central claim.
