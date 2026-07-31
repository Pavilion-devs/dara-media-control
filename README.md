# Dara

**Dara is the control plane for AI-generated media: governed pipelines, verifiable
provenance, and an honest spend ledger built on Genblaze and Backblaze B2.**

[Live application](https://usedara.xyz) ·
[Deployment evidence](docs/DEPLOYMENT.md) ·
[Trust model](docs/PRD.md#the-trust-model)

> No test account is required. Dara is public end to end, including policy previews,
> live runs, regeneration, disclosure links, Verify, Assets, and the live Ledger.
> Paid generation remains protected by a disabled-by-default kill switch, anonymous
> action quotas, and the durable daily spend cap.

## The problem

A creative team generating thousands of assets across model providers has no durable
answer to basic operational questions: What did this asset cost, including discarded
attempts? Which exact model and parameters produced it? Can the same conditions be
reconstructed? Did policy approve it before money was spent? What provenance can be
shared without leaking the prompt library?

Dara makes those answers part of the media supply chain instead of leaving them in
spreadsheets, chat history, and provider dashboards.

## A 60-second tour

### 1. Generate under policy

![Dara Studio showing a deterministic QA revision, policy reserve, and linked event stream](docs/assets/tour-studio.jpg)

Replay is the default and creates no new provider spend. It opens on a verified
production OpenAI/B2 record with its original estimated cost visible; the committed
13-run corpus also includes clearly marked deterministic fixtures for still, motion,
voice, regeneration, policy blocks, and a QA fail-revise-pass path. Live generation is
a separate, spend-labelled action with two-step confirmation. The live B2 evidence
corpus contains 20 current client-project runs: 12 approved assets, three zero-cost
policy blocks, three paid QA rejections, two provider-diverse recoveries, production
voice, and a complete production motion package.

### 2. Verify the delivered bytes

![Dara Verify showing a trusted published-record match and whole-file SHA-256](docs/assets/tour-verify.jpg)

Dara extracts the Genblaze manifest and checks its canonical integrity, then compares the
uploaded file's whole-file SHA-256 with the trusted `published_sha256` stored in B2. A
valid foreign manifest is reported only as self-consistent; a changed trusted file fails
closed as a mismatch.

The browser computes SHA-256 locally before any upload, so the visitor can see the exact
digest of the bytes they hold before trusting Dara or the network. Normal-sized files are
then streamed for embedded-manifest inspection; oversized files can fall back to the
content-hash lookup without transmitting the file.

### 3. Account for every attempt

![Dara Ledger querying live accounting Parquet in Backblaze B2](docs/assets/tour-ledger.jpg)

The live ledger queries immutable accounting Parquet directly in B2 with DuckDB. Failed,
rejected, and policy-blocked work stays visible, so cost per approved asset includes the
work that did not ship.

## What Dara does

- **Verify:** public, no-provider-call file verification with embedded-manifest and
  content-addressed lookup paths.
- **Govern:** typed policies enforced pre-flight, before every provider step, after QA,
  and after embedding but before publication.
- **Generate:** Genblaze still, motion, voice-pack, and regeneration workflows with
  fallback chains, streaming events, structured prompt expansion, and agentic visual QA.
- **Account:** immutable per-run Parquet in B2, queried in place by DuckDB for spend,
  waste, savings, and cost per approved asset.
- **Disclose:** expiring, token-scoped client shares that expose limited provenance
  without leaking prompts, parameters, job IDs, or run IDs.

## Judging criteria

| Criterion | Where to look | Evidence |
|---|---|---|
| **Real-world utility** | [`docs/PRD.md`](docs/PRD.md), [Verify screen](<app/(public)/verify/verify-screen.tsx>), [Ledger screen](<app/(app)/ledger/ledger-screen.tsx>) | A named buyer and five concrete questions; verify and ledger remain useful without starting generation. |
| **Production readiness** | [`api/dara/policy/`](api/dara/policy/), [`api/dara/jobs.py`](api/dara/jobs.py), [`api/dara/main.py`](api/dara/main.py), [`api/tests/`](api/tests/) | Pre-spend policy blocks, atomic reservations, B2-backed restart recovery, anonymous action quotas, typed errors, fallback routes, and measured deployment evidence. Verify distinguishes trusted match, trusted mismatch, self-consistent, and unknown; SHA-256 is computed client-side before upload. |
| **B2 storage and data orchestration** | [`api/dara/storage.py`](api/dara/storage.py), [`api/dara/ledger.py`](api/dara/ledger.py), [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | One B2 bucket holds source assets, delivered derivatives, manifests, job/policy/share state, hash indexes, and immutable Parquet. There is no application database. |
| **Use of Genblaze** | [`api/dara/pipelines/`](api/dara/pipelines/), [`api/dara/verify.py`](api/dara/verify.py), [`api/dara/share.py`](api/dara/share.py) | Multi-step pipelines, `input_from` fan-in, `fallback_models`, `AgentLoop`, `parent_run_id`, `ObjectStorageSink`, `ParquetSink`, `EmbedPolicy`, manifest embed/extract/verify, `ModelRegistry`, `astream()`, `abatch_run()`, replay semantics, and `LoggingTracer`. |

## Architecture

```text
Next.js public judge server on TierHive
  Studio · Ledger · Verify · Share
            │ HTTPS + SSE
            ▼
FastAPI + Genblaze on TierHive, London
  policy · pipelines · jobs · ledger · verification
            │                         │
            │ OpenAI                  │ S3 API
            ▼                         ▼
  media + QA providers       Backblaze B2, us-east-005
                              the only datastore
```

The web server and Python API are separate always-on services on the same VPS. The API
binds only to loopback; the web server binds to the TierHive private subnet and is
exposed by TierHive's regional HAProxy at `https://usedara.xyz`. Provider and B2 secrets
never cross that server boundary. The API remains a single instance because admission
control and job execution use in-process locks. Durable state is in B2, so restart
reconciliation can fail orphaned work safely and rebuild the daily spend commitment. A
multi-instance API would require an external transactional coordinator.

### One bucket, distinct byte roles

```text
dara/live/runs/{tenant}/{date}/{run_id}/     Genblaze run grouping
dara/assets/{aa}/{bb}/{source_sha}.ext       immutable source bytes
dara/published/{aa}/{bb}/{published_sha}.ext exact delivered bytes
dara/share-assets/{token}/{asset_id}.ext     redacted client derivatives
dara/manifests/{run_id}.json                 provenance
dara/index/sha/{sha}.json                    source/published lookup
dara/ledger/{table}/year=YYYY/month=MM/*.parquet
dara/state/{jobs,live-runs,assets,policies,projects,shares}/
```

Genblaze's source hash and Dara's delivered-file hash are deliberately different.
Embedding changes a file, so Dara never overwrites the Genblaze-bound source and never
pretends those two hashes should match.

## Providers and models

OpenAI is Dara's primary AI provider. Replicate's official FLUX 1.1 Pro route is the
provider-diverse image fallback; both providers have completed production calls that
were persisted and verified in B2. Genblaze is the orchestration and provenance SDK,
not a provider. The inventory is generated from
[`api/dara/providers.py`](api/dara/providers.py):

| Provider | Model | Use | Evidence |
|---|---|---|---|
| OpenAI | `gpt-image-2` | Primary image generation | Production calls persisted and verified in B2 |
| OpenAI | `gpt-image-2-2026-04-21` | Same-provider image fallback | Configured and account-catalog verified |
| Replicate | `black-forest-labs/flux-1.1-pro` | Provider-diverse image fallback | Production call persisted and verified in B2 · 5.518s · $0.040000 |
| OpenAI | `gpt-4.1-mini` | Prompt expansion and vision QA | Production calls recorded |
| OpenAI | `sora-2` → `sora-2-pro` | Motion generation | Verified 4s production call · `$0.400000` estimated provider cost |
| OpenAI | `tts-1` → `tts-1-hd` | Voice generation | Production MP3 calls persisted, embedded, and verified in B2 |

See [`docs/MODELS_USED.md`](docs/MODELS_USED.md) for the generated submission table and
[`docs/PROVIDERS.md`](docs/PROVIDERS.md) for measurement and cost-basis details.

## Run locally

Requirements: Python 3.12+, Node.js 22.13+, and FFmpeg for the motion regression.

```bash
git clone https://github.com/Pavilion-devs/dara-media-control.git dara
cd dara
cp .env.example .env

python3.12 -m venv api/.venv
api/.venv/bin/pip install --upgrade pip
api/.venv/bin/pip install -e api

npm ci
```

For the zero-spend demo, leave `DARA_LIVE_GENERATION_ENABLED=false`. B2 credentials are
required for durable state and the live ledger; `OPENAI_API_KEY` is required only for
explicit live generation. Browser-facing API routes require no account. The web server
derives a pseudonymous actor ID from the connecting address for abuse controls and
mutation audit records; raw IP addresses and ChatGPT identity are not persisted.

Start the API:

```bash
set -a
source .env
set +a
api/.venv/bin/uvicorn dara.main:app --app-dir api --port 8000
```

In a second terminal, load the same server-side variables and start the web app:

```bash
set -a
source .env
set +a
npm run dev
```

Open `http://localhost:3000` for the committed Studio demo replay. The product overview
remains at `http://localhost:3000/about`. The replay makes no provider call.

## Verify the build

```bash
PYTHONPATH=api api/.venv/bin/python -m unittest discover -s api/tests -v
npm run lint
npm test
```

The provider/model inventory is reproducible:

```bash
PYTHONPATH=api api/.venv/bin/python -m dara.tools.list_models
```

## Honest limitations

- **Tamper-evident, not tamper-proof.** Dara is authoritative within an organisation
  controlling its trusted B2 records. It is not an adversarial authenticity system;
  C2PA or an external signer is the appropriate next layer.
- **Reproducible conditions, not identical bytes.** Media models are generally
  non-deterministic. Regeneration replays canonical parameters and records lineage.
- **One writer per job.** B2 has no compare-and-swap transaction for these JSON records;
  concurrent updates to the same job are last-write-wins.
- **Provider diversity is image-first.** OpenAI and Replicate image routes are both
  production-probed, including two deliberate cross-provider recoveries. Video and
  speech have paid production proofs but currently use same-provider OpenAI fallbacks.
- **No fabricated history.** All 20 client evidence records retain their real July 2026
  execution timestamps. The monthly chart therefore has one honest bar; Dara does not
  backdate rows to manufacture a longer operating history.
- **Single-region ingress.** `usedara.xyz` terminates TLS through TierHive's London
  HAProxy and reaches one private VPS backend. B2 remains durable in `us-east-005`, but
  the interactive control plane does not yet fail over to a second compute region.

## Genblaze feedback

Reproducible SDK findings and workarounds live in
[`docs/SDK_FEEDBACK.md`](docs/SDK_FEEDBACK.md):

- [`#238` — pointer-mode output path can be nonexistent](https://github.com/backblaze-labs/genblaze/issues/238)
- [`#239` — successful fallback erases the failed primary attempt](https://github.com/backblaze-labs/genblaze/issues/239)
- [`#240` — `DalleProvider` drops GPT Image response usage](https://github.com/backblaze-labs/genblaze/issues/240)

## License

MIT
