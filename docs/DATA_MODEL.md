# DATA MODEL

Everything is an object in one B2 bucket. There is no database.

## Bucket layout

```
dara/
  live/runs/{tenant}/{yyyy-mm-dd}/{run_id}/
      manifest.json                     Genblaze manifest, HIERARCHICAL sink
      assets/{asset_id}.{ext}            unembedded source bytes
  assets/{sha[0:2]}/{sha[2:4]}/{sha}.{ext}    source bytes, content-addressable
  published/{sha[0:2]}/{sha[2:4]}/{sha}.{ext} final embedded deliverables
  manifests/{run_id}.json                     flat lookup by run
  index/sha/{sha}.json                        any source/published sha -> pointer
  ledger/
      runs/year={yyyy}/month={mm}/{run_id}.parquet
      steps/year={yyyy}/month={mm}/{run_id}.parquet
      assets/year={yyyy}/month={mm}/{run_id}.parquet
      accounting/year={yyyy}/month={mm}/{job_or_attempt_id}.parquet
  state/
      jobs/{tenant}/{job_id}.json
      live-runs/{tenant}/{job_id}.json
      assets/{asset_id}.json
      projects/{tenant}/{project_id}.json
      policies/{tenant}/{policy_id}.json
      shares/{token}.json
  share-assets/{token}/{asset_id}.{ext}          isolated source-byte copies
  share-assets/{token}/{asset_id}.{ext}.genblaze.json
                                                  redacted Genblaze pointer sidecars
  seeds/demo/{scenario_id}.json               deterministic test evidence only
```

One fresh `ObjectStorageSink` writes the hierarchical run layout for each pipeline run.
After it closes, Dara uses a server-side backend copy to materialise the same source bytes
under the content-addressable key. This avoids re-running a completed result through a
second single-use sink while preserving both layouts:

- `HIERARCHICAL` under `runs/` gives a human-navigable, run-grouped view — this is what
  you show a judge browsing the bucket.
- `CONTENT_ADDRESSABLE` under `assets/` gives deduplication for the unembedded bytes that
  Genblaze commits to in `asset.sha256`.
- `published/` contains the exact embedded deliverables sent to clients. Embedding changes
  the bytes, so these objects have a distinct `published_sha256`.

`index/sha/` is Dara's own addition: a tiny pointer object so verify can resolve either
a source hash or a published-file hash without knowing the extension or listing. Write
one pointer for `source_sha256` when the source is stored and another for
`published_sha256` when the embedded derivative is published.

Genblaze's manifest commits to the source hash before embedding. Do not compare the
whole-file hash of an embedded upload directly with that value: it will differ even for
an untampered file. For embedded uploads, use the manifest's identifiers to load the
trusted AssetRef and compare with `published_sha256`.

## Object schemas

All stored objects are Pydantic v2 models serialised to JSON. Every one carries
`schema_version` — bump it rather than mutating in place.

### Project

```jsonc
{
  "schema_version": 1,
  "project_id": "prj_northwind_q3",
  "tenant_id": "demo",
  "name": "Northwind — Q3 campaign",
  "client": "Northwind Foods",
  "policy_id": "pol_standard",
  "created_at": "2026-07-28T09:00:00Z",
  "tags": ["campaign", "food"]
}
```

### Policy

Full field reference in `POLICY_ENGINE.md`. Stored at `state/policies/{tenant}/{id}.json`.

### Job

The central record. One writer per job.

```jsonc
{
  "schema_version": 1,
  "job_id": "job_01J8Z...",
  "tenant_id": "demo",
  "project_id": "prj_northwind_q3",
  "pipeline_id": "still-campaign",
  "policy_id": "pol_standard",
  "status": "succeeded",          // queued|running|publishing|succeeded|failed|blocked|cancelled
  "created_at": "...",
  "updated_at": "...",
  "prompt": "hero shot of a ceramic bowl on linen, morning light",
  "aspect_ratio": "1:1",
  "variants": 1,
  "expected_cost_usd": "0.030000", // pre-flight, from ModelRegistry
  "worst_case_cost_usd": "0.090000", // held while queued/running
  "actual_cost_usd": "0.055000",   // known or conservative estimated terminal amount
  "cost_basis": "estimated",
  "parent_job_id": null,
  "genblaze_run_id": "run_...",
  "manifest_hash": "...",
  "source_sha256": "...",
  "published_sha256": "...",
  "published_content_address": "dara/published/ab/cd/....png",
  "qa_status": "passed",
  "qa_score": 0.91,
  "qa_attempts": 2,
  "policy_decisions": [ /* Decision objects, see POLICY_ENGINE.md */ ],
  "events": [ /* StepEvent objects, see below */ ],
  "attempts": [ /* RunAttempt objects, see below */ ],
  "asset_id": "ast_...",
  "error_code": null,
  "error_message": null
}
```

### StepEvent

Appended in order. This is the SSE payload shape and the audit trail — same object
serves both, deliberately.

```jsonc
{
  "seq": 7,
  "at": "2026-07-28T09:00:14.221Z",
  "type": "step.failover",
  "provider": "openai",
  "model": "gpt-image-2-2026-04-21",
  "message": "Primary model unavailable; the recorded fallback recovered."
}
```

Emit `step.failover` prominently. Visible graceful degradation is one of the strongest
production-readiness signals available and it costs nothing extra to surface.

### RunAttempt

