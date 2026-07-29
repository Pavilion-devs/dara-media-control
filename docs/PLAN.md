# PLAN.md — build order

Deadline: **Aug 3 2026, 5:00pm EDT.** Target submit: **Aug 2, evening.** Aug 3 is buffer only.

## Strategy in one paragraph

Four judging criteria, equally weighted: real-world utility, production readiness,
B2 depth, Genblaze depth. Two of the four are "did you use our stuff meaningfully,"
which is winnable by effort rather than inspiration. So: put the ambition in the
pipeline and policy layers where judges read code, keep the UI to three screens,
and make sure every B2 role and every Genblaze primitive listed in the specs is
actually exercised and actually named in the README.

## Milestones

| # | Milestone | Done when |
|---|---|---|
| M0 | Spike green | A real asset and its manifest land in B2 from a Genblaze pipeline |
| M1 | Verify works | Public page accepts a file, extracts manifest, verifies hash, renders lineage |
| M2 | Policy blocks | A run that violates budget is rejected before any provider call is made |
| M3 | One pipeline live | `still-campaign` runs end to end with QA loop and streams to the UI |
| M4 | Ledger queries | DuckDB returns spend-by-model from Parquet on B2 |
| M5 | Regenerate works | Replay a run from its manifest and show the diff |
| M6 | Judge-ready | Deployed, seeded, rate-limited, README done, demo mode default |
| M7 | Submitted | Devpost form complete, video public, repo access granted |

## Day by day

**Day 1 — spike and skeleton (M0)**
Do nothing else until an asset is in your bucket. The single biggest risk in this
project is discovering on Day 5 that a provider model ID is wrong or a modality is
unavailable. Find that out today.

**Day 2 — verify and policy (M1, M2)**
These are the differentiators and they cost no API credits to build or test. Both are
pure logic over data you already have. Doing them early means that even a disastrous
Day 4 still leaves you with a submittable, defensible product.

**Day 3 — generation and streaming (M3)**
One pipeline, done properly, with the QA loop and SSE. Resist adding pipelines two and
three until this one is solid.

**Day 4 — ledger, regenerate, remaining pipelines (M4, M5)**

**Day 5 — harden, deploy, seed, README (M6)**
Seeding is not optional. A judge who clicks nothing must still see a fully populated
system.

**Day 6 — demo video, submission text, submit (M7)**
Budget the whole day. The video is scored and most people give it forty minutes.

## Task checklist

Work top to bottom. Each task is one commit.

### Phase 0 — foundations

- [x] **T-01** Create private B2 bucket `dara-media-control-2026` with default
      encryption. Generate a read/write application key scoped only to that bucket.
      Record `B2_KEY_ID`, `B2_APP_KEY`, `B2_BUCKET`, `B2_REGION`, `B2_ENDPOINT`
      in the ignored local environment file.
- [x] **T-02** Configure an OpenAI API key and confirm this account can access
      `gpt-image-2`, `gpt-image-1.5`, `gpt-image-1`, and `gpt-image-1-mini`.
      OpenAI is Dara's primary live-media provider; NVIDIA is no longer a prerequisite.
- [ ] **T-03** Add a vision-capable QA evaluator and one provider-diverse image
      fallback only after the primary OpenAI still pipeline is reliable. Claude may be
      used as the evaluator, but it is not a Genblaze media-generation provider.
- [x] **T-04** Scaffold `api/` — FastAPI, Pydantic v2, tests, health and policy
      endpoints.
- [x] **T-05** Scaffold and deploy the web control surface.
- [x] **T-06** Install and inspect the Genblaze core, S3, Parquet, testing, and OpenAI
      packages actually used by Dara. Record their public surface in
      `docs/SDK_SURFACE.md`.
- [x] **T-07** Run Dara's zero-key Genblaze pipeline. It produces a valid canonical
      manifest with both verification checks true and is covered by the test suite.
- [x] **T-08** **Spike (M0):** one `gpt-image-2` generation through `Pipeline` →
      Genblaze's OpenAI provider → `ObjectStorageSink` → B2. The stored asset was
      downloaded and rehashed; its bytes match the manifest SHA-256, and
      `verify_hash()` plus `verify()` both return true.
- [ ] **T-09** Record real latency and cost per model in `docs/PROVIDERS.md`. Mark any
      model that fails or exceeds 90s. These become your fallback ordering.

### Phase 1 — verify (M1)

- [x] **T-10** `storage.py`: typed helpers for `put_json`, `get_json`, `list_prefix`,
      `put_bytes`, `presign`. Everything else goes through these.
- [x] **T-11** `verify.py`: accept an uploaded file, detect type, extract the embedded
      manifest, verify its canonical hash, resolve the trusted AssetRef, and compare the
      uploaded whole-file hash with `published_sha256`. Report `trusted-match`,
      `trusted-mismatch`, or `self-consistent` explicitly. Never compare embedded bytes
      directly with Genblaze's pre-embed `asset.sha256`.
- [x] **T-12** Fallback path: if no manifest is embedded, hash the file and fetch
      `index/sha/{sha}.json`; do not guess a content-address key without its extension.
      Report `embedded` vs `matched-by-hash` vs `unknown`.
- [x] **T-13** `POST /v1/verify` and `GET /v1/verify/{sha256}`. Public, no auth,
      rate-limited by IP.
- [x] **T-14** Verify page in `web/`. Dropzone, hash comparison rendering, lineage
      display. See `docs/FRONTEND_SPEC.md` for the hash-diff treatment.
- [x] **T-15** Publish an embedded derivative, persist its `published_sha256`, and test
      with a tampered copy. One flipped byte must produce a visible trusted mismatch while
      the untouched embedded file passes. This is the demo money shot — make it look good.

