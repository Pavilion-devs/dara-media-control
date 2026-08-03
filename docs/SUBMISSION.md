# SUBMISSION

Deadline **Aug 3 2026, 5:00pm EDT**. Judging Aug 5–11. Winners on or around Aug 12.

## Required by the rules

- [x] Working app URL a judge can access, test, and evaluate
- [x] Public repo, or private with access granted to the Backblaze testing account
- [x] Setup instructions in the README
- [x] Text description: features, how B2 is used, how Genblaze is used
- [x] **Explicit list of AI providers and models** — generated in
      `docs/MODELS_USED.md` and incorporated into `docs/DEVPOST.md`
- [ ] Demo video under 3 minutes, public on YouTube, no third-party trademarks or
      copyrighted music
- [x] No test account required anywhere in Dara. Exact route-by-route instructions
      and anonymous spend controls are in `docs/JUDGE_ACCESS.md`.
- [x] Optional but do it: SDK feedback as GitHub issues on the Genblaze repo

The app must stay free, unrestricted, and reachable until judging ends on Aug 11. Do not
redeploy after submitting.

## Demo video — beat sheet

Target 2:45. Judges are not required to watch past three minutes and many will decide in
the first thirty seconds. No intro card, no logo animation, no "hi, my name is."

| Time | Beat | On screen |
|---|---|---|
| 0:00–0:12 | **The problem, concretely.** "A team generates four thousand assets a month across five providers. Ask them what any one of them cost, or how to make it again, and there's no answer." | Ledger screen, populated, real numbers |
| 0:12–0:25 | **What Dara is.** One sentence: governed pipelines, verifiable provenance, a spend ledger. | Studio screen |
| 0:25–0:50 | **Govern.** Select the locked policy and an incompatible request. Show the live reservation becoming a zero-spend block. Say the words: "no provider was called." | Studio, policy block state |
| 0:50–1:15 | **Generate.** Switch to Standard, show the live estimate and the two confirmations, then cut cleanly from the submitted job to its real completed state. Do not make the viewer wait through provider latency. | Studio, event stream, published asset |
| 1:15–1:40 | **Orchestrate.** Filter Runs by `Fallback`, open a genuine B2 record, and show the provider failover plus version tree. Then point to the `QA revised`, motion, and voice evidence filters. | Runs, live evidence badges and event stream |
| 1:40–2:10 | **Verify — the money shot.** Download the published embedded asset. Drop it into the public verify page: its whole-file hash matches the trusted `published_sha256` in B2 and full lineage renders. Then flip one byte and drop the copy again: the trusted comparison diverges visibly. Do not imply that Genblaze's pre-embed `asset.sha256` is the whole-file hash of the embedded derivative. | Verify page, both states |
| 2:10–2:35 | **The B2 story.** Show the one-run architecture and bucket layout: Genblaze-bound sources, exact embedded deliverables, manifests, immutable Parquet, and job state. Show DuckDB querying the Parquet in place. "No database. One bucket." | Architecture docs, B2 console, Ledger |
| 2:35–2:50 | **Close.** Cost per approved asset and spend prevented, on screen. No sign-off, no thanks. | Ledger headline numbers |

Production notes:

- Screen recording at 1080p minimum, cursor visible, UI at a readable zoom.
- Every product surface shown must be live API/B2 data. Use a clean edit between a real
  submitted job and its completed state rather than making the viewer wait through
  provider latency. Existing fallback and revision evidence must be shown from genuine
  B2 records, never fixtures.
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
| **Use of Genblaze** | `api/dara/pipelines/`, `api/dara/verify.py`, `api/dara/share.py`, live Runs evidence filters | Multi-step DAG execution, `input_from` fan-in, `fallback_models`, `AgentLoop`, `parent_run_id` lineage, `ObjectStorageSink` + `ParquetSink`, `EmbedPolicy` redaction, manifest embed/extract/verify, `ModelRegistry` pricing customisation, `astream()`, manifest-driven regeneration, `LoggingTracer` |

## Devpost description

Sections, in this order:

**What it does** — the problem paragraph, then the four pillars, one sentence each.

**How it uses Backblaze B2** — be specific and quantitative. Name the source and published
asset roles, hierarchical Genblaze writes plus Dara's content-addressed copies, manifests
and app state, and the
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

- [x] Open the app in a private window, no session, from a phone. Verified Studio,
      Ledger, Verify, and a live B2 asset in a clean 390×844 browser viewport on
      2026-07-30: no sign-in wall, horizontal overflow, warnings, or errors.
- [x] Clone the repo to a fresh directory and follow your own README exactly. Verified
      anonymously from public commit `1cb5b13` on 2026-07-29.
- [ ] Video is public, not unlisted, and plays without sign-in.
- [ ] Every link in the submission resolves.
- [x] Repo access granted to the Backblaze testing account if private. Not applicable:
      the repository is public and was cloned without authentication.
- [x] Studio is live-first; fixture evidence is restricted to automated tests.
- [x] Spend cap is active.
- [x] Nobody can reach a judge-path screen that requires a key they do not have.
- [ ] Submit. Then stop deploying.
