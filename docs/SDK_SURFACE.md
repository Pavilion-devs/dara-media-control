# Verified Genblaze SDK surface

Captured against the installed packages on 2026-07-29:

| Package | Version |
|---|---:|
| `genblaze` | `0.4.3` |
| `genblaze-core` | `0.3.8` |
| `genblaze-s3` | `0.3.6` |

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

## Important corrections from the original plan

- `Pipeline.run()` returns `PipelineResult`; use `result.run` and `result.manifest`.
- Pass `raise_on_failure=True` now. The current default emits a deprecation warning
  because a future core release will raise on failed steps by default.
- Parquet support is an extra: install `genblaze-core[parquet]`.
- Backblaze storage is supplied by `genblaze-s3`, not the core package alone.
- `ObjectStorageSink` accepts a `ParquetSink`, but the Parquet sink itself remains local.
  Dara uploads closed immutable Parquet files to its B2 ledger partition keys.
