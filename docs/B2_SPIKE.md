# Backblaze B2 storage spike

Verified on 2026-07-29 against Dara's dedicated private bucket:

| Field | Result |
|---|---|
| Bucket | `dara-media-control-2026` |
| Region | `us-east-005` |
| Run ID | `c206e036-887b-4fab-874d-cb3e2994dd0e` |
| Asset ID | `8590d1cd-5e02-48c8-8367-202b3da8031b` |
| Asset SHA-256 | `2d433a14b308cfee9b6bff28417941354cccfe0a51b4a0cfdd3482d25ac3e224` |
| Manifest canonical hash | `3f4eafb0a17b66b767df26200b499334262ab15c05e31b32478c5eb0355f780c` |
| `verify_hash()` | `true` |
| `verify()` | `true` |

The bucket contained exactly the two expected spike objects after the run:

```text
dara/spikes/runs/demo/2026-07-29/c206e036-887b-4fab-874d-cb3e2994dd0e/assets/8590d1cd-5e02-48c8-8367-202b3da8031b.png
dara/spikes/runs/demo/2026-07-29/c206e036-887b-4fab-874d-cb3e2994dd0e/manifest.json
```

No credentials are committed. The scoped application key is stored in the ignored
local `.env` file.

## Live OpenAI generation

The first paid provider run completed on 2026-07-29:

| Field | Result |
|---|---|
| Provider | `openai-dalle` |
| Model | `gpt-image-2` |
| Run ID | `f1a3332d-5727-4644-976a-2f7c09c74e82` |
| Asset ID | `9856ed41-b723-47e7-99b8-4a6fee2663cf` |
| Asset SHA-256 | `97f3532e16f7132ee46af4c581a32b6fb720466dd15c131eef1e7a9b7d5f3164` |
| Downloaded SHA-256 | `97f3532e16f7132ee46af4c581a32b6fb720466dd15c131eef1e7a9b7d5f3164` |
| Manifest canonical hash | `13dc9b8ae977809a90ffcc5b3971a011dc5cbac8c8505df2e7f131fa8a9e9b28` |
| Provider latency | `29.369s` |
| Provider-reported cost | unavailable; must be supplied by Dara's pricing registry |
| `verify_hash()` | `true` |
| `verify()` | `true` |

```text
dara/live/runs/demo/2026-07-29/f1a3332d-5727-4644-976a-2f7c09c74e82/assets/9856ed41-b723-47e7-99b8-4a6fee2663cf.png
dara/live/runs/demo/2026-07-29/f1a3332d-5727-4644-976a-2f7c09c74e82/manifest.json
```

## Published derivative and tamper proof

Dara preserved the Genblaze-bound source object, embedded the manifest into a separate
published derivative, and recorded both hashes:

| Field | Result |
|---|---|
| Source SHA-256 | `97f3532e16f7132ee46af4c581a32b6fb720466dd15c131eef1e7a9b7d5f3164` |
| Published SHA-256 | `efaf24d3c4cbeeb2497acd5fcba1e485be529a0ece944190c4caef8720244c25` |
| Untouched published file | `trusted-match`, `verified: true` |
| One-byte-changed copy | `trusted-mismatch`, `verified: false` |
| Changed-copy SHA-256 | `d90b1143fb5392a6fd6eeb7de0c23f2b35a71fe53f76a780c7c4469f45bb8ae5` |

The published object, flat manifest lookup, trusted AssetRef, and source/published
SHA-index pointers all live in Dara's dedicated B2 prefix.

## Durable zero-spend policy proof

Job `job_b2_block_proof_20260729` requested three variants under a one-variant locked
policy. Dara returned `blocked`, made zero provider calls, recorded actual cost
`0.000000`, and wrote the job to:

```text
dara/state/jobs/demo/job_b2_block_proof_20260729.json
```

A newly constructed `B2JobStore` loaded the record back with status `blocked` and
violation `TOO_MANY_VARIANTS`. This proves the policy decision survives service
reconstruction rather than existing only in process memory.
