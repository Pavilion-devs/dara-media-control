# PIPELINES

Three templates. Each is a Genblaze `Pipeline` with fallback chains, a QA loop, and both
sinks attached.

> **Before implementing:** confirm every Genblaze symbol used here exists in the installed
> version (`AGENTS.md`, T-06). Where reality differs from this spec, follow reality and
> record the gap in `docs/SDK_FEEDBACK.md`.

## Shared setup

```python
from genblaze_core import (
    Pipeline, Modality, ObjectStorageSink, ParquetSink, KeyStrategy, LoggingTracer,
)
from genblaze_s3 import S3StorageBackend

def build_sink(job_id: str) -> ObjectStorageSink:
    return ObjectStorageSink(
        S3StorageBackend.for_backblaze(settings.b2_bucket),
        key_strategy=KeyStrategy.HIERARCHICAL,
        parquet_sink=ParquetSink(settings.parquet_staging_dir / job_id),
    )
```

`ParquetSink` writes locally. After a run completes and the sink closes, upload each
generated table to an immutable partitioned B2 key under `ledger/`, then remove that
job's staging directory. Never treat `ParquetSink("ledger/")` as an S3 destination and
never overwrite a shared monthly Parquet object.

Construct a fresh `ObjectStorageSink` per run; Genblaze closes it after the run. After
the hierarchical write succeeds, use the storage backend's server-side `copy()` to write
each source asset to its content-addressable key and drop an
`index/sha/{source_sha256}.json` pointer. Do not reuse the closed sink or run the result
through a second sink. Both source layouts must exist — `DATA_MODEL.md` explains why.
Publish is a separate byte transition: embed into a derivative, compute
`published_sha256`, store it under `published/`, and index that hash without overwriting
the source.

Attach `LoggingTracer` to every pipeline. Observability is explicitly named in the
Genblaze feature set and it costs one line.

## Genblaze surface to exercise

Track these. Breadth is scored, and each is small.

- [ ] `Pipeline(chain=True)` multi-step chaining
- [x] `input_from` fan-in (audio + video → composite)
- [x] `fallback_models=[...]` on every generative step
- [x] `AgentLoop` for QA refinement
- [x] `from_result()` / `parent_run_id` lineage
- [ ] `ObjectStorageSink` with both key strategies
- [x] `ParquetSink`
- [ ] `EmbedPolicy` for redacted shares
- [x] `Mp4Handler` / image handler `embed()` and `extract()`
- [x] `manifest.verify()`
- [x] `ModelRegistry.fork()` + `register_pricing()` + `register(ModelSpec(...))`
- [x] `chat()` for prompt expansion and QA scoring
- [x] `astream()` for live step events
- [x] `arun()` / `abatch_run()` for variants
- [x] `genblaze replay` semantics for regeneration
- [x] `LoggingTracer`

## P1 — `still-campaign` (P0, build first)

Brief → expanded prompt → N image variants → QA scoring → best variant approved.

```
chat(expand)  →  image × variants  →  qa.score  →  [revise → image]*  →  publish
```

| Step | Provider chain | Notes |
|---|---|---|
| expand | google gemini → nvidia nemotron | Turns a one-line brief into a full prompt with style, lighting, composition. Returns JSON. |
| image | nvidia `flux.1-dev` → nvidia `sd3.5-large` → replicate `flux-schnell` | `fallback_models` in this order. Confirm real model ids in T-09. |
| qa | google gemini (vision) → nvidia nemotron | See QA loop below |
| publish | — | Embed and validate a local candidate, run `PRE_PUBLISH`, then store under `published/` and index both hashes |

Variants run through `abatch_run()` where the SDK supports it — parallel variants are both
faster and a better use of the async API than a loop.

## P2 — `motion-spot` (P1)

Brief → keyframe image → image-to-video → narration → composite.

```
chat(expand) → image(keyframe) → video(image2video) → audio(tts) → composite → publish
                                          ↘                    ↗
                                           input_from fan-in
```

| Step | Provider chain | Notes |
|---|---|---|
| keyframe | OpenAI `gpt-image-2` → dated `gpt-image-2` snapshot | Reuses the central image route and registry |
| video | OpenAI `sora-2` → `sora-2-pro` | Fixed at 4s / 720p. Video is the expensive and slow step; the policy engine must gate it. |
| narration | OpenAI `tts-1` → `tts-1-hd` | Script comes from the expanded brief |
| composite | Genblaze `FFmpegCompositor` | Real `input_from=[video, audio]` fan-in, exercised with FFmpeg |

