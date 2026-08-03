# ARCHITECTURE

## Components

```
Next.js 16 / Vinext (TierHive public judge service)
  studio · ledger · verify · share
        │  HTTPS + SSE
        ▼
FastAPI + Genblaze (TierHive VPS, London)
  policy engine · pipeline registry · job registry · ledger query · verify
        │                                    │
        │ provider APIs                      │ S3 API
        ▼                                    ▼
OpenAI · Replicate fallback           Backblaze B2 (single bucket)
                                       assets · manifests · ledger · state
```

Two application deployables and one bucket. The model providers and TierHive ingress are
external dependencies, not Dara-owned application services.

## The architectural claim

**B2 is the entire persistence layer.** Not just media — job state, policy documents,
project records, and the analytics tables all live as objects in the same bucket. There
is no database.

This is a deliberate position, and it is worth stating plainly in the README because it
is exactly what a storage company wants demonstrated. The consequences:

- Durable state is external to the Python service. The process still owns ephemeral tasks,
  admission locks, rate limits, caches, and the embedded DuckDB connection. Kill it mid-run
  and the job record in B2 reflects the last committed state; startup reconciliation then
  fails orphaned work safely rather than replaying a paid call automatically.
- Deployment is two containers and a bucket. No migrations, no connection pools.
- The analytics story and the storage story are the same story: `ParquetSink` writes
  locally, Dara uploads immutable per-run Parquet objects to B2, and DuckDB queries them
  in place over the B2 S3 endpoint.

The honest tradeoff, which should also be stated: object storage has no transactions and
no atomic compare-and-swap, so concurrent writers to the same job record are
last-write-wins. Dara has one writer per job by construction. Document this rather than
hiding it — acknowledging a real limit reads better than pretending there isn't one.
Admission control also uses a per-tenant `asyncio.Lock`: pre-flight reserves the run's
worst-case cost before releasing the lock, and completion reconciles the reservation to
actual cost. This is correct for the documented single-instance deployment; a
multi-instance deployment would require an external coordinator or transactional
reservation service.

## Request flows

### Create a run

1. `POST /v1/runs` with a pipeline id, brief, project id, policy id.
2. Resolve project and policy from B2.
3. Build the pipeline spec — model selection, step list, fallback chains.
4. **Pre-flight policy evaluation.** Under the tenant admission lock, estimate cost from
   `ModelRegistry`, check the model allowlist, modality, duration, aspect ratio, step count,
   and daily spend including reservations. **No provider has been contacted at this
   point.**
5. On `BLOCK`, write a job record with status `blocked` plus its policy event, then return
   `409` with the `job_id`, estimate, and structured violations. Reserve no budget.
6. On allow, reserve the worst-case cost, write the job record to B2 with status `queued`,
   and return `202` with a job id and the SSE URL.
7. Execute asynchronously: for each step, evaluate `PRE_STEP` against accumulated actual
   cost, run the step through Genblaze with its fallback chain, evaluate `POST_STEP` for
   the QA gate, emit events.
8. On generation success: `ObjectStorageSink` uploads the unembedded source assets and
   manifest to B2. `ParquetSink` writes telemetry to a per-job local staging directory;
   Dara uploads those files to immutable B2 keys and removes the local staging files.
   The job record is updated to `succeeded`, with assets either pending approval or ready
   for automatic publish according to policy.
9. On publish: create a local candidate derivative, embed the manifest, and hash the final
   bytes as `published_sha256`. Evaluate `PRE_PUBLISH` against that prepared candidate
   (approval, successful re-extraction, and any required redaction) before uploading it
   under `published/`, writing both SHA index pointers, and marking the asset approved.
   Never overwrite the Genblaze-bound source bytes. On terminal job state, reconcile the
   worst-case reservation to known actual cost and preserve uncertainty for estimated or
   unknown provider charges.

### Verify a file

1. `POST /v1/verify` with the file. No auth.
2. Detect container type; extract the embedded manifest with the matching handler.
3. If a manifest is present: call `verify_hash()` for canonical integrity and `verify()`
   for declared source-hash coverage, then resolve its run and asset in B2. Compare the
   uploaded file's SHA-256 with the trusted `published_sha256`. Return `embedded` plus a
   verification status of
   `trusted-match`, `trusted-mismatch`, or `self-consistent`.
4. If absent: compute SHA-256 and fetch `index/sha/{sha}.json`. On hit, load the associated
   record and manifest and return `matched-by-hash`. On miss, return `unknown`.
5. Never reveal bucket internals in the response. Return lineage fields only.

### Query the ledger

1. `GET /v1/ledger/summary` or `/v1/ledger/query` with an allowlisted query id plus
   typed parameters.
