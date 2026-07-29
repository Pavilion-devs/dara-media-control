# Dara

**The control plane for AI-generated media.** Governed pipelines, verifiable provenance,
and a queryable spend ledger — built on [Genblaze](https://github.com/backblaze-labs/genblaze)
and Backblaze B2.

> Built for the Backblaze Generative Media Hackathon.
> **Live app:** https://diamonds-jessica-accidents-icq.trycloudflare.com · **Demo video:** `TODO` · **Test account:** Not required

---

## The problem

A creative team generating across five model providers accumulates thousands of assets a
month with no system of record. Ask what any single asset cost, which model made it,
whether it can be reproduced, or what can be disclosed to the client, and the answer is a
Slack search. The generation tooling is excellent. The operational layer under it does not
exist.

Dara is that layer.

## What it does

**Verify.** Drop any generated file into a public page. Dara extracts the embedded
provenance manifest, verifies it, and compares the uploaded bytes with the trusted
`published_sha256` recorded in B2 when that exact embedded deliverable was published.
It renders the full lineage — provider, model, prompt, parameters, cost, and parent runs.
No account required.

**Govern.** Policies are declarative documents attached to a project: allowed models,
spend limits, quality thresholds, retention, redaction. They are enforced at four points,
the first of which runs **before any provider is contacted** — cost is estimated from the
Genblaze `ModelRegistry` and a run that would breach budget is rejected at zero cost.

**Generate.** Multi-step Genblaze pipelines with provider fallback chains and an agentic
QA loop that scores each output against a rubric and revises the prompt until it passes.
Every attempt, including failures, is preserved and linked by `parent_run_id`.

**Account.** `ParquetSink` writes run telemetry to per-job local staging; Dara uploads
the completed files to immutable, partitioned B2 keys. DuckDB queries that Parquet in
place over the B2 S3 endpoint. The ledger reports spend by model and project, and the
number nobody tracks: **cost per approved asset, including failed and discarded
attempts.**

## How this maps to the judging criteria

| Criterion | Where to look | What it does |
|---|---|---|
| **Real-world utility** | `docs/PRD.md` | A named buyer with five concrete questions they currently cannot answer. Verify and ledger deliver value without any generation happening. |
| **Production readiness** | `api/dara/policy/`, `api/dara/jobs.py`, `api/dara/providers.py` | Policy enforced before spend; fallback chains on every generative step; orphaned-run reconciler; typed error model; rate limits and spend caps; a test asserting that a blocked run makes **zero** provider calls. |
| **B2 storage + data orchestration** | `api/dara/storage.py`, `api/dara/ledger.py`, `docs/DATA_MODEL.md` | One bucket is the entire persistence layer — source assets, published deliverables, manifests, job state, policies, projects, and analytics. Hierarchical keys aid navigation; content-addressed source and published keys provide dedupe and exact verification. Locally staged Parquet is uploaded as immutable partitions and queried in place by DuckDB. **There is no database.** |
| **Use of Genblaze** | `api/dara/pipelines/`, `api/dara/verify.py`, `api/dara/share.py` | Multi-step DAG execution, `input_from` fan-in, `fallback_models`, `AgentLoop`, `parent_run_id` lineage, `ObjectStorageSink` + `ParquetSink`, `EmbedPolicy` redaction, manifest embed/extract/verify, `ModelRegistry` pricing customisation, `astream()` streaming, replay-based regeneration, `LoggingTracer`. |

## Architecture

```
Next.js / Vinext (TierHive VPS)  ──HTTPS + SSE──▶  FastAPI + Genblaze (TierHive VPS)
                                                        │              │
                                               provider APIs       S3 API
                                                        ▼              ▼
                                         OpenAI · Replicate      Backblaze B2
                                         fallback                (single bucket)
```

Two deployables, one bucket, no other infrastructure. Full detail in
`docs/ARCHITECTURE.md`.

### Bucket layout

```
runs/{tenant}/{date}/{run_id}/     hierarchical — human-navigable, run-grouped
assets/{sha[:2]}/{sha[2:4]}/{sha}.ext  unembedded source — Genblaze-bound, deduped
published/{sha[:2]}/{sha[2:4]}/{sha}.ext embedded deliverables — exact client bytes
share-assets/{token}/{asset_id}.ext  token-scoped redacted derivatives
manifests/{run_id}.json            provenance records, retained longer than assets
index/sha/{sha}.json                extension-free lookup for either hash
ledger/{table}/year={yyyy}/month={mm}/{id}.parquet  queried in place by DuckDB
state/{jobs,projects,policies,shares}/               application state as objects
```

## Providers and models

See `docs/MODELS_USED.md`, generated from the live model registry.

## Setup

```bash
git clone https://github.com/Pavilion-devs/dara-media-control.git && cd dara
cp .env.example .env          # fill in B2 and provider keys

cd api && pip install -e . && uvicorn dara.main:app --reload
cd web && npm install && npm run dev
```

Demo mode is the default and requires no provider keys — it replays committed runs from
`api/seeds/`. Provider keys are only needed for live generation.

## Honest limitations

Stated plainly because the trust model matters more than the marketing.

- **The manifest is tamper-evident, not tamper-proof.** It is authoritative within an
  organisation that controls its own B2 bucket, and a good-faith disclosure artifact
  outside it. It is not an adversarial authenticity proof. Pairing with C2PA or an
  external signer is the correct next step and is not implemented here.
- **Embedded bytes have a separate trusted hash.** Genblaze's `asset.sha256` covers the
  source bytes before embedding, because embedding changes the file. Dara records
  `published_sha256` for the final embedded deliverable and uses that trusted B2 value
  for whole-file verification. An internally valid manifest with no Dara record is
  reported as self-consistent, not verified.
- **Regeneration reproduces conditions, not bytes.** Most media models are not
  deterministic. Dara reconstructs the exact parameters; it does not promise an identical
  file, and the UI says so.
- **Object storage has no transactions.** Concurrent writers to one job record are
  last-write-wins. Dara has one writer per job by construction, which is sufficient here
  and would need revisiting at scale.
- **No user accounts.** One demo workspace. Non-public API routes are protected by a
  server-side workspace token that never reaches the browser. `tenant_id` is threaded
  through the data model so full multi-tenant identity and authorisation are a deployment
  concern rather than a rewrite.

## Feedback on Genblaze

Issues filed during this build: `TODO — links`. Notes in `docs/SDK_FEEDBACK.md`.

## License

MIT
