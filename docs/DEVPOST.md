# Dara — Devpost submission copy

Live application: https://usedara.xyz
Public source: https://github.com/Pavilion-devs/dara-media-control

## What it does

Creative teams can generate thousands of media assets while still being unable to
answer basic operational questions about any one file: What did it cost, including
discarded attempts? Which exact model and parameters produced it? Did policy approve
the spend before the provider call? Can the conditions be reconstructed? Can the
delivered bytes be checked against a trusted record?

Dara is the control plane that makes those answers part of the media pipeline.

- **Govern:** typed policies estimate and reserve worst-case cost before execution, then
  enforce again before each provider step, after QA, and before publication. A blocked
  run persists its decision and spends nothing because no provider is called.
- **Verify:** the public verifier extracts and validates the embedded Genblaze manifest,
  resolves Dara's trusted B2 record, and compares the uploaded whole-file SHA-256 with
  the exact published-file hash. One changed byte produces a visible trusted mismatch.
- **Generate:** still, motion, voice, and regeneration workflows stream their steps,
  preserve failed attempts, run structured visual QA, revise when necessary, and link
  every retry through parent/child lineage.
- **Account:** an immutable B2-backed Parquet ledger exposes spend by model, project, and
  month, spend prevented, and cost per approved asset—including work that failed or did
  not ship.

The default experience is a zero-spend replay of a committed 13-run corpus, including
two production policy blocks and a deterministic fail-revise-pass QA path. Live
generation is a separate, explicitly spend-labelled action.

## How it uses Backblaze B2

Backblaze B2 is Dara's entire durable state layer. There is no application database.
The production bucket in `us-east-005` stores media, provenance, lookup indexes, job and
policy state, client shares, and the accounting ledger.

Dara deliberately preserves two immutable byte roles:

1. `assets/{aa}/{bb}/{source_sha}.ext` stores the unembedded source bytes addressed by
   the SHA-256 bound into the Genblaze manifest.
2. `published/{aa}/{bb}/{published_sha}.ext` stores the exact embedded derivative
   delivered to a client, addressed by its own whole-file SHA-256.

Embedding metadata changes a file, so Dara never overwrites the source object and never
pretends the source hash and delivered-file hash should match. Tiny
`index/sha/{sha}.json` pointer objects let the public verifier resolve either trusted
hash without guessing an extension or object key.

The bucket layout is:

```text
dara/live/runs/{tenant}/{date}/{run_id}/      Genblaze run grouping
dara/assets/{aa}/{bb}/{source_sha}.ext        immutable source bytes
dara/published/{aa}/{bb}/{published_sha}.ext exact delivered bytes
dara/share-assets/{token}/{asset_id}.ext      token-scoped share copies
dara/manifests/{run_id}.json                  provenance
dara/index/sha/{sha}.json                     trusted hash lookup
dara/ledger/{table}/year=YYYY/month=MM/*.parquet
dara/state/{jobs,live-runs,policies,projects,shares}/
```

For accounting, Genblaze's `ParquetSink` first writes completed tables into a local
per-job staging directory. Dara uploads each completed table as a new immutable,
year/month-partitioned B2 object, cleans the staging directory, and configures DuckDB
`httpfs` against the B2 S3-compatible endpoint. Ledger queries run directly over those
remote Parquet objects; Dara does not download the dataset into another database.

Job records are written to B2 on every state transition. After a process restart, Dara
reconciles orphaned work, releases safe reservations, and rebuilds the current day's
committed spend from durable live-run records. Policies, projects, and redacted share
records use the same object-storage model.

## How it uses Genblaze

Genblaze is the execution and provenance spine, not a thin wrapper around one model
call. Dara uses:

- multi-step `Pipeline` graphs for still, motion, voice, and regeneration workflows;
- `input_from` fan-in to connect generated visuals, narration, and deterministic FFmpeg
  composition;
