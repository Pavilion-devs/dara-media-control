# Providers and models

Generated from `api/dara/providers.py`. OpenAI is Dara's only configured AI
provider. Genblaze is the orchestration and provenance SDK, not a model provider.

| Provider | Model | Modality | Role | Evidence |
|---|---|---|---|---|
| OpenAI | `gpt-image-2` | image | Primary | Production calls persisted and verified in B2 |
| OpenAI | `gpt-image-2-2026-04-21` | image | Fallback | Configured fallback; account catalog verified |
| OpenAI | `sora-2` | video | Primary | Pipeline implemented; deterministic integration proof |
| OpenAI | `sora-2-pro` | video | Fallback | Configured fallback; deterministic integration proof |
| OpenAI | `tts-1` | audio | Primary | Pipeline implemented; deterministic integration proof |
| OpenAI | `tts-1-hd` | audio | Fallback | Configured fallback; deterministic integration proof |
| OpenAI | `gpt-4.1-mini` | text + vision | Prompt expansion and visual QA | Production prompt-expansion and vision-QA calls |

The motion pipeline also uses Genblaze `FFmpegCompositor` for deterministic
local audio/video fan-in. Committed demo fixtures use visibly named mock
providers and never masquerade as live AI-provider execution.
