# Dara

Dara is the control plane for AI-generated media: governed pipelines, verifiable
provenance, and an honest spend ledger built on Genblaze and Backblaze B2.

**Live app:** https://dara-media-control.asaborodaniel.chatgpt.site

## What works now

- Private Studio with an explicit **Live OpenAI** mode, authenticated server-side so
  the workspace token and provider key never reach the browser
- Asynchronous `gpt-image-2` still generation with its verified dated snapshot fallback,
  durable B2 job events, authenticated SSE streaming, polling fallback, and a signed
  result preview
- Structured `gpt-4.1-mini` brief expansion before generation, with validated JSON,
  policy-priced execution, an original-brief fallback, and exact prompt reuse on
  regeneration
- A four-step motion pipeline: `gpt-image-2` keyframe → Sora image-to-video →
  OpenAI narration → Genblaze `FFmpegCompositor`, with real video/audio fan-in,
  declared fallback routes, and a verified composite MP4 regression
- Bounded parallel voice packs through Genblaze `abatch_run()`, with strict
  OpenAI voice validation, `tts-1` → `tts-1-hd` fallback, ordered variant
  metadata, and a verified manifest for every narration
- Authenticated creation of opaque, expiring client shares backed by separate
  token-scoped B2 objects, exact shared-file hashes, and Genblaze `EmbedPolicy`
  pointer redaction that exposes no prompt, params, job id, or run id
- A live public `/share/{token}` disclosure page that rechecks served bytes and
  shows only allowed provenance fields, the whole-file shared hash, redaction
  notice, and Dara's explicit trust boundary
- A reproducible 13-run demo corpus spanning still, motion, voice, regeneration,
  two policy blocks, and a QA revision. Every entry distinguishes production
  proof from deterministic fixture, and demo mode makes no provider call
- Default zero-spend replay with the original 61-second event clock accelerated
  for presentation; live OpenAI generation remains behind an explicit
  spend-labelled control
- Per-client verification throttling behind the Cloudflare tunnel, plus a
  per-tenant daily live-spend cap with atomic admission, worst-case reservation,
  and B2-backed restart hydration that fails closed on uncertain provider spend
- A real Genblaze `AgentLoop` with structured `gpt-4.1-mini` vision scoring,
  bounded prompt revision, parent-run lineage, and publish-only-after-QA behavior
- A persisted version tree for every QA attempt, including rejected and failed runs,
  with native Genblaze `parent_run_id` links rather than reconstructed UI-only history
- Manifest-based regeneration that re-applies policy, links both Dara jobs and
  Genblaze runs, then compares the original and regenerated assets side by side
- A live regeneration proof whose eight canonical conditions matched, whose native
  lineage verified, and whose regenerated asset passed visual QA at 0.95
- Typed policy enforcement at pre-flight, before each provider step, after visual QA,
  and after local manifest embedding but before B2 publication
- Exact-decimal reservations, a $1 standard daily cap, and a guaranteed zero-spend
  block before any provider call
- Authenticated B2-backed policy create, list, read, update, and simulation endpoints
  with permissive, standard, and locked-down policies seeded durably
- Durable policy decisions embedded in each live run record and rendered in Studio
  with their enforcement point, outcome, reservation, and human-readable violations
- Honest replay of the recorded OpenAI → Genblaze → B2 proof; it is clearly labelled
  and makes no provider call
- Ledger view grounded in the recorded OpenAI run and durable zero-spend policy proof
- Public verification UI with a whole-file SHA-256 signature and lineage
- Three real `gpt-image-2` → Genblaze → Backblaze B2 generation proofs, including
  an authenticated vision-QA run that passed at 0.90 and recorded $0.015 estimated spend
- Manifest-embedded published derivative with separate source and published hashes
- Trusted-match and one-byte tamper detection through the public verification API
- B2-backed policy and live-run records persisted on every state transition
- Startup reconciliation that fails orphaned nonterminal jobs safely, releases their
  persisted reservations, and records a recovery event instead of retrying spend
- Genblaze `ParquetSink` telemetry staged per job, uploaded as immutable B2
  `runs`/`steps`/`assets` month partitions, then removed with the temporary workspace
- DuckDB 1.5.5 querying immutable accounting Parquet directly through B2's S3 API,
  with fixed query ids for model, project, month, QA, waste, and policy savings
- Live authenticated Ledger screen with total spend, prevented spend, cost per approved
  asset, waste ratio, and model/project/month tables
- Structured `409 POLICY_BLOCKED` responses with persisted zero-spend decisions
- Asset detail with separate source and published hashes
- Redacted client disclosure view
- Exact-decimal policy engine with atomic per-tenant budget reservations
- No-key Genblaze pipeline proof that emits and verifies a provenance manifest

## Repository

```text
app/          Dara web application
api/dara/     FastAPI and policy execution foundation
api/tests/    Zero-network policy and Genblaze spike tests
docs/         Product, architecture, pipeline, provider, and submission specs
```

## Run the web app

Requires Node.js 22.13 or newer.

```bash
npm install
npm run dev
npm run build
```

## Run the API foundation

```bash
python3 -m venv api/.venv
api/.venv/bin/pip install -e api
api/.venv/bin/python -m unittest discover -s api/tests -v
api/.venv/bin/uvicorn dara.main:app --app-dir api --reload
```

The current policy tests prove that a blocked job is persisted, costs zero, and makes
zero provider calls. They also cover worst-case retry estimates, unpriced-model warnings,
successful settlement, and concurrent budget admission.

## Trust boundary

Dara provides tamper-evident accountability within an organisation that controls its
trusted storage, plus a good-faith disclosure record for clients. It does not claim
adversarial authenticity. See [docs/PRD.md](docs/PRD.md) and
[docs/SDK_SURFACE.md](docs/SDK_SURFACE.md) for the precise model.