- `fallback_models` on generative steps, with explicit failover events;
- `AgentLoop` for structured visual scoring, prompt revision, and capped retries;
- `parent_run_id` to preserve retry and regeneration lineage;
- `ObjectStorageSink` for B2-bound source assets and manifests;
- `ParquetSink` for run, step, asset, and cost telemetry;
- `EmbedPolicy` pointer mode for disclosure-safe, integrity-preserving share sidecars;
- manifest embed, extract, canonical verification, and trusted-record resolution;
- a customised `ModelRegistry` for pre-flight pricing and worst-case reservations;
- `astream()` for the live Studio event stream;
- `abatch_run()` for bounded, genuinely concurrent voice variants;
- replay semantics for regeneration from recorded parameters;
- `LoggingTracer` for structured execution evidence; and
- `FFmpegCompositor` for deterministic audio/video fan-in.

Dara also preserves a boundary Genblaze correctly exposes: the manifest's source asset
hash is not the whole-file hash of a derivative after embedding. Dara adds the trusted
`published_sha256` record in B2 so the public verifier can make the stronger delivered-
file comparison without corrupting Genblaze's source binding.

During the build, Dara produced three reproduced Genblaze SDK reports:

- [#238 — pointer-mode output path can be nonexistent](https://github.com/backblaze-labs/genblaze/issues/238)
- [#239 — successful fallback erases the failed primary attempt](https://github.com/backblaze-labs/genblaze/issues/239)
- [#240 — `DalleProvider` drops GPT Image response usage](https://github.com/backblaze-labs/genblaze/issues/240)

## Providers and models

OpenAI is Dara's primary AI provider. Replicate's official FLUX route is implemented as
the provider-diverse image fallback. Both providers have completed production image
calls persisted and verified in B2. Genblaze is the orchestration and provenance SDK.

| Provider | Model | Modality | Dara role | Evidence |
|---|---|---|---|---|
| OpenAI | `gpt-image-2` | Image | Primary generation | Production calls persisted and verified in B2 |
| OpenAI | `gpt-image-2-2026-04-21` | Image | Same-provider snapshot fallback | Configured and verified in the account catalog |
| Replicate | `black-forest-labs/flux-1.1-pro` | Image | Provider-diverse fallback | Production call persisted and verified in B2 · 5.518s · $0.040000 |
| OpenAI | `gpt-4.1-mini` | Text and vision | Prompt expansion and visual QA | Production prompt-expansion and QA calls |
| OpenAI | `sora-2` | Video | Primary motion generation | Implemented pipeline and deterministic integration proof |
| OpenAI | `sora-2-pro` | Video | Motion fallback | Configured pipeline fallback and deterministic integration proof |
| OpenAI | `tts-1` | Audio | Primary speech generation | Implemented parallel voice pipeline and deterministic integration proof |
| OpenAI | `tts-1-hd` | Audio | Speech fallback | Configured pipeline fallback and deterministic integration proof |

The production measurement set contains five `gpt-image-2` calls—four successes and one
recorded failure—and three successful `gpt-4.1-mini` visual-QA calls. Failed work remains
in the ledger instead of disappearing from cost-per-approved-asset calculations.

Committed demo fixtures use visibly named mock providers and are never presented as live
provider execution. The Replicate evidence is a separate paid call whose stored bytes
and Genblaze manifest were read back from B2 and independently verified.

## What we'd build next

- **C2PA signing or an external signer:** Dara is tamper-evident inside an organisation's
  trusted B2 boundary; adversarial public authenticity needs an independent signature
  layer.
- **Webhook and CI sinks:** policy decisions and verification results should be able to
  block a publishing workflow automatically.
- **Multi-tenant identity and coordination:** the current deployment is intentionally a
  single API instance with in-process admission locks. Horizontal scale needs durable
  transactional coordination in addition to object storage.
- **Broader provider diversity:** extend the measured cross-provider route beyond still
  images to motion and speech while retaining deterministic graceful degradation.
