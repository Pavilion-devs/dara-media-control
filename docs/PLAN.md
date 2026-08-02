# PLAN.md — build order

Deadline: **Aug 3 2026, 5:00pm EDT.** Target submit: **Aug 2, evening.** Aug 3 is buffer only.

## Strategy in one paragraph

Four judging criteria, equally weighted: real-world utility, production readiness,
B2 depth, Genblaze depth. Two of the four are "did you use our stuff meaningfully,"
which is winnable by effort rather than inspiration. So: put the ambition in the
pipeline and policy layers where judges read code, keep the UI to three screens,
and make sure every B2 role and every Genblaze primitive listed in the specs is
actually exercised and actually named in the README.

**Execution directive:** the deadline does not reduce Dara's acceptance criteria.
Complete every legitimate target in this plan; do not activate the historical cut
order at the bottom of this file.

## Milestones

| # | Milestone | Done when |
|---|---|---|
| M0 | Spike green | A real asset and its manifest land in B2 from a Genblaze pipeline |
| M1 | Verify works | Public page accepts a file, extracts manifest, verifies hash, renders lineage |
| M2 | Policy blocks | A run that violates budget is rejected before any provider call is made |
| M3 | One pipeline live | `still-campaign` runs end to end with QA loop and streams to the UI |
| M4 | Ledger queries | DuckDB returns spend-by-model from Parquet on B2 |
| M5 | Regenerate works | Replay a run from its manifest and show the diff |
| M6 | Judge-ready | Deployed, live-first, rate-limited, README and acceptance pass done |
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

**Day 5 — harden, deploy, production evidence, README (M6)**
Production evidence is not optional. A judge who opens the read surfaces must see
real B2-backed history without first creating a new paid run.

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
- [x] **T-03** Add a vision-capable QA evaluator and one provider-diverse image
      fallback only after the primary OpenAI still pipeline is reliable. Claude may be
      used as the evaluator, but it is not a Genblaze media-generation provider.
      OpenAI `gpt-4.1-mini` is the production vision evaluator. On 2026-07-30,
      Replicate `black-forest-labs/flux-1.1-pro` completed a paid Genblaze→B2 probe in
      5.518 seconds at `$0.040000`; the 433,331-byte asset was read back with an exact
      SHA-256 match and both manifest verification checks true. The production VPS
      health endpoint now reports Replicate configured.
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
- [x] **T-09** Record real latency and cost per model in `docs/PROVIDERS.md`. Mark any
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
- [x] **T-14** Verify page in `app/(public)/verify/`. Dropzone, hash comparison rendering, lineage
      display. See `docs/FRONTEND_SPEC.md` for the hash-diff treatment.
- [x] **T-15** Publish an embedded derivative, persist its `published_sha256`, and test
      with a tampered copy. One flipped byte must produce a visible trusted mismatch while
      the untouched embedded file passes. This is the demo money shot — make it look good.

### Phase 2 — policy (M2)

- [x] **T-16** `policy/models.py`: `Policy`, `Violation`, `Decision` per
      `docs/POLICY_ENGINE.md`.
- [x] **T-17** `policy/estimator.py`: estimate run cost from `ModelRegistry` pricing
      before any provider call. Use `Decimal`, handle unpriced models explicitly, and
      reserve worst-case daily spend under the per-tenant admission lock.
- [x] **T-18** `policy/engine.py`: `evaluate()` at all four enforcement points.
- [x] **T-19** Policy CRUD endpoints + three seeded policies (permissive, standard,
      locked-down).
- [x] **T-20** Wire pre-flight enforcement into run creation. A blocked run returns
      `409` with a persisted blocked `job_id`, estimate, and structured violations and
      **spends nothing**. It creates no daily-budget reservation.
- [x] **T-21** Policy decisions recorded onto the run record and surfaced in the UI.

### Phase 3 — generation (M3)

- [x] **T-22** `providers.py`: provider factory, per-modality fallback chains, custom
      `ModelRegistry` with real pricing for cost display.
- [x] **T-23** `jobs.py`: async job registry. Records persisted to B2 on every state
      transition. State survives a process restart; startup reconciliation marks stale
      running jobs failed as `orphaned` and releases their budget reservations.
- [x] **T-24** `pipelines/still.py`: prompt expansion → image → QA → publish.
- [x] **T-25** `pipelines/qa.py`: `AgentLoop` evaluator. Structured JSON score, revised
      prompt on failure, retries linked by `parent_run_id`, attempt cap from policy.
