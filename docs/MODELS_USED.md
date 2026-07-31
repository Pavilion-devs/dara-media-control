# Providers and models

Generated from `api/dara/providers.py`. OpenAI is Dara's primary AI provider;
Replicate is the provider-diverse image fallback. Genblaze is the orchestration
and provenance SDK, not a model provider.

| Provider | Model | Modality | Role | Evidence |
|---|---|---|---|---|
| OpenAI | `gpt-image-2` | image | Primary | Production calls persisted and verified in B2 |
| OpenAI | `gpt-image-2-2026-04-21` | image | Fallback | Configured fallback; account catalog verified |
| Replicate | `black-forest-labs/flux-1.1-pro` | image | Fallback | Production call persisted and verified in B2 (5.518s; $0.040000) |
| OpenAI | `sora-2` | video | Primary | Production 4s motion call persisted and verified in B2 ($0.400000 estimated) |
| OpenAI | `sora-2-pro` | video | Fallback | Configured fallback; account catalog verified |
| OpenAI | `tts-1` | audio | Primary | Production calls persisted and verified in B2 |
| OpenAI | `tts-1-hd` | audio | Fallback | Configured fallback; account catalog verified |
| OpenAI | `gpt-4.1-mini` | text + vision | Prompt expansion and visual QA | Production prompt-expansion and vision-QA calls |

The motion pipeline also uses a Dara compositor built on Genblaze's FFmpeg
provider primitives for local still/video/audio fan-in. Those local steps
are recorded at $0. Committed demo fixtures use visibly named mock
providers and never masquerade as live AI-provider execution.