Video is where the demo breaks if you are careless. Hard per-step timeout, guaranteed
fallback to a still, and pre-generated seeds so the demo never depends on a live video
call succeeding.

## P3 — `voiceover-pack` (P2, first to cut)

Script → N voices in parallel → publish as a set. Cheap, fast, reliable — a good filler
if video proves unworkable.

Implemented as a single-step OpenAI `tts-1` → `tts-1-hd` pipeline expanded by
`abatch_run(items=...)`. Each item overrides `voice`, receives an ordered pack index,
and runs under a bounded concurrency semaphore. The regression uses a thread-safe mock
provider to prove at least two variants overlap and verifies every resulting manifest.

## P4 — `regenerate` (P1)

Not a template. Takes an existing Dara `job_id`, loads its Genblaze manifest,
reconstructs the canonical parameters, and re-runs the same pipeline. The Dara job is
linked by `parent_job_id`; the Genblaze run is linked by `parent_run_id`.

```python
async def regenerate(job_id: str) -> Job:
    original_job = await load_job(job_id)
    manifest = await load_manifest(original_job.genblaze_run_id)
    spec = pipeline_spec_from_manifest(manifest)   # canonical params round-trip
    # policy still applies — a regeneration can breach a budget that has since tightened
    decision = policy.evaluate(PRE_FLIGHT, spec, policy_for(spec.project_id))
    ...
    result = Pipeline(spec.pipeline_id).from_result(original_result).step(...).run(sink=...)
```

Then diff: original vs regenerated, side by side, plus a parameter diff table showing what
matched and what drifted. Note honestly in the UI that most media models are not
bit-deterministic — the claim is **reproducible conditions**, not identical bytes.
Overclaiming determinism here fails the same way overclaiming adversarial provenance does.

## The QA loop

```python
QA_RUBRIC = """
You are reviewing an AI-generated asset against a creative brief.
Score each dimension 0.0-1.0 and return ONLY valid JSON, no markdown fences:

{
  "prompt_adherence": 0.0,   // does it show what was asked for
  "technical_quality": 0.0,  // artifacts, distortion, malformed detail
  "brand_fit": 0.0,          // matches the stated brand guidance
  "usable_as_is": 0.0,       // would a producer ship this without retouching
  "overall": 0.0,            // weighted judgement, not a mean
  "issues": ["..."],         // concrete and specific, not "could be better"
  "revised_prompt": "..."    // full replacement prompt addressing the issues
}
"""
```

Loop:

1. Generate.
2. Score against the rubric with a vision-capable `chat()` call.
3. `overall >= min_qa_score` → approve, exit.
4. Below threshold and attempts remain → new run via `from_result()` with
   `revised_prompt`, linked by `parent_run_id`. Emit `qa.revised`.
5. Attempts exhausted → finish unapproved, keep every attempt, surface the best score.

Implementation notes that matter:

- **Persist every attempt, including failures.** The version tree showing a real failure
  and its successful revision is far more convincing than three successes in a row.
- **Parse defensively.** Strip markdown fences, retry once with a stricter instruction on
  parse failure, then fall back to a neutral score and a `qa.parse_failed` event rather
  than crashing the run.
- **The evaluator is a cost.** It counts toward the run budget and must appear in the
  estimate.
- Make the rubric visible in the UI. A judge seeing the actual scoring criteria
  understands immediately that the loop is real and not a `sleep()`.

## Model registry and pricing

```python
def registry_for(provider: str) -> ModelRegistry:
    reg = PROVIDER_DEFAULTS[provider].models_default().fork()
    for model_id, price in PRICING[provider].items():
        reg.register_pricing(model_id, per_unit(price))
    for spec in EXTRA_MODELS.get(provider, []):
        reg.register(spec)
    return reg
```

Keep real prices in `docs/PROVIDERS.md` and load them from one place. Convert registry
outputs to `Decimal` at Dara's boundary and serialise six-place decimal strings. Accurate
cost display is what makes the ledger credible, and registry customisation is an explicit
Genblaze feature — using it is worth saying out loud in the README.

## Streaming

Use `astream()` where available; otherwise wrap `arun()` and emit events at step
boundaries. Every event goes to both the SSE channel and the persisted job record — same
shape, one code path (`DATA_MODEL.md`, `StepEvent`).

Judges watch the step stream. Make sure `step.failover` and `qa.revised` are visually
distinct — those two events are the product demonstrating itself.
