# Verified Genblaze SDK surface

Captured against the installed packages on 2026-07-29:

| Package | Version |
|---|---:|
| `genblaze` | `0.4.3` |
| `genblaze-core` | `0.3.8` |
| `genblaze-s3` | `0.3.6` |
| `genblaze-openai` | `0.3.4` |

These are the versions Dara pins for the spike. Do not code against an assumed SDK
surface without updating this file and the executable spike.

## Confirmed entry points

```python
from genblaze_core import (
    AgentLoop,
    EmbedPolicy,
    FFmpegCompositor,
    KeyStrategy,
    LoggingTracer,
    Manifest,
    Modality,
    ModelRegistry,
    ModelSpec,
    ObjectStorageSink,
    ParquetSink,
    Pipeline,
)
from genblaze_s3 import S3StorageBackend
from genblaze_openai import DalleProvider, OpenAITTSProvider, SoraProvider
```

Confirmed constructor and method shape:

- `Pipeline(name=None, tenant_id=None, *, project_id=None, chain=False, ...)`
- `Pipeline.step(provider, *, model, prompt=None, modality=Modality.IMAGE,
  fallback_models=None, input_from=None, params=None, **extra_params)`
- `Pipeline.run(*, sink=None, fail_fast=True, raise_on_failure=None, timeout=None, ...)`
- `Pipeline.arun(...)` and `Pipeline.astream(...)`
- `Pipeline.abatch_run(items=[...], max_concurrency=N, ...)` clones the graph per
  item, merges non-reserved item keys into step-zero params, and returns results in
  input order. Dara uses it for bounded, parallel voice variants.
- `Pipeline.from_result(result: PipelineResult)` sets the next run's
  `parent_run_id` to `result.run.run_id`; Dara uses this for QA revisions and
  manifest-based regeneration.
- `ObjectStorageSink(backend, *, prefix="genblaze",
  key_strategy=KeyStrategy.CONTENT_ADDRESSABLE, parquet_sink=None, ...)`
- `ParquetSink(base_dir, *, policy=None)` writes to a local directory.
- `S3StorageBackend.for_backblaze(bucket=None, *, region=None, key_id=None,
  app_key=None, public_url_base=None, auto_lifecycle=False, preflight=True)`
- `DalleProvider(api_key=None, http_timeout=60.0, output_dir=None, ...)` supports
  the `gpt-image-*` model family and reads `OPENAI_API_KEY` from the environment.
- `SoraProvider(...)` supports the `sora-2` family, including image-to-video when a
  prior image asset is wired with `input_from`.
- `OpenAITTSProvider(...)` supports `tts-1` and `tts-1-hd`.
- `FFmpegCompositor(output_dir=None, timeout=120.0, ...)` accepts video and audio
  assets through `input_from=[video_step, audio_step]` and produces an MP4.
- `LoggingTracer()` is accepted by `Pipeline(..., tracer=...)`.
- `ModelRegistry.fork()`, `register(ModelSpec(...))`, and `register_pricing(...)`
  are used by Dara's central image, video, and audio provider factory.
- `Manifest.verify_hash()` verifies the canonical manifest hash.
- `Manifest.verify()` additionally requires declared output SHA-256 coverage; it does
  not fetch or rehash remote asset bytes.
- `AgentLoop(pipeline_factory, evaluator, *, max_iterations=3, ...)`
- `EmbedPolicy(prompt_visibility=PRIVATE, embed_mode="pointer",
  include_params=False, include_seed=False)` is the integrity-safe redaction path in
  the installed SDK. Full-mode redaction is deliberately rejected because it would
  leave the pre-redaction canonical hash beside changed content. Pointer mode emits
  only `schema_version`, `canonical_hash`, and `manifest_uri`.

## Executable proof

Run:

```bash
cd api
.venv/bin/python -m dara.tools.sdk_spike
```

The no-key pipeline currently produces one mock video step, a 64-character canonical
hash, `verify_hash: true`, and `verify: true`. The run id and hash change per run and
must not be hard-coded.

For the real B2 storage proof, run:

```bash
cd api
.venv/bin/python -m dara.tools.b2_spike
```

This exercises `Pipeline` → `ObjectStorageSink` →
`S3StorageBackend.for_backblaze()` against Dara's private scoped bucket. The first
verified run is recorded in `docs/B2_SPIKE.md`. It deliberately uses a local provider
so storage can be validated independently of the live media-provider decision.

The live provider proof is:

```bash
cd api
.venv/bin/python -m dara.tools.openai_b2_spike
```

It uses `gpt-image-2` at low quality for a low-cost smoke test, then persists the
generated image and manifest under `dara/live/`.

The motion pipeline has a zero-network executable test that runs the full
generated still + text-to-video + narration → FFmpeg fan-in graph with mock generative
providers and real local media composition:

```bash
cd api
.venv/bin/python -m unittest tests.test_motion_pipeline -v
```

The test verifies the composite MP4, `input_from` metadata, fallback metadata,
canonical manifest hash, and declared asset hashes.

The voice-pack regression exercises `abatch_run()` and `arun()` without network
calls, proves concurrent provider execution, and verifies one manifest per voice:

```bash
cd api
.venv/bin/python -m unittest tests.test_voice_pipeline -v
```

## Important corrections from the original plan

- `Pipeline.run()` returns `PipelineResult`; use `result.run` and `result.manifest`.
- Pass `raise_on_failure=True` now. The current default emits a deprecation warning
  because a future core release will raise on failed steps by default.
- Parquet support is an extra: install `genblaze-core[parquet]`.
- Backblaze storage is supplied by `genblaze-s3`, not the core package alone.
- `ObjectStorageSink` accepts a `ParquetSink`, but the Parquet sink itself remains local.
  Dara uploads closed immutable Parquet files to its B2 ledger partition keys.
- `SmartEmbedder` pointer mode writes a sidecar; it does not mutate or copy the media.
  Dara therefore copies trusted source bytes into a separate token-scoped object first,
  writes the pointer sidecar beside it, and records/rechecks the shared object's exact
  SHA-256. Calling that object an inline redacted manifest would be incorrect.
