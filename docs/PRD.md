# PRD — Dara

## One line

Dara is the control plane for AI-generated media: governed pipelines, verifiable
provenance, and a queryable spend ledger, built on Genblaze and Backblaze B2.

## The problem

A creative team running generation across four or five model providers accumulates
thousands of assets a month and has no system of record for any of it. Concretely,
they cannot answer:

- **Attribution.** Which model produced this asset, with what prompt and parameters?
- **Cost.** What did this asset cost, including the seven attempts that were thrown
  away, and which client does it bill to?
- **Reproducibility.** The client wants a variant of the hero image from March. Can we
  reproduce the original conditions, or do we start over?
- **Disclosure.** The client's legal team wants a record of what was AI-generated. What
  do we hand them that does not also hand them our prompt library?
- **Control.** An intern kicked off a batch against the most expensive video model. How
  would we have stopped that before it happened rather than after the invoice?

Today these are answered by Slack search, a spreadsheet someone stopped updating, and
hope. The generation tooling is excellent and the operational layer under it does not
exist.

## Positioning — read this before writing any marketing copy

Dara is **not** an anti-deepfake or adversarial-authenticity product. Genblaze's manifest
is tamper-evident in trusted storage; its own documentation recommends pairing it with a
signer or C2PA when adversarial verification matters. Any claim that Dara proves
authenticity to a hostile third party is false, and the hackathon judges are the people
who wrote that caveat.

The defensible claim, and the one that matches a real buyer:

> Dara gives a team internal accountability and reproducibility over its own generated
> media, and gives that team's clients a disclosure record they can check.

Trust boundary: the manifest is authoritative **within** an org that controls its own B2
bucket, and is a good-faith disclosure artifact **outside** it. Say exactly that in the
README and the demo. Precision here reads as competence.

## Users

**Primary — creative operations lead at a small agency or in-house brand studio.**
Runs or oversees generation for multiple clients. Accountable for spend and for what
gets delivered. Wants guardrails that work before the money is gone, and an audit trail
they did not have to assemble by hand.

**Secondary — the producer or designer generating the work.** Wants the QA loop to stop
handing them obviously broken outputs, and wants to find the March hero image and its
exact settings in under thirty seconds.

**Tertiary — the client receiving the work.** Gets a share link showing what was
generated and how, without seeing the prompt engineering.

## The four pillars

### 1. Verify

Public, no-authentication page. Drop in any file. Dara extracts the embedded manifest,
verifies its canonical hash, resolves the manifest's run and asset against Dara's trusted
B2 record, and compares the uploaded bytes with the `published_sha256` recorded when the
embedded deliverable was published. `Manifest.verify_hash()` checks canonical manifest
integrity; `Manifest.verify()` additionally requires declared source SHA coverage, but
neither replaces the whole-file published comparison. Dara then renders the full lineage:
provider, model, prompt (if not redacted), parameters, timestamps, cost, and parent runs.

This distinction is required by Genblaze's embedding model: `asset.sha256` covers the
upstream bytes before a manifest is embedded, while embedding changes the file bytes.
Dara therefore records both hashes — `source_sha256` for the Genblaze-bound original and
`published_sha256` for the exact embedded file a client receives. Manifest verification
is necessary but not sufficient for uploaded-file integrity because it does not fetch
and rehash media bytes.

If no manifest is embedded, Dara hashes the file and resolves
`index/sha/{sha}.json`, reporting the match honestly as `matched-by-hash` rather than
`embedded`. An embedded manifest with no corresponding trusted B2 record is reported as
`self-consistent`, not as verified or tampered.

Requires no provider call and works when generation providers are unavailable. Give B2
lookups a bounded timeout: if trusted storage is unavailable but an embedded manifest can
be extracted, report only `self-consistent` with a storage warning. A hash-only lookup
cannot be classified without B2 and returns a retryable storage error rather than
incorrectly reporting `unknown`. This is why Verify is built first.

### 2. Govern

Policies are declarative documents attached to a project. They constrain allowed
providers and models, maximum spend per step and per run, maximum step count, required
QA score, permitted modalities and durations, retention, and whether the manifest is
redacted on publish.

Enforcement happens at four points, the first of which is **before any provider is
called** — cost is estimated from the Genblaze `ModelRegistry` and compared to budget.
A run that would exceed budget is rejected at zero cost.

This is the pillar most likely to be unique in the field. Details in `POLICY_ENGINE.md`.

### 3. Generate

Three pipeline templates, each a multi-step Genblaze `Pipeline` with provider fallback
chains and an agentic QA loop that scores output against a rubric and retries with a
refined prompt until it passes or exhausts its attempt budget. Every attempt — including
failures — is preserved and linked by `parent_run_id`, so the version tree shows the
real history rather than a sanitised one.

### 4. Account

`ParquetSink` writes run, step, and asset tables to a per-job local staging directory.
Dara uploads each completed Parquet file to an immutable, partitioned key in B2; DuckDB
then queries that Parquet **in place** over the B2 S3 endpoint. The ledger answers spend
by model, by project, by month, and the number nobody tracks: cost per approved asset
including discarded and failed attempts.

## Feature list

| Feature | Pillar | Priority |
|---|---|---|
| Public file verification with hash diff | Verify | P0 |
| Content-address lookup fallback | Verify | P0 |
| Policy documents with 4-point enforcement | Govern | P0 |
| Pre-flight cost estimation and rejection | Govern | P0 |
| `still-campaign` pipeline | Generate | P0 |
| Agentic QA loop with revision | Generate | P0 |
| Live step streaming (SSE) | Generate | P0 |
| Version tree with failed attempts | Generate | P0 |
| DuckDB ledger over B2 Parquet | Account | P0 |
| Live-first public control plane with two-step spend confirmation | — | P0 |
| Regeneration from manifest | Verify | P1 |
| Regeneration visual diff | Verify | P1 |
| `motion-spot` pipeline | Generate | P1 |
| Redacted client share links | Verify | P1 |
| `voiceover-pack` pipeline | Generate | P2 |

## Non-goals

Explicitly out of scope. Say so in the README — stated non-goals read as judgment, not
as gaps.

- User signup, org management, roles, permissions. One demo workspace; `tenant_id` is
  threaded through the data model so multi-tenancy is a deployment concern, not a rewrite.
- Payments and billing.
- A timeline or node editor. Dara governs generation; it does not replace an NLE.
- Model hosting or fine-tuning.
- Mobile app. The web app is responsive; that is the extent of it.
- Adversarial authenticity, C2PA signing, watermark detection. Named as a future
  direction, not claimed as a capability.

## Success criteria for the submission

- A judge with no context reaches a working, populated app in under 15 seconds.
- The verify demo works offline of any provider and cannot fail live.
- A policy violation is demonstrably blocked before spend.
- The README maps every judging criterion to specific files.
- Total live API spend across the whole judging period stays under $20.