- [x] **T-26** SSE endpoint streaming pipeline step events via `astream()`.
- [x] **T-27** Studio screen: brief form, policy selector, live step stream, result.
- [x] **T-28** Version tree component — every attempt including failures, linked by
      parent run. The rebuilt UI renders the deterministic fail-revise-pass tree in
      Studio and actual Genblaze attempt IDs and `parent_run_id` links for live runs.

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
- [x] **T-33** `POST /v1/regenerate/{job_id}` — resolve the job's
      `genblaze_run_id`, reconstruct params from the manifest, re-run, link Dara jobs via
      `parent_job_id` and Genblaze runs via `parent_run_id`.
- [x] **T-34** Regeneration diff view: original vs regenerated, side by side, with a
      parameter diff table. Completed live rows now require a second explicit
      spend-confirmation click, poll the linked child run, and render the verified
      original/child comparison from the live diff endpoint.

### Phase 5 — remaining pipelines and sharing

- [x] **T-35** `pipelines/motion.py`: generated still → exact 720p normalization +
      Sora text-to-video + narration → FFmpeg composite. The five-step Genblaze graph
      prepends the generated still to the Sora clip and muxes narration, so every input
      contributes to the delivered MP4. The account does not permit Sora image-to-video;
      Dara records that limitation instead of claiming inpaint support. Run
      `e0ed245d-5c9f-4092-87f9-549b48f2efc1` completed the paid graph, embedded and
      re-extracted its manifest, persisted to B2, and reconciled to `$0.410780` total
      provider spend. The zero-network regression exercises the same composition path.
- [x] **T-36** `pipelines/voice.py`: script → multi-voice TTS. Voice variants
      execute through Genblaze `abatch_run(items=...)` with bounded true
      concurrency, per-variant metadata, OpenAI `tts-1` → `tts-1-hd` fallback,
      strict voice validation, and verified manifests.
- [x] **T-37** `share.py`: redacted share links using Genblaze `EmbedPolicy` pointer
      mode. Dara copies trusted source bytes to a separate token-scoped object, stores
      the three-field redacted pointer sidecar separately, persists `shared_sha256`,
      and rehashes served bytes against the Share record. Prompt, params, job id, and
      run id never enter the public response; the unredacted published file is never
      reused. This follows the installed SDK's integrity-safe pointer contract rather
      than creating an unverifiable full redacted manifest.
- [x] **T-38** Public `/share/{token}` disclosure page, backed by the live public API
      and a short-lived URL for the token-scoped object. It renders only provider,
      model, generated time, whole-file shared hash, verification status, redaction
      notice, and the trust-boundary note. Invalid, expired, and integrity-failed
      shares fail closed.

### Phase 6 — judge-readiness (M6)

- [x] **T-39** Seed script: 13 committed run records across still, motion, voice,
      and regeneration in `api/seeds/demo-runs.json`, including two production
      policy-block proofs and one deterministic QA-failed-then-passed fixture.
      Every record carries an explicit `production-proof` or
      `deterministic-fixture` evidence label; fixture provider names and settled
      spend never masquerade as live OpenAI execution. The default record is the
      verified production `openai-dalle / gpt-image-2` asset and shows its original
      `$0.010000` conservative estimate; synthetic fixtures remain selectable.
- [x] **T-40** Demo mode is the default landing state and replays the committed
      production proof using accelerated timers and no new provider call. The screen
      distinguishes original recorded cost from replay spend and keeps live generation
      behind a separate spend-labelled, two-confirmation control. The deterministic
      QA-revision path remains clearly labelled in the replay selector. `/` redirects
      to Studio; the product overview remains available at `/about`.
- [x] **T-41** Rate limits: per-IP on verify; pseudonymous per-actor quotas on
      policy simulation, live generation/regeneration, and disclosure creation;
      plus a global daily spend cap on live generation. The web server HMACs the
      provider-supplied connecting address and never persists a raw IP. The verifier
      trusts Cloudflare forwarding only from the local tunnel peer. Policy admission
      holds a per-tenant lock across worst-case reservation. On restart Dara rebuilds
      today's committed amount from durable B2 live-run records and pessimistically
      charges the full reservation for failed runs whose provider execution began
      but whose settled cost is unknown.
- [x] **T-42** Deployment target superseded by the user-selected stack and verified in
      `docs/DEPLOYMENT.md`: the API runs as an always-on service on a TierHive VPS in
      London, the private preview runs on OpenAI Sites, the public judge web service
      runs separately on the same VPS behind TierHive HAProxy at `usedara.xyz`, and B2
      remains in `us-east-005`.
      Production health, an API-restart/tunnel-stability check, live DuckDB-over-B2
      ledger data, and eight non-US latency samples passed. Median health latency was
      486 ms, p95 was 506 ms, and controlled API restart-to-ready time was 13 seconds.