Every evaluated candidate is retained independently so rejected paid work contributes
to waste and cost-per-approved-asset calculations.

```jsonc
{
  "attempt": 2,
  "genblaze_run_id": "run_...",
  "parent_run_id": "run_parent...",
  "status": "approved",            // running|rejected|approved|failed
  "prompt": "expanded production prompt",
  "provider": "replicate",
  "model": "black-forest-labs/flux-1.1-pro",
  "qa_score": 0.91,
  "asset_id": "ast_...",
  "cost_usd": "0.025000",
  "cost_basis": "estimated",
  "created_at": "..."
}
```

### AssetRef

```jsonc
{
  "asset_id": "ast_...",
  "source_sha256": "9f2c...",
  "published_sha256": "b741...",
  "mime_type": "image/png",
  "bytes": 1841222,
  "source_content_address": "assets/9f/2c/9f2c....png",
  "published_content_address": "published/b7/41/b741....png",
  "modality": "image",
  "duration_s": null,
  "manifest_embedded": true,
  "redacted": false,
  "qa_score": 0.86,
  "approved": true,
  "cost_usd": "0.070000",
  "cost_basis": "known"
}
```

Persist storage keys, not presigned URLs. API responses mint a short-lived download URL
from `published_content_address` (or the source key for an internal view) at read time.
For a deliberately public bucket or CDN, the API may instead return the configured
public URL. A presigned URL must never be written into an AssetRef, manifest, or ledger.
`cost_basis` is `known`, `estimated`, or `unknown`; failed and timed-out attempts are
never silently assigned zero cost.

### Share

```jsonc
{
  "schema_version": 1,
  "token": "shr_7Kq...",           // opaque, 32 bytes of randomness, url-safe
  "job_id": "job_...",
  "assets": [
    {
      "asset_id": "ast_...",
      "shared_sha256": "c821...",
      "storage_key": "share-assets/shr_7Kq.../ast_....png"
    }
  ],
  "redaction": { "strip_prompt": true, "strip_params": true },
  "created_at": "...",
  "expires_at": "2026-09-01T00:00:00Z",
  "view_count": 0
}
```

The token never encodes the job id. Look it up.
Never serve the ordinary published derivative on a redacted share: its embedded manifest
may contain the prompt and parameters. Copy the trusted source bytes into a separate
token-scoped object, hash it as `shared_sha256`, and store the Genblaze `EmbedPolicy`
pointer sidecar beside it. The pointer contains only schema version, the trusted
canonical manifest hash, and an opaque share URI. This is the installed SDK's
integrity-safe redaction contract; a full redacted manifest is intentionally rejected
because its old canonical hash could not verify changed content. Add the exact shared
hash to `index/sha/`. The share route compares served bytes against this token-scoped
record, and presigned URLs are minted only when the share is read.

## Ledger tables

`ParquetSink` produces Genblaze `runs`, `steps`, and `assets` tables in a per-job local
staging directory. Dara uploads each completed table to the partitioned keys above after
the sink closes. Dara also writes its own `accounting` table: one immutable row per paid
attempt when attempt-level cost exists, otherwise one terminal run row. The record
includes `source_job_id`, provider/model, `primary_model`, `failover_count`, status,
cost and basis, saved cost, approval contribution, QA, asset id, and timestamp. For a
multi-step delivered asset, every contributing billable step is approved for waste
purposes but only the final row carries `asset_id`; summary denominators count distinct
approved asset IDs, never step rows. Blocked work records zero cost plus
`saved_cost_usd`; cancelled in-flight work records the conservative full reservation
when upstream spend is uncertain.

Partition all ledger writes by year and month in the object path so DuckDB can prune.
Use one immutable file per run/job rather than appending to or overwriting a shared
monthly object:
`ledger/runs/year=2026/month=07/run_01J....parquet`.

## Canonical queries

These back the ledger screen. Implement each as a named, parameterised template in
`ledger.py` — never as user-supplied SQL.

| id | Answers |
|---|---|
| `spend_by_model` | Total and mean cost per model over a date range |
| `spend_by_project` | Cost per project, with asset counts |
| `spend_by_month` | Monthly trend across all projects |
| `cost_per_approved_asset` | Total run cost ÷ approved assets — the number that includes waste |
| `waste_ratio` | Share of spend on assets that never got approved |
| `failover_rate` | Fallback activations per model, and which primaries are unreliable |
| `qa_pass_rate` | First-attempt pass rate by model |
| `policy_savings` | Spend prevented by blocked runs |

`cost_per_approved_asset`, `waste_ratio`, and `policy_savings` are the three nobody else
will compute. Lead the ledger screen with them.

## Identifiers

- Prefixed and sortable: `job_`, `prj_`, `pol_`, `ast_`, `shr_`, `run_`.
- Use ULIDs, not UUID4 — lexicographic ordering means B2 list operations come back in
  time order for free.
- Dara APIs and UI routes use `job_id`. Genblaze issues its own `run_id`; store it as
  `genblaze_run_id` and do not conflate it with the Dara job id.
- Job-to-job lineage uses `parent_job_id`; Genblaze manifest lineage continues to use
  `parent_run_id`.

## Money

- Use `Decimal` in Python and decimal strings at the JSON boundary, quantised to six
  fractional digits. Never add policy or billing values with binary floating point.
- Analytics tables may use `DECIMAL(18,6)`. Cast to `DOUBLE` only for visualisation where
  exact arithmetic is no longer being performed.
