# Dara

Dara is the control plane for AI-generated media: governed pipelines, verifiable
provenance, and an honest spend ledger built on Genblaze and Backblaze B2.

**Live app:** https://dara-media-control.asaborodaniel.chatgpt.site

## What works now

- Populated Studio with live cost estimation and a guaranteed pre-spend policy block
- Visible fallback and agentic QA revision events
- Ledger with cost per approved asset, prevented spend, and waste ratio
- Public verification UI with a whole-file SHA-256 signature and lineage
- Real `gpt-image-2` → Genblaze → Backblaze B2 generation proof
- Manifest-embedded published derivative with separate source and published hashes
- Trusted-match and one-byte tamper detection through the public verification API
- B2-backed job state that survives service reconstruction
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