- [x] **T-43** No test account is required. Demo replay, policy preview, live-run
      creation/listing/status/events/regeneration/diff, disclosure creation,
      verification, asset viewing, and aggregate DuckDB-over-B2 ledger reads are
      anonymous. The Runs screen separates live B2 history from fixtures; Verify hashes
      locally, streams normal files for full embedded-manifest inspection, and reserves
      hash-only lookup for an edge upload-limit fallback.
      Paid mutations remain bounded by the kill switch, per-actor quota, and independent
      deployment-wide daily spend cap. Project changes, cancellation, asset approval,
      policy previews, shares, and generation all use anonymous quotas. Cancellation
      after provider work may have started keeps the full reservation accounted rather
      than pretending it was free. Exact route-by-route instructions live in
      `docs/JUDGE_ACCESS.md`.
- [x] **T-44** README rewritten per `docs/SUBMISSION.md` with real production
      screenshots, the four-criteria mapping, the deployed architecture, the B2
      object layout, exact local setup and verification commands, an honest limitations
      section, and a generated provider/model inventory.
- [x] **T-45** Filed three substantive, reproduced Genblaze issues from
      `docs/SDK_FEEDBACK.md`: pointer-mode output-path integrity
      ([#238](https://github.com/backblaze-labs/genblaze/issues/238)), fallback-attempt
      provenance/accounting
      ([#239](https://github.com/backblaze-labs/genblaze/issues/239)), and missing GPT
      Image response usage
      ([#240](https://github.com/backblaze-labs/genblaze/issues/240)).

### Production evidence hardening

- [x] **T-50** Replace prototype-scale accounting evidence with actual provider-backed
      client-project records: OpenAI and Replicate, still plus a complete motion and
      voice proof, paid rejected attempts, a provider-diverse fallback recovery, and
      policy-blocked expensive work. Every timestamp must be the real execution time;
      do not backdate rows merely to manufacture a monthly chart. The live ledger must
      show attempt-level unapproved spend and more than one provider/model before this
      box is checked. Completed 2026-07-31 with 20 client records across Northwind,
      Atlas, and Field Notes: 12 approved assets, three zero-cost expensive-video
      blocks (`$4.800000` prevented), three paid QA rejections, two OpenAI→Replicate
      recoveries, production motion and voice, and `$0.723650` recorded client spend.
      The all-project live DuckDB ledger reads `$0.818650` spend, `$4.815000` prevented,
      and 27.1593% spend on unshipped work. All dates are actual July execution dates,
      so the monthly chart intentionally has one truthful bar.
- [x] **T-51** Deploy this hardening release and repeat the cookie-free desktop/mobile
      route, console, verification-upload, live ledger, and cancellation checks against
      `usedara.xyz`. API release `58b2e78` and web release `018056f` passed the final
      1440×1000 and 390×844 production audit: ten cookie-free routes returned 200, all
      browser routes had zero overflow and clean consoles, the 1.2 MB proof uploaded as
      a trusted match, live B2 Runs/Ledger rendered, and completed-run cancellation
      failed safely with typed HTTP 409. Exact evidence is in `docs/DEPLOYMENT.md`.
- [x] **T-52** Replace the public replay/fixture presentation with a live-first product
      boundary. Studio now starts as an empty governed generation, requires live B2
      projects and policies, and preserves the two-step maximum-cost confirmation.
      Runs, Assets, Policies, and Ledger render only live API/B2 data and show explicit
      unavailable states instead of substituting committed evidence. Test fixtures stay
      in the automated suite. Accounting writes invalidate the process dashboard cache
      so a completed run appears on the next Ledger query.

### Phase 7 — submit (M7)

- [ ] **T-46** Record the demo video to the beat sheet in `docs/SUBMISSION.md`.
      Under 3:00. Upload public to YouTube.
      Reproducible 12-scene source is committed under `videos/dara-demo`; its
      165.929-second composition passes the HyperFrames runtime, layout, motion, and
      contrast gates with zero errors. Final render, end-to-end playback review, and
      public upload remain.
- [x] **T-47** Write the Devpost description: features, B2 usage, Genblaze usage,
      explicit provider and model list.
- [x] **T-48** Grant judge access if the repo is private. Verify the working URL from a
      clean browser with no session.
- [ ] **T-49** Submit. Then stop touching the deploy.

## Historical contingency order — inactive

This early planning artifact is retained for decision history only. It is not
authorized: Dara is being built against the full checklist above.

1. `voiceover-pack` pipeline
2. Regeneration diff view (keep regeneration itself, drop the visual diff)
3. `motion-spot` video pipeline
4. Share links
5. ─── do not cut below this line ───
6. Ledger, policy engine, verify page, one working pipeline