2. DuckDB with `httpfs`, `s3_endpoint` set to the B2 endpoint, `s3_url_style='path'`.
3. `SELECT ... FROM read_parquet('s3://{bucket}/ledger/runs/**/*.parquet')` — read the
   immutable uploaded partitions in place, with no application download step.
4. Cache the connection across requests; DuckDB startup is not free.

**Never pass user-supplied SQL to DuckDB.** Query ids map to parameterised templates in
`ledger.py`. This is both a security requirement and something a judge reading the code
will notice you got right.

## Job execution

No Celery, no Redis. An in-process `asyncio` task registry with every state transition
written through to B2.

```
queued → running → (succeeded | failed | blocked | cancelled)
```

The job record holds the state machine, the step event log, accumulated cost, policy
decisions, and asset references. The SSE endpoint tails the in-memory event buffer and
falls back to polling the B2 record if the client reconnects to a different process.

Single-instance deployment is assumed and is fine at this scale. If the process dies
mid-run, the record shows `running` with a stale heartbeat; a reconciler on startup marks
those `failed` with reason `orphaned`. Implement the reconciler — it is ten lines and it
is the difference between "demo" and "production readiness."

## Live-first product boundary

The root route opens `/studio`, where no run is preloaded. The public product overview
remains available at `/about`. Studio requires active project and policy data, shows the
live model-registry reservation, and requires two explicit confirmation clicks before a
provider call. Runs, Assets, Policies, and Ledger expose only active API/B2 records and
show a clear unavailable state instead of replacing them with local evidence.

Deterministic seeds remain in `api/seeds/` for repeatable automated coverage of policy
blocks, QA revision, provider fallback, and every pipeline. They are not imported by the
public Studio, Runs, Assets, Policies, or Ledger screens.

## Deployment

| Concern | Choice |
|---|---|
| Frontend | TierHive VPS, London, private-subnet Node service behind regional HAProxy |
| API | TierHive VPS, London, single instance, 2 vCPU / 3GB RAM |
| Region rationale | User-selected existing VPS provider; measured rather than represented as US-East |
| HTTPS | `usedara.xyz` → Vercel DNS → TierHive London HAProxy → private web listener |
| Persistence | Backblaze B2, `us-east-005` |
| Secrets | Root-readable service environment only. Never in the repo or browser bundle |
| Browser boundary | The server-side proxy holds the API token; the browser never receives it |
| Rate limits | Per-IP on `/v1/verify`; pseudonymous quotas on mutations; independent global daily cap on live generation |
| Health | `GET /healthz` reports B2 configuration and SDK/provider readiness |

The web boundary derives a pseudonymous actor from TierHive's forwarded client address
and never sends the raw address to the API or B2. The daily cap survives a process
restart: startup rebuilds settled spend from today's B2-backed live-run records and
charges the full reservation for any failed run
that reached provider execution without a known settled cost.

Measured deployment and latency evidence, including the explicitly documented quick-
tunnel lifecycle limit, lives in `docs/DEPLOYMENT.md`.

## Failure modes and responses

| Failure | Response |
|---|---|
| Provider returns `MODEL_ERROR` | Genblaze `fallback_models` retries the next model in the chain; the failover is recorded as a step event and shown in the UI |
| Every model in a chain fails | Job → `failed`, structured error; every attempt remains in the ledger with known, estimated, or unknown cost because providers may charge for failed work |
| Provider hangs | Per-step timeout from the pipeline spec; treated as a model error and failed over |
| B2 unreachable or capped | Mutating routes and hash-only verify return `503`; embedded verify may return `self-consistent` with `storage_status=unavailable`, never a trusted result. Failed ledger initialization and query execution enter configurable retry cooldowns so public polling cannot multiply B2 transactions. |
| DuckDB cold start slow | Connection cached at module scope; dashboard cache is invalidated by every accounting write |
| Judge exhausts credits | Live generation is blocked by the spend-cap policy; existing B2-backed read surfaces remain functional |
| Process restart mid-run | Startup reconciler marks orphaned runs `failed`; the ledger stays consistent |
| User cancels after provider work starts | The task is stopped best-effort; the full reservation remains conservatively accounted because upstream spend may already have occurred |

## Security notes

- Provider keys and B2 credentials exist only in the API process environment.
- The frontend receives public URLs or short-lived presigned URLs minted at read time,
  never B2 credentials. Presigned URLs are never persisted in manifests or job records.
- Verify is public but rate-limited and returns no bucket paths.
- Share tokens are opaque, random, and map to a redacted view; they never expose the
  underlying run id.
- Redacted shares serve token-scoped derivatives with their own `shared_sha256`; they
  never reuse a published file whose embedded manifest contains unredacted fields.
- Uploads to verify are size-capped and streamed, never buffered whole into memory.
