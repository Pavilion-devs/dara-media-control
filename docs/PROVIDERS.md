# PROVIDERS

## Context

GMI Cloud hackathon credits are exhausted, so every live call must be deliberately
budgeted. Dara uses the official `genblaze-openai` adapter as its primary provider:
GPT Image for images, Sora for video, and OpenAI TTS for speech. The first
`gpt-image-2` runs have completed and persisted successfully to B2.

## Credit strategy — do this first

1. Use `gpt-image-2` low quality for smoke tests and reserve higher-quality generations
   for seeded showcase assets.
2. Keep live generation behind Dara's policy gate. Demo mode must never spend credits.
3. Add a second provider only where it creates real resilience. Do not collect keys
   speculatively.
4. A Claude key is optional for prompt refinement or visual QA through a custom evaluator;
   it does not replace the Genblaze media provider.

Budget the whole event at **under $20 of real spend.** If you are heading past that,
something is wrong with demo mode.

## Fallback chains

Every generative step declares `fallback_models`. Order is by cost ascending, then
reliability. Fill in the reliability column from T-09 once you have measured, and
reorder — measured latency beats assumption.

### Image

| Rank | Provider | Model | Status |
|---|---|---|---|
| 1 | openai | `gpt-image-2` | Active primary; four production successes, one recorded failure |
| 2 | openai | `gpt-image-2-2026-04-21` | Active snapshot fallback; confirmed present in the deployed account catalog without spending |
| 3 | replicate | `black-forest-labs/flux-1.1-pro` | Provider-diverse fallback implemented and contract-tested; production token and live probe pending |
| 4 | openai | `gpt-image-1.5` / `gpt-image-1-mini` | Deprecated and removed from Dara's live chain |

The current OpenAI catalog calls GPT Image 2 the state-of-the-art image model and
marks both GPT Image 1.5 and `gpt-image-1-mini` deprecated. Dara therefore does not
claim that a same-provider deprecated alias satisfies provider diversity.
[GPT Image 2 model card](https://developers.openai.com/api/docs/models/gpt-image-2) ·
[GPT Image 1.5 model card](https://developers.openai.com/api/docs/models/gpt-image-1.5) ·
[`gpt-image-1-mini` model card](https://developers.openai.com/api/docs/models/gpt-image-1-mini)

Replicate's FLUX 1.1 Pro route uses the official-model endpoint, which Replicate
documents as warm, stable, and predictably priced. Its current listed price is $0.04
per output image. The token stays server-side in `REPLICATE_API_TOKEN`.
[Official-model contract](https://replicate.com/docs/topics/models/official-models/) ·
[FLUX 1.1 Pro API](https://replicate.com/black-forest-labs/flux-1.1-pro/api)

After configuring the token, run the paid production probe once:

```bash
python -m dara.tools.replicate_b2_probe
```

The probe must report `provider=replicate`, both manifest checks true, a B2 asset URL,
measured duration, and the registered $0.04 cost before T-03 is checked.

### Video

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | openai | `sora-2` | Primary candidate; must be probed and policy-gated |
| 2 | replicate or google | To be measured | Provider-diverse fallback |
| 3 | — | still fallback | If both fail, degrade to the keyframe still and say so in the UI |

Video is the highest-risk path in the project. Treat the still fallback as a real feature,
not an error state — graceful degradation is a production-readiness signal.

### Audio

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | openai | `tts-1` | Active primary using the existing key; $0.015 per 1K input characters |
| 2 | openai | `tts-1-hd` | Same-provider quality fallback; $0.030 per 1K input characters |
| 3 | elevenlabs | To be measured | Provider-diverse voice fallback |
| 4 | — | no narration | Graceful degradation for motion output |

### Chat — prompt expansion and QA scoring

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | openai | `gpt-4.1-mini` | Live structured vision evaluator; first candidate scored 0.90 |
| 2 | anthropic | Claude, optional custom evaluator | QA only; not a Genblaze media provider |
| 3 | — | deterministic checks | Dimensions, format, file integrity, and manifest verification |

## Production measurement

Generated on 2026-07-29 by `python -m dara.tools.provider_report` from the durable
B2 live-run records and trusted Genblaze manifests. Latency covers the actual provider
step only. Cost is explicitly labelled as a conservative Dara estimate because the
installed Genblaze OpenAI adapter does not preserve settled image-token usage.

| Provider | Model | Modality | Samples | Success / fail | Unit cost | p50 / max latency | >90s |
|---|---|---|---|---|---|---|---|
| openai-dalle | `gpt-image-2` | image | 5 | 4 / 1 | $0.010000 estimated | 20.758s / 21.972s | no |
| openai | `gpt-4.1-mini` | vision QA | 3 | 3 / 0 | $0.005000 estimated | 8.234s / 9.100s | no |

No active measured model exceeded 90 seconds. The single image failure remains in the
sample count and ledger rather than being silently discarded. Video, speech, deprecated
image models, and the Replicate fallback are not presented as measured until a live
production probe exists.

The current Genblaze/OpenAI adapter does not return a provider-reported image cost, so
Dara settles these runs from its conservative registry estimate and labels the basis
`estimated`.

OpenAI prices GPT Image models by input/output image tokens and directs image-generation
users to its calculator for estimates. Dara's registry reservation is therefore an
operational cap, not a claim about a provider-settled invoice amount.
[Official API pricing](https://developers.openai.com/api/docs/pricing)

## Model id verification

Model identifiers drift, and a wrong id fails at runtime on demo day. Before building any
pipeline:

```bash
python -m dara.tools.probe_models --provider openai --modality image
```

`dara.tools.provider_report` derives the evidence from real production calls rather than
spending again merely to probe a model that already has live records. Run it again on
Day 5 before recording the video — catalogs change.

Genblaze ships `probe_models` for conformance checking; use it if the installed version
exposes it rather than writing your own.

## Rate limits and 429s

Treat rate limits and available spend as runtime constraints. Assume seeding can hit
either even when individual smoke tests succeed.

- Exponential backoff with jitter on 429, capped at 3 retries.
- On 402 (credits exhausted), do not retry — fail over to the next provider in the chain
  immediately and emit a `step.failover` event.
- Seed generation runs sequentially with a delay, not in parallel. Blowing your credits
  on parallel seeding on Day 5 would be an unforced error.

## Demo-day protection

1. All seeded runs are pre-generated and committed to `api/seeds/`. Demo mode never calls
   a provider.
2. Live generation is capped by `pol_locked`: $0.10 per run, images only, 1:1 only,
   1 variant. This is the same seeded policy defined in `POLICY_ENGINE.md`; do not create
   a fourth policy name only for this document.
3. A global daily spend ceiling enforced by the policy engine itself. When it trips, live
   generation is blocked with a clear message and demo mode still works completely.
4. Record the demo video against seeded runs, not live calls. Do one live run on camera
   only if it has been reliable for a full day, and have the seeded take ready as backup.

## Attribution for the submission

Devpost requires an explicit list of providers and models. Generate it from the registry
rather than writing it by hand, so it cannot drift from what the code actually calls:

```bash
python -m dara.tools.list_models --format markdown > docs/MODELS_USED.md
```

Paste that into the submission and the README.

## Failed-attempt accounting

A provider error, timeout, or unusable output does not imply a free call. Record every
attempt with one of:

- `known` — the provider or Genblaze returned an actual cost;
- `estimated` — actual cost was unavailable, so record the registry estimate and mark it;
- `unknown` — neither is defensible.

Never silently write zero for a failed attempt. Dara's cost-per-approved-asset claim
depends on preserving the cost and uncertainty of work that did not ship.
