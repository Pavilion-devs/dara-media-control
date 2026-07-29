# Dara

Dara is the control plane for AI-generated media: governed pipelines, verifiable
provenance, and an honest spend ledger built on Genblaze and Backblaze B2.

**Live app:** https://dara-media-control.asaborodaniel.chatgpt.site

## What works now

- Private Studio with an explicit **Live OpenAI** mode, authenticated server-side so
  the workspace token and provider key never reach the browser
- Asynchronous `gpt-image-2` still generation with a `gpt-image-1-mini` fallback,
  durable B2 job events, authenticated SSE streaming, polling fallback, and a signed
  result preview
- A real Genblaze `AgentLoop` with structured `gpt-4.1-mini` vision scoring,
  bounded prompt revision, parent-run lineage, and publish-only-after-QA behavior
- Pre-flight policy admission with exact-decimal reservations, a $1 standard daily
  cap, and a guaranteed zero-spend block before any provider call
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
