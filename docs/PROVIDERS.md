# PROVIDERS

## Context

GMI Cloud hackathon credits are exhausted, so every live call must be deliberately
budgeted. Dara uses the official `genblaze-openai` adapter as its primary provider:
GPT Image for images, Sora for video, and OpenAI TTS for speech. The first
`gpt-image-2` run has already completed and persisted successfully to B2.

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

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | openai | `gpt-image-2` | Primary; live B2 proof is green |
| 2 | openai | `gpt-image-1-mini` | Lower-cost same-provider degradation |
| 3 | replicate or google | To be measured | Provider-diverse fallback, added only after a real probe |

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
| 1 | openai | `gpt-4o-mini-tts` | Primary candidate using the existing key |
| 2 | elevenlabs | To be measured | Provider-diverse voice fallback |
| 3 | — | no narration | Graceful degradation for motion output |

### Chat — prompt expansion and QA scoring

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | openai | Vision-capable current model | Reuse the existing key; exact model and price must be registered |
| 2 | anthropic | Claude, optional custom evaluator | QA only; not a Genblaze media provider |
| 3 | — | deterministic checks | Dimensions, format, file integrity, and manifest verification |

## Cost table

**Fill this in from measurement, not from documentation.** These feed `ModelRegistry`
pricing and therefore every estimate, every budget check, and every ledger figure. Wrong
numbers here make the whole governance layer wrong.

| Provider | Model | Modality | Unit | Price USD | p50 latency | Measured |
|---|---|---|---|---|---|---|
| openai | gpt-image-2 | image | per image | pending registry | 29.369s | ☑ one low-quality 1024² run |
| openai | gpt-image-1-mini | image | per image | | | ☐ |
| openai | sora-2 | video | per second | | | ☐ |
| openai | gpt-4o-mini-tts | audio | per 1k chars | | | ☐ |
| openai | vision QA model TBD | chat/vision | per 1k tokens | | | ☐ |
| provider-diverse fallback | TBD | image/video | TBD | | | ☐ |

Register these via `ModelRegistry.fork()` + `register_pricing()`. Where a model has no
published price, register a conservative estimate and flag it `UNPRICED_MODEL` in the UI
rather than silently reporting zero. A ledger that quietly under-reports is worse than one
that admits uncertainty.

## Model id verification

Model identifiers drift, and a wrong id fails at runtime on demo day. Before building any
pipeline:

```bash
python -m dara.tools.probe_models --provider openai --modality image
```

Write this probe as task T-09. It should attempt a minimal generation against each
candidate id, record success, latency, and cost, and emit a table. Run it again on Day 5
before recording the video — catalogs change.

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
