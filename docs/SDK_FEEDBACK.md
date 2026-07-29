# Genblaze SDK feedback

Findings from building Dara against:

| Package | Version |
|---|---:|
| `genblaze` | `0.4.3` |
| `genblaze-core` | `0.3.8` |
| `genblaze-s3` | `0.3.6` |
| `genblaze-openai` | `0.3.4` |

The upstream tracker was searched before filing. A fourth finding about binary-float
money representation was not filed because
[`backblaze-labs/genblaze#63`](https://github.com/backblaze-labs/genblaze/issues/63)
already covers it.

## 1. Pointer-mode `SmartEmbedder` can return a nonexistent output path

**Filed:** [`backblaze-labs/genblaze#238`](https://github.com/backblaze-labs/genblaze/issues/238)

### Summary

When pointer mode is used with a distinct `output=`, `SmartEmbedder.embed()` writes the
pointer sidecar next to the requested output path and returns that path in
`EmbedResult.path`, but it does not create or copy the media file to that path.
Consumers receive an apparently successful result whose declared media path does not
exist.

### Reproduction

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from genblaze_core import Asset, EmbedPolicy, Modality, Pipeline
from genblaze_core.media.embedder import SmartEmbedder
from genblaze_core.testing import MockProvider

with TemporaryDirectory() as tmp:
    root = Path(tmp)
    source = root / "source.png"
    source.write_bytes(b"png")
    result = (
        Pipeline("pointer")
        .step(
            MockProvider(
                name="mock",
                assets=[
                    Asset(
                        url=source.as_uri(),
                        media_type="image/png",
                        sha256="a" * 64,
                    )
                ],
            ),
            model="mock-v1",
            modality=Modality.IMAGE,
            prompt="x",
        )
        .run(raise_on_failure=True)
    )
    result.manifest.manifest_uri = "https://example.test/manifest.json"
    output = root / "redacted.png"
    embedded = SmartEmbedder().embed(
        source,
        result.manifest,
        output=output,
        policy=EmbedPolicy(embed_mode="pointer"),
    )
    print(embedded.path.exists())         # False
    print(embedded.sidecar_path.exists()) # True
```

### Why it matters

Dara creates token-scoped disclosure derivatives. Trusting `EmbedResult.path` would
upload a missing file or tempt callers to assume the redacted output owns separate media
bytes when it does not. Dara works around this by copying trusted bytes first, then
writing the pointer sidecar.

### Suggested fix

Choose and document one contract:

1. copy `source` to `output` atomically before writing the pointer sidecar, then return
   the existing output path; or
2. reject a distinct `output` in pointer mode and return `source` as the path.

Add a regression asserting `EmbedResult.path.exists()` for source-only and distinct-
output pointer calls.

## 2. Successful fallback erases the failed primary attempt from provenance

**Filed:** [`backblaze-labs/genblaze#239`](https://github.com/backblaze-labs/genblaze/issues/239)

### Summary

`fallback_models` retries correctly, but a successful fallback replaces the failed
primary `Step`. The final run and manifest keep only `fallback_from` /
`fallback_model` metadata. The primary error, timing, upstream ID, and possible charge
are lost.

### Reproduction

```python
from genblaze_core import Asset, Modality, Pipeline
from genblaze_core.exceptions import ProviderError
from genblaze_core.models.enums import ProviderErrorCode
from genblaze_core.testing import MockProvider

class FailThenPass(MockProvider):
    def generate(self, step, config=None):
        if step.model == "primary-v1":
            raise ProviderError(
                "primary unavailable",
                error_code=ProviderErrorCode.MODEL_ERROR,
            )
        return super().generate(step, config)

provider = FailThenPass(
    name="mock",
    assets=[
        Asset(
            url="memory://ok.png",
            media_type="image/png",
            sha256="a" * 64,
        )
    ],
    cost_usd=0.01,
)
result = (
    Pipeline("fallback-audit")
    .step(
        provider,
        model="primary-v1",
        modality=Modality.IMAGE,
        prompt="x",
        fallback_models=["fallback-v2"],
    )
    .run(raise_on_failure=True)
)

print(len(result.run.steps))  # 1
print(result.run.steps[0].model)  # fallback-v2
print("primary unavailable" in result.manifest.to_canonical_json())  # False
```

### Why it matters

A provider error does not imply a free call. Production cost-per-approved-asset,
reliability analysis, and audit trails need every attempt—including a failed primary
that may have started billable work. Dara must maintain a separate attempt ledger because
the provenance manifest cannot reconstruct the failure.

### Suggested fix

Persist an append-only attempt record for each primary, retry, and fallback invocation,
with model, provider, timestamps, outcome, error code, upstream ID, and known/estimated/
unknown cost. This could be `Step.attempts` to avoid changing the pipeline graph.
Streaming should emit a distinct fallback-attempt event from the same data.

## 3. `DalleProvider` drops GPT Image response usage

**Filed:** [`backblaze-labs/genblaze#240`](https://github.com/backblaze-labs/genblaze/issues/240)

### Summary

OpenAI GPT Image responses expose a top-level `usage` object, but
`DalleProvider.generate()` consumes only `response.data`. It leaves
`Step.provider_payload` empty and applies registry pricing without preserving the token
counts. Consumers cannot calculate or audit usage-based settled cost later.

### Reproduction

```python
import base64
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from genblaze_core import Modality, Step
from genblaze_openai import DalleProvider

with TemporaryDirectory() as tmp:
    provider = DalleProvider(api_key="test", output_dir=tmp)
    response = SimpleNamespace(
        data=[
            SimpleNamespace(
                b64_json=base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode()
            )
        ],
        usage=SimpleNamespace(
            input_tokens=12,
            output_tokens=34,
            total_tokens=46,
        ),
    )
    client = Mock()
    client.images.generate.return_value = response
    step = Step(
        provider="openai-dalle",
        model="gpt-image-2",
        modality=Modality.IMAGE,
        prompt="x",
        params={"quality": "low", "size": "1024x1024"},
    )
    with patch.object(provider, "_get_client", return_value=client):
        result = provider.generate(step)

    print(result.provider_payload)  # {}
```

### Why it matters

Dara can cap pre-flight spend with a conservative registry estimate, but the honest
ledger must distinguish reservation from provider-reported usage. Dropping usage forces
all GPT Image accounting to remain estimated even when the API returned the data needed
for later reconciliation.

### Suggested fix

Copy the stable usage fields into `Step.provider_payload["usage"]`, using plain JSON
types and no signed URLs or response bodies. If the connector can calculate cost from a
user-supplied registry, retain both usage and cost rather than replacing one with the
other. Add tests for SDK-object and dict-shaped responses, plus responses without usage.
