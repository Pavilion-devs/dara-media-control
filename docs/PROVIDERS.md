# PROVIDERS

## Context

GMI Cloud hackathon credits are exhausted, so every live call must be deliberately
budgeted. Dara uses the official `genblaze-openai` adapter as its primary provider:
GPT Image for images, Sora for video, and OpenAI TTS for speech. The first
`gpt-image-2`, Replicate FLUX, `sora-2`, and `tts-1` runs have completed and
persisted successfully to B2.

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
| 1 | openai | `gpt-image-2` | Active primary; production successes and paid rejected attempts are both accounted |
| 2 | openai | `gpt-image-2-2026-04-21` | Active snapshot fallback; confirmed present in the deployed account catalog without spending |
| 3 | replicate | `black-forest-labs/flux-1.1-pro` | Active provider-diverse fallback; paid production call persisted and verified in B2 |
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

The paid production probe was run once on 2026-07-30:

```bash
python -m dara.tools.replicate_b2_probe
```

It reported `provider=replicate`, model
`black-forest-labs/flux-1.1-pro`, 5.518 seconds, registered cost `$0.040000`, and both
manifest checks true. Run `bf796a04-4e49-4519-ae11-ab31bc54b44b` stored its manifest
and 433,331-byte PNG under `dara/probes/runs/demo/2026-07-30/` in
`dara-media-control-2026`. An independent B2 read-back matched asset SHA-256
`8d6072c64632a5cde5a920830e1c79d815d2e1bfe4dc76767177ac1aea33bf84`
exactly and revalidated both manifest checks. The production health endpoint then
reported Replicate configured.

### Video

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | openai | `sora-2` | Active primary; paid 4s production run persisted and verified in B2 |
| 2 | openai | `sora-2-pro` | Configured same-provider fallback; account catalog verified |
| 3 | — | generated still + local composite | Dara prepends the generated still to the text-to-video result; the current OpenAI organisation does not permit image-to-video/inpaint |

Video is the highest-risk path in the project. Production run
`e0ed245d-5c9f-4092-87f9-549b48f2efc1` completed in 86.652 seconds for the Sora step;
the full five-step package recorded `$0.410780` after local FFmpeg steps were reconciled
to `$0`.

### Audio

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | openai | `tts-1` | Active primary; production MP3 assets persisted and verified; $0.015 per 1K input characters |
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

Generated from durable B2 live-run records and trusted Genblaze manifests through
2026-07-31. Latency
covers the actual provider step only. OpenAI image cost is explicitly labelled as a
conservative Dara estimate because the installed Genblaze adapter does not preserve
settled image-token usage; Replicate's official-model route uses its registered
per-output price.

| Provider | Model | Modality | Samples | Success / fail | Unit cost | p50 / max latency | >90s |
|---|---|---|---|---|---|---|---|
| openai-dalle | `gpt-image-2` | image | 8 | 7 / 1 | $0.010000 estimated | 20.500s / 24.204s | no |
| openai | `gpt-4.1-mini` | vision QA | 8 | 5 / 3 | $0.005000 estimated | 8.633s / 9.100s approved calls | no |
| replicate | `black-forest-labs/flux-1.1-pro` | image | 2 | 2 / 0 | $0.040000 registered | 6.738s / 7.151s | no |
| openai-sora | `sora-2` | video | 1 | 1 / 0 | $0.100000 / output second, estimated | 86.652s / 86.652s | no |
| openai-tts | `tts-1` | audio | 11 | 11 / 0 | $0.015000 / 1K chars | 2.056s / 3.808s | no |

No active measured provider step exceeded 90 seconds. The single image failure, three
paid QA rejections, and two post-provider publication failures remain recorded rather
than being silently discarded. Deprecated image models and uncalled fallback models are
not presented as measured production calls.

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
2. The locked demonstration policy caps a run at $0.02, images only, 1:1 only,
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