### Phase 2 — policy (M2)

- [ ] **T-16** `policy/models.py`: `Policy`, `Violation`, `Decision` per
      `docs/POLICY_ENGINE.md`.
- [ ] **T-17** `policy/estimator.py`: estimate run cost from `ModelRegistry` pricing
      before any provider call. Use `Decimal`, handle unpriced models explicitly, and
      reserve worst-case daily spend under the per-tenant admission lock.
- [ ] **T-18** `policy/engine.py`: `evaluate()` at all four enforcement points.
- [ ] **T-19** Policy CRUD endpoints + three seeded policies (permissive, standard,
      locked-down).
- [x] **T-20** Wire pre-flight enforcement into run creation. A blocked run returns
      `409` with a persisted blocked `job_id`, estimate, and structured violations and
      **spends nothing**. It creates no daily-budget reservation.
- [ ] **T-21** Policy decisions recorded onto the run record and surfaced in the UI.

### Phase 3 — generation (M3)

- [ ] **T-22** `providers.py`: provider factory, per-modality fallback chains, custom
      `ModelRegistry` with real pricing for cost display.
- [x] **T-23** `jobs.py`: async job registry. Records persisted to B2 on every state
      transition. State survives a process restart; startup reconciliation marks stale
      running jobs failed as `orphaned` and releases their budget reservations.
- [ ] **T-24** `pipelines/still.py`: prompt expansion → image → QA → publish.
- [x] **T-25** `pipelines/qa.py`: `AgentLoop` evaluator. Structured JSON score, revised
      prompt on failure, retries linked by `parent_run_id`, attempt cap from policy.
- [x] **T-26** SSE endpoint streaming pipeline step events via `astream()`.
- [x] **T-27** Studio screen: brief form, policy selector, live step stream, result.
- [ ] **T-28** Version tree component — every attempt including failures, linked by
      parent run.

### Phase 4 — ledger and regeneration (M4, M5)

- [x] **T-29** Attach `ParquetSink` alongside `ObjectStorageSink`; write to a per-job local
      staging directory, then explicitly upload each completed table to an immutable,
      year/month-partitioned B2 key under `ledger/`. Confirm the local staging directory
      is cleaned. `ParquetSink` itself does not upload to B2.
- [x] **T-30** `ledger.py`: DuckDB with `httpfs` configured against the B2 S3 endpoint.
      Query Parquet in place — do not download it first.
- [x] **T-31** Ledger endpoints: summary aggregates plus a parameterised query surface.
      **Allowlist the queries** — never pass raw user SQL to DuckDB.
- [x] **T-32** Ledger screen: spend by model, by project, by month; cost per approved
      asset including failed retries.
- [ ] **T-33** `POST /v1/regenerate/{job_id}` — resolve the job's
      `genblaze_run_id`, reconstruct params from the manifest, re-run, link Dara jobs via
      `parent_job_id` and Genblaze runs via `parent_run_id`.
- [ ] **T-34** Regeneration diff view: original vs regenerated, side by side, with a
      parameter diff table.

### Phase 5 — remaining pipelines and sharing

- [ ] **T-35** `pipelines/motion.py`: image → video → narration → composite.
- [ ] **T-36** `pipelines/voice.py`: script → multi-voice TTS.
- [ ] **T-37** `share.py`: redacted share links using `EmbedPolicy`. Create a separate
      token-scoped embedded derivative, persist `shared_sha256`, and verify it from the
      Share record. Prompt and params stripped, hash chain intact; never reuse an
      unredacted published file.
- [ ] **T-38** Public `/share/{token}` disclosure page.

### Phase 6 — judge-readiness (M6)

- [ ] **T-39** Seed script: generate 12–15 runs across all pipelines, including two
      policy-blocked runs and one QA-failed-then-passed run. Commit the outputs to
      `api/seeds/` so demo mode needs no live calls.
- [ ] **T-40** Demo mode: default landing state replays seeded runs with realistic step
      timing. Live generation behind an explicit control.
- [ ] **T-41** Rate limits: per-IP on verify, global daily spend cap on live generation.
      Cap enforced by the policy engine itself — dogfood it.
- [ ] **T-42** Deploy `api/` to a US-East region (Fly.io or Railway). Deploy `web/` to
      Vercel, US-East. Confirm cold-start latency is acceptable from a non-US connection.
- [ ] **T-43** Test account and login instructions in the submission. Judges must not
      have to think.
- [ ] **T-44** README rewrite per `docs/SUBMISSION.md`, including the criteria mapping
      table with file paths.
- [ ] **T-45** File 3–5 substantive issues on the Genblaze repo from
      `docs/SDK_FEEDBACK.md`. Qualifies for the Feedback Prize, which stacks with an
      overall prize.

### Phase 7 — submit (M7)

- [ ] **T-46** Record the demo video to the beat sheet in `docs/SUBMISSION.md`.
      Under 3:00. Upload public to YouTube.
- [ ] **T-47** Write the Devpost description: features, B2 usage, Genblaze usage,
      explicit provider and model list.
- [ ] **T-48** Grant judge access if the repo is private. Verify the working URL from a
      clean browser with no session.
- [ ] **T-49** Submit. Then stop touching the deploy.

## Cut list — if you are behind

Cut in this order. Everything above the line still makes a coherent, submittable product.

1. `voiceover-pack` pipeline
2. Regeneration diff view (keep regeneration itself, drop the visual diff)
3. `motion-spot` video pipeline (falls back to still images only)
4. Share links
5. ─── do not cut below this line ───
6. Ledger, policy engine, verify page, one working pipeline
