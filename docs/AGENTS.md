# AGENTS.md — operating manual for Codex

Read this first, every session. Then read `PLAN.md` for what to build next.

## What this repo is

**Dara** — a media supply chain control plane. Teams generate media through governed
pipelines, every output carries a verifiable provenance manifest, and every run is
accounted for in a queryable ledger. Built for the Backblaze Generative Media Hackathon
(submission deadline: Aug 3 2026, 5:00pm EDT).

Four pillars, in priority order. If you must cut, cut from the bottom:

1. **Verify** — public, no-auth verification of any generated file. Zero API cost.
2. **Govern** — declarative policy enforced before spend happens.
3. **Generate** — multi-provider Genblaze pipelines with agentic QA.
4. **Account** — DuckDB-over-Parquet ledger on B2.

## Non-negotiable constraints

- **Genblaze is Python-only.** All generation logic lives in `api/`. The Next.js app
  never calls a media provider directly. No exceptions.
- **B2 is the only datastore.** No Postgres, no Redis, no SQLite-on-a-volume. Job state,
  policies, projects, manifests, assets, ledger — all objects in one B2 bucket.
  This is a deliberate architectural claim, not a shortcut. See `docs/ARCHITECTURE.md`.
- **Parquet staging is not a datastore.** `ParquetSink` writes into a per-job local
  temporary directory. Upload every completed file to an immutable partitioned B2 key,
  then delete the staging files. Never claim `ParquetSink` writes directly to B2.
- **Source and published hashes are different.** Genblaze's `asset.sha256` covers the
  source before embedding. Publish an embedded derivative without overwriting that source,
  record its `published_sha256`, and use the trusted published value for whole-file
  verification.
- **No secrets in the frontend.** Provider keys and B2 credentials only ever exist in
  the Python service's environment.
- **Demo mode is the default.** Judges land in a replay of cached runs that costs $0.
  Live generation is behind an explicit action with a hard spend cap.
- **Every generation path must have a `fallback_models` chain.** Provider flakiness is
  the single most likely cause of a failed demo.
- **Every provider attempt is accounted for.** Failure and timeout do not imply zero
  cost. Record known, estimated, or unknown cost for every attempt.

## Repo layout

```
dara/
├── AGENTS.md              you are here
├── PLAN.md                build order + task checklist
├── README.md              judge-facing; keep current, it is scored
├── .env.example
├── docs/                  specs — read the relevant one before writing code
├── api/                   FastAPI + Genblaze (Python 3.11+)
│   ├── dara/
│   │   ├── main.py            app factory, routers
│   │   ├── config.py          settings from env
│   │   ├── storage.py         B2 object helpers (get/put/list JSON)
│   │   ├── policy/
│   │   │   ├── models.py      Policy, Violation, Decision
│   │   │   ├── engine.py      evaluate() at 4 enforcement points
│   │   │   └── estimator.py   pre-flight cost estimate from ModelRegistry
│   │   ├── pipelines/
│   │   │   ├── registry.py    pipeline spec -> builder
│   │   │   ├── still.py       still-campaign
│   │   │   ├── motion.py      motion-spot
│   │   │   ├── voice.py       voiceover-pack
│   │   │   └── qa.py          AgentLoop evaluator
│   │   ├── providers.py       provider factory + fallback chains
│   │   ├── jobs.py            async job registry, B2-persisted
│   │   ├── ledger.py          DuckDB over Parquet on B2
│   │   ├── verify.py          manifest extract + verify
│   │   ├── share.py           redacted share links (EmbedPolicy)
│   │   └── routers/           one module per API surface
│   ├── seeds/                 pre-generated demo runs (committed)
│   └── tests/
├── app/                   Next.js App Router routes and server-side API proxies
├── components/            Shared UI, Dara domain, and shell components
└── worker/                Vinext/Cloudflare-compatible web entry
```

## Working rules

**Before writing code in an area, read its spec.** `docs/POLICY_ENGINE.md` before
touching `api/dara/policy/`. `docs/PIPELINES.md` before `api/dara/pipelines/`.
`docs/API_SPEC.md` before any router. `docs/FRONTEND_SPEC.md` before any UI.
The specs are the contract; if code and spec disagree, fix one of them explicitly
and say which.

**Verify Genblaze API surface against the installed package, not memory.** This SDK is
new and its docs may lag. Before using any Genblaze symbol, confirm it exists:

```bash
python -c "import genblaze_core; print([x for x in dir(genblaze_core) if not x.startswith('_')])"
```

If a documented feature does not exist in the installed version, note it in
`docs/SDK_FEEDBACK.md` (create it) with the exact error — that file becomes the
Feedback Prize submission. Do not silently work around it without recording it.

**Ship vertical slices.** A working end-to-end path beats four half-built layers.
Order: verify page → policy engine → one pipeline → ledger → remaining pipelines.

**Commit on every green task** with the task ID from `PLAN.md`, e.g.
`git commit -m "T-14: pre-flight cost estimation from ModelRegistry"`.

**Log every provider call** with model, latency, cost, and outcome. You will need this
for the ledger, for debugging at 2am, and for the demo video.

## Style

- Python: type hints everywhere, `ruff` clean, Pydantic v2 models for all
  request/response and stored-object schemas. Async by default in routers.
- Money: `Decimal` in policy and accounting logic; six-place decimal strings in JSON.
  Do not use binary floats for budget decisions.
- TypeScript: strict mode. No `any`. Zod-parse every API response at the boundary.
- Errors surface real causes. Never swallow a provider exception into a generic 500 —
  map it to a typed error the UI can render (see `docs/API_SPEC.md` error model).
- No emoji in code, commits, or UI.

## Things that will lose the hackathon — do not do them

- Making a judge wait on a spinner for a video that takes four minutes.
- Requiring the judge to supply their own API key.
- A README that does not map the work to the four judging criteria.
- Using B2 as a plain file bucket. Every B2 role in `docs/DATA_MODEL.md` must be real.
- Calling one `Pipeline.step()` and calling it Genblaze integration.
- Claiming the provenance manifest defeats an adversarial forger. It does not — it is
  tamper-evident in trusted storage. See the positioning note in `docs/PRD.md`.
  Overclaiming this is the fastest way to lose credibility with these specific judges.
- Comparing an embedded file's whole-file hash to Genblaze's pre-embed `asset.sha256`.
  It will differ for a legitimate file. Resolve the trusted AssetRef and compare with
  `published_sha256`.
