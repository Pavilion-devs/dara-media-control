# SUBMISSION

Deadline **Aug 3 2026, 5:00pm EDT**. Judging Aug 5–11. Winners on or around Aug 12.

## Required by the rules

- [ ] Working app URL a judge can access, test, and evaluate
- [ ] Public repo, or private with access granted to the Backblaze testing account
- [ ] Setup instructions in the README
- [ ] Text description: features, how B2 is used, how Genblaze is used
- [ ] **Explicit list of AI providers and models** — generate it from the registry
- [ ] Demo video under 3 minutes, public on YouTube, no third-party trademarks or
      copyrighted music
- [ ] Test account with login instructions if anything is gated
- [ ] Optional but do it: SDK feedback as GitHub issues on the Genblaze repo

The app must stay free, unrestricted, and reachable until judging ends on Aug 11. Do not
redeploy after submitting.

## Demo video — beat sheet

Target 2:45. Judges are not required to watch past three minutes and many will decide in
the first thirty seconds. No intro card, no logo animation, no "hi, my name is."

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:12 | **The problem, concretely.** "A team generates four thousand assets a month across five providers. Ask them what any one of them cost, or how to make it again, and there's no answer." | Ledger screen, populated, real numbers |
| 0:12–0:25 | **What Dara is.** One sentence: governed pipelines, verifiable provenance, a spend ledger. | Studio screen |
| 0:25–1:00 | **Generate.** Submit a brief. Live estimate updates before committing. Step stream runs. A `step.failover` fires and the fallback catches it. QA scores below threshold, revises the prompt, second attempt passes. | Studio, step stream, version tree |
| 1:00–1:25 | **Govern.** Switch to the locked policy. Submit the same brief. Blocked, with the reason and the cost that was not spent. Say the words: "no provider was called." | Studio, policy block state |
| 1:25–2:00 | **Verify — the money shot.** Download the published embedded asset. Drop it into the public verify page: its whole-file hash matches the trusted `published_sha256` in B2 and full lineage renders. Then flip one byte and drop it again: the trusted comparison diverges visibly. Do not imply that Genblaze's pre-embed `asset.sha256` is the whole-file hash of the embedded derivative. | Verify page, both states |
| 2:00–2:20 | **Regenerate.** Open an asset from March in the ledger, hit regenerate, show the reconstructed parameters and the side-by-side. | Asset detail |
| 2:20–2:40 | **The B2 story.** Bucket layout on screen: Genblaze-bound source assets, exact embedded deliverables, manifests, immutable Parquet partitions, and job state. Show one local `ParquetSink` output uploaded to B2, then DuckDB querying it in place. "No database. One bucket." | B2 console, ledger |
| 2:40–2:50 | **Close.** Cost per approved asset and spend prevented, on screen. No sign-off, no thanks. | Ledger headline numbers |

Production notes:

- Screen recording at 1080p minimum, cursor visible, UI at a readable zoom.
- Record against **seeded runs**, not live provider calls. A timeout on camera is fatal.
- Voiceover written and read, not improvised. Write the script, time it, then record.
- No copyrighted music. Silence with clear narration beats a licensing problem.
- Show real numbers. Placeholder or obviously fake data undercuts everything.

## README structure

The README is scored. Write it for someone reading twenty of them.

1. **One line** — what Dara is
2. **The problem** — three sentences, concrete
3. **Live demo + test account**
4. **60-second tour** — three screenshots with captions
5. **How this maps to the judging criteria** — the table below
6. **Architecture** — the diagram plus the one-bucket claim
7. **Providers and models used** — from `MODELS_USED.md`
8. **Setup** — clone, env, run, verified from a clean machine
9. **What we learned about Genblaze** — links to the issues filed
10. **Honest limitations** — the trust boundary, non-determinism in regeneration,
    last-write-wins on concurrent job updates

### Criteria mapping table

Put this near the top. Fill in real paths and line numbers before submitting.

| Criterion | Where | What to look at |
|---|---|---|
| **Real-world utility** | `docs/PRD.md` | Named buyer, five concrete unanswerable questions Dara answers. Verify and ledger work without any generation happening. |
| **Production readiness** | `api/dara/policy/`, `api/dara/jobs.py`, `api/dara/providers.py` | Pre-spend policy enforcement, fallback chains on every step, orphaned-run reconciler, typed error model, rate limits, spend caps, tests asserting a blocked run makes zero provider calls |
| **B2 storage + data orchestration** | `api/dara/storage.py`, `api/dara/ledger.py`, `docs/DATA_MODEL.md` | Single bucket as the entire persistence layer. Source and published content-addressed objects preserve both Genblaze binding and exact delivered bytes. Locally staged `ParquetSink` telemetry is uploaded as immutable B2 partitions and queried in place by DuckDB. Job state, policies, projects, shares all live as objects. |
| **Use of Genblaze** | `api/dara/pipelines/`, `api/dara/verify.py`, `api/dara/share.py` | Multi-step chaining, `input_from` fan-in, `fallback_models`, `AgentLoop`, `parent_run_id` lineage, `ObjectStorageSink` + `ParquetSink`, `EmbedPolicy` redaction, manifest embed/extract/verify, `ModelRegistry` pricing customisation, `astream()`, replay-based regeneration, `LoggingTracer` |

## Devpost description

Sections, in this order:

**What it does** — the problem paragraph, then the four pillars, one sentence each.

**How it uses Backblaze B2** — be specific and quantitative. Name the source and published
asset roles, both key strategies, manifests and app state, and the
local-Parquet → immutable-B2-upload → DuckDB query path. Say plainly that there is no
other datastore. Include the bucket layout.

**How it uses Genblaze** — the full primitive list. Do not be modest; this is a scored
question and vagueness reads as shallow integration.

**Providers and models** — the generated table.

**What we'd build next** — C2PA signing for adversarial verification, webhook sinks for
CI integration, multi-tenant auth. Naming what you deliberately did not build shows you
understood the boundary.

## SDK feedback — Feedback Prize

Ten winners, stacks with an overall prize, evaluated on completeness, viability, and
potential impact. File 3–5 issues from `docs/SDK_FEEDBACK.md`, and file them **during**
the build, not on submission day.

What makes a good issue here:

- A bug with the exact traceback, installed version, and a minimal reproduction
- A missing parameter you needed and the workaround you used
- A documented feature that does not match installed behaviour
- A concrete feature request with the use case that motivated it — for example, policy or
  budget hooks in the pipeline lifecycle, which is exactly what Dara had to build on top

Not: "great SDK, add more models."

## Final checks — Aug 2

- [ ] Open the app in a private window, no session, from a phone. Does it work?
- [ ] Clone the repo to a fresh directory and follow your own README exactly.
- [ ] Video is public, not unlisted, and plays without sign-in.
- [ ] Every link in the submission resolves.
- [ ] Repo access granted to the Backblaze testing account if private.
- [ ] Demo mode is the default landing state.
- [ ] Spend cap is active.
- [ ] Nobody can reach a screen that requires a key they do not have.
- [ ] Submit. Then stop deploying.
