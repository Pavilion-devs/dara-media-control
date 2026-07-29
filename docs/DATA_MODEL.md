# DATA MODEL

Everything is an object in one B2 bucket. There is no database.

## Bucket layout

```
dara/
  runs/{tenant}/{yyyy-mm-dd}/{run_id}/
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
      policy_events/year={yyyy}/month={mm}/{job_id}.parquet
  state/
      jobs/{tenant}/{job_id}.json
      projects/{tenant}/{project_id}.json
      policies/{tenant}/{policy_id}.json
      shares/{token}.json
  share-assets/{token}/{asset_id}.{ext}          isolated source-byte copies
  share-assets/{token}/{asset_id}.{ext}.genblaze.json
                                                  redacted Genblaze pointer sidecars
  seeds/demo/{scenario_id}.json               committed demo replays
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
  "status": "succeeded",          // queued|running|succeeded|failed|blocked|cancelled
  "created_at": "...",
  "started_at": "...",
  "finished_at": "...",
  "heartbeat_at": "...",          // used by the orphan reconciler
  "brief": {
    "prompt": "hero shot of a ceramic bowl on linen, morning light",
    "modality": "image",
    "aspect_ratio": "16:9",
    "variants": 3
  },
  "estimated_cost_usd": "0.180000", // pre-flight, from ModelRegistry
  "reserved_cost_usd": "0.540000",  // worst case while queued/running; zero on terminal
  "actual_cost_usd": "0.210000",    // accumulated from step results
  "attempt_count": 2,
  "parent_job_id": null,
  "genblaze_run_id": "run_...",
  "manifest_uri": "b2://dara-media/manifests/run_....json",
  "policy_decisions": [ /* Decision objects, see POLICY_ENGINE.md */ ],
  "events": [ /* StepEvent objects, see below */ ],
  "assets": [ /* AssetRef objects, see below */ ],
  "error": null
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
  // step.queued | step.started | step.progress | step.failover |
  // step.succeeded | step.failed | qa.scored | qa.revised |
  // policy.evaluated | policy.blocked | run.succeeded | run.failed
  "step_index": 1,
  "provider": "nvidia",
  "model": "flux.1-dev",
  "message": "primary model unavailable, falling back",
  "data": { "from_model": "sd3.5-large", "error_code": "MODEL_ERROR" }
}
```

Emit `step.failover` prominently. Visible graceful degradation is one of the strongest
production-readiness signals available and it costs nothing extra to surface.

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

`ParquetSink` produces `runs`, `steps`, and `assets` in a per-job local staging
directory. It does not upload those files to B2. After the sink closes successfully,
Dara uploads each table as its own immutable object at the partitioned keys above.
Dara writes a fourth table, `policy_events`, because policy decisions are Dara's concept
and not Genblaze's — and because "we blocked N runs and saved $X" is the single best
number in the demo.

### policy_events

| column | type | notes |
|---|---|---|
| `event_id` | VARCHAR | |
| `at` | TIMESTAMP | |
| `tenant_id` | VARCHAR | |
| `project_id` | VARCHAR | |
| `job_id` | VARCHAR | |
| `policy_id` | VARCHAR | |
| `enforcement_point` | VARCHAR | `pre_flight`/`pre_step`/`post_step`/`pre_publish` |
| `outcome` | VARCHAR | `allow`/`warn`/`block` |
| `violation_codes` | VARCHAR[] | |
| `estimated_cost_usd` | DECIMAL(18,6) | what the run would have cost |
| `saved_cost_usd` | DECIMAL(18,6) | non-zero only on `block` |

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
