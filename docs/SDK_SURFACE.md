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
    KeyStrategy,
    Manifest,
    Modality,
    ModelRegistry,
    ObjectStorageSink,
    ParquetSink,
    Pipeline,
)
from genblaze_s3 import S3StorageBackend
from genblaze_openai import DalleProvider
```

Confirmed constructor and method shape:

- `Pipeline(name=None, tenant_id=None, *, project_id=None, chain=False, ...)`
- `Pipeline.step(provider, *, model, prompt=None, modality=Modality.IMAGE,
  fallback_models=None, input_from=None, params=None, **extra_params)`
- `Pipeline.run(*, sink=None, fail_fast=True, raise_on_failure=None, timeout=None, ...)`
- `Pipeline.arun(...)` and `Pipeline.astream(...)`
- `ObjectStorageSink(backend, *, prefix="genblaze",
  key_strategy=KeyStrategy.CONTENT_ADDRESSABLE, parquet_sink=None, ...)`
- `ParquetSink(base_dir, *, policy=None)` writes to a local directory.
- `S3StorageBackend.for_backblaze(bucket=None, *, region=None, key_id=None,
  app_key=None, public_url_base=None, auto_lifecycle=False, preflight=True)`
- `DalleProvider(api_key=None, http_timeout=60.0, output_dir=None, ...)` supports
  the `gpt-image-*` model family and reads `OPENAI_API_KEY` from the environment.
- `Manifest.verify_hash()` verifies the canonical manifest hash.
- `Manifest.verify()` additionally requires declared output SHA-256 coverage; it does
  not fetch or rehash remote asset bytes.
- `AgentLoop(pipeline_factory, evaluator, *, max_iterations=3, ...)`

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

## Important corrections from the original plan

- `Pipeline.run()` returns `PipelineResult`; use `result.run` and `result.manifest`.
- Pass `raise_on_failure=True` now. The current default emits a deprecation warning
  because a future core release will raise on failed steps by default.
- Parquet support is an extra: install `genblaze-core[parquet]`.
- Backblaze storage is supplied by `genblaze-s3`, not the core package alone.
- `ObjectStorageSink` accepts a `ParquetSink`, but the Parquet sink itself remains local.
  Dara uploads closed immutable Parquet files to its B2 ledger partition keys.
