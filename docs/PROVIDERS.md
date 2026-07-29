# PROVIDERS

## Context

GMI Cloud hackathon credits are exhausted, so there is no sponsor-funded generation
budget. Every call is either free-tier or out of pocket. This shapes provider selection
and it shapes the demo.

The good news: NVIDIA NIM is a first-class Genblaze adapter (`genblaze-nvidia`) covering
**every modality** — Cosmos for video, SDXL / SD 3.5 / FLUX for image, Fugatto and Riva
for audio, Nemotron for chat. It scores identically to GMI on the Genblaze criterion.

## Credit strategy — do this first

1. Join the free NVIDIA Developer Program at build.nvidia.com and generate an `nvapi-`
   key. Signup grants 1,000 API credits with no credit card.
2. Request more from the profile menu. **Use a business-style email address** — a personal
   address caps you, while a business address activates a free 90-day AI Enterprise
   license and unlocks an additional 4,000 credits, for 5,000 total.
3. Note the terms: the hosted free tier is for development, evaluation, and prototyping.
   A hackathon demo sits inside that. Do not build a public production service on it, and
   do not claim you have.
4. Some catalog models are free and consume no credits at all. Check current model pages
   and prefer those for the QA evaluator, which runs on every attempt and is your highest
   call-volume step.

Secondary keys, all free tier: Google AI Studio (Gemini, for vision-capable QA scoring),
ElevenLabs (voice), Replicate (cheap per-call image overflow, pay-as-you-go).

Budget the whole event at **under $20 of real spend.** If you are heading past that,
something is wrong with demo mode.

## Fallback chains

Every generative step declares `fallback_models`. Order is by cost ascending, then
reliability. Fill in the reliability column from T-09 once you have measured, and
reorder — measured latency beats assumption.

### Image

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | nvidia | FLUX.1 dev | Primary. Quality-to-cost leader on the catalog. |
| 2 | nvidia | SD 3.5 large | Same key, different family — survives a single-model outage |
| 3 | replicate | flux-schnell | Paid but cheap; the safety net when NIM credits run dry |

### Video

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | nvidia | Cosmos (text2world / video2world) | Cap 5s, 720p. Expensive and slow — gate with policy. |
| 2 | replicate | image-to-video model | Fallback |
| 3 | — | still fallback | If both fail, degrade to the keyframe still and say so in the UI |

Video is the highest-risk path in the project. Treat the still fallback as a real feature,
not an error state — graceful degradation is a production-readiness signal.

### Audio

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | elevenlabs | eleven_v3 | Best quality, free tier is limited |
| 2 | nvidia | Riva TTS | Same key as everything else |
| 3 | nvidia | Fugatto | Sound effects and music beds |

### Chat — prompt expansion and QA scoring

| Rank | Provider | Model | Notes |
|---|---|---|---|
| 1 | google | Gemini (vision-capable) | Needed for image QA — the evaluator must actually see the asset |
| 2 | nvidia | Nemotron | Text-only fallback; degrade QA to prompt-adherence-only and say so |
| 3 | nvidia | a free-tier catalog model | Zero-credit option for high-volume scoring |

## Cost table

**Fill this in from measurement, not from documentation.** These feed `ModelRegistry`
pricing and therefore every estimate, every budget check, and every ledger figure. Wrong
numbers here make the whole governance layer wrong.

| Provider | Model | Modality | Unit | Price USD | p50 latency | Measured |
|---|---|---|---|---|---|---|
| nvidia | flux.1-dev | image | per image | | | ☐ |
| nvidia | sd3.5-large | image | per image | | | ☐ |
| nvidia | cosmos | video | per second | | | ☐ |
| nvidia | riva-tts | audio | per 1k chars | | | ☐ |
| nvidia | nemotron | chat | per 1k tokens | | | ☐ |
| google | gemini | chat/vision | per 1k tokens | | | ☐ |
| replicate | flux-schnell | image | per image | | | ☐ |
| elevenlabs | eleven_v3 | audio | per 1k chars | | | ☐ |

Register these via `ModelRegistry.fork()` + `register_pricing()`. Where a model has no
published price, register a conservative estimate and flag it `UNPRICED_MODEL` in the UI
rather than silently reporting zero. A ledger that quietly under-reports is worse than one
that admits uncertainty.

## Model id verification

Model identifiers drift, and a wrong id fails at runtime on demo day. Before building any
pipeline:

```bash
python -m dara.tools.probe_models --provider nvidia --modality image
```

Write this probe as task T-09. It should attempt a minimal generation against each
candidate id, record success, latency, and cost, and emit a table. Run it again on Day 5
before recording the video — catalogs change.

Genblaze ships `probe_models` for conformance checking; use it if the installed version
exposes it rather than writing your own.

## Rate limits and 429s

NVIDIA's free tier is rate-limited and the per-model ceiling is not published — you
discover your own limit in your account. Assume you will hit it during seeding.

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
