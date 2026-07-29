# FRONTEND SPEC

Next.js 15 App Router, TypeScript strict, Tailwind. Five routes. Ambition lives in the
Python layer; the UI's job is to make the system legible in under thirty seconds.

## Design direction

**Subject grounding.** Dara's world is not "creative AI tool." It is the production
ledger, the film lab report, the chain-of-custody form, the contact sheet. Dara's real
content is hashes, model ids, parameters, timestamps, and money. So the design treats
that data as the subject rather than hiding it behind cards and gradients.

The deliberate risk: **the SHA-256 is the hero element, rendered at display size.** Most
products hide hashes in a tooltip. Dara puts a 64-character hash across the top of the
asset detail page, grouped in blocks of eight, and uses it as the primary visual signature.
It is the one thing a person will remember about the interface.

**What this is not:** not cream-and-serif with a terracotta accent, not near-black with
one acid accent, not a hairline-ruled broadsheet grid. Cool, technical, dense, printed.

### Tokens

```css
--ink:        #14181C;   /* near-black, cool — text and dark surfaces */
--slate:      #3A444F;   /* secondary text */
--graphite:   #6B7684;   /* tertiary, metadata */
--paper:      #F2F4F3;   /* page background — cool off-white, never cream */
--card:       #FFFFFF;
--rule:       #D8DEDC;   /* hairlines, table borders */
--verified:   #2E7D5B;   /* deep green — verified, approved */
--blocked:    #B03A2E;   /* brick red — policy block, tamper */
--pending:    #C97A16;   /* amber — running, needs review */
--active:     #1F5F8B;   /* slate blue — links, active state */
```

Semantic only. A colour never appears for decoration. Three states carry colour —
verified, blocked, pending — and everything else is ink on paper.

Dark mode: invert surfaces to `--ink` / `#1C222A`, keep the three semantic hues, lighten
them one step for contrast. Ship it; judges browse at night.

### Type

| Role | Face | Use |
|---|---|---|
| Display | **Archivo** 500/600, tight tracking | Page titles, the hash hero, section heads |
| Body | **Inter** 400/500 | Prose, labels, buttons |
| Data | **IBM Plex Mono** 400/500 | Every hash, id, model name, parameter, timestamp, money |

The mono/sans split is the load-bearing typographic decision: anything the system
generated or recorded is mono, anything a human wrote is sans. It makes provenance legible
at a glance without a single icon.

Scale: 12 / 14 / 16 / 20 / 28 / 44. Sentence case everywhere. No text below 12px.

### Structure

- 8px spacing base. Dense but not cramped: 16px inside cards, 24px between sections.
- 2px radius on controls, 0 on data tables. Tables are tables.
- Hairline rules at `--rule`, 1px, used to separate data rows — not as decoration.
- Numbering only where order is real: pipeline steps and lineage generations are
  sequences, so they get numbers. Nothing else does.
- Motion: state transitions only. Step events arrive with a 120ms fade-and-rise. A
  policy block gets one 200ms shake. Nothing ambient, nothing looping. Respect
  `prefers-reduced-motion`.

## Routes

### `/` — Studio

Landing. Must be immediately populated in demo mode.

Layout: left column brief form (⅓), right column live run (⅔).

**Brief form.** Project select, pipeline select, prompt textarea, aspect ratio,
variant count, brand notes, policy select.

Below the form, always visible: **the live estimate.** As inputs change, call
`/v1/policies/{id}/simulate` (debounced 400ms) and show expected cost, worst case, and
any violations *before the person commits*. If the current configuration would be
blocked, the submit button is disabled and states the reason. Governance visible at the
point of decision, not after.

**Run panel.** The SSE step stream. Each event is a mono row: sequence number, elapsed
time, provider, model, message. Two event types are styled distinctly:

- `step.failover` — amber, with the from-model struck through and the to-model beside it.
- `qa.revised` — a nested block showing the score breakdown, the specific issues, and the
  revised prompt. The rubric is visible; that is what proves the loop is real.

On completion: variant grid, QA score per variant, approve action.

**Empty state** is a directive, not a mood: "Pick a project and describe the shot. The
estimate updates as you type."

### `/ledger` — Ledger

Three headline numbers across the top, large, mono:

1. **Cost per approved asset** — the honest one, including discarded attempts
2. **Spend prevented** — policy blocks × what they would have cost
3. **Waste ratio** — share of spend that never shipped

Then a filter bar (date range, project, model) and a dense table. Bars are inline in the
table cells rather than in a separate chart — the number and its magnitude in the same
row. If a standalone chart is needed, use one: spend by month, single series, no legend.

Every row links to its run.

### `/verify` — Verify (public, no auth)

The most important page. It must remain useful when generation providers are down.
Trusted verification still depends on the Dara API and B2; do not claim otherwise.

Single centred dropzone on `--paper`. Copy: "Drop a file to check where it came from."

**The signature moment.** On result, the uploaded file's whole-file SHA-256 renders at
28px mono, grouped in eight blocks of eight characters, across the full content width.
For an embedded deliverable this is compared with the trusted `published_sha256`, not
with Genblaze's pre-embed `asset.sha256`. Verified: `--verified`, blocks separated by
hairlines. Tampered: the matching leading characters stay ink, the first divergent
character onward turns `--blocked`, and the expected published value renders directly
beneath, aligned character-for-character. The failure is visible at a glance from across
a room, which is exactly what the demo video needs.

Below: a lineage spine. A single vertical rule down the left with a node per generation,
each showing provider, model, parameters, timestamp, and cost. Parent runs continue up
the spine. This is the design signature and it is the reason the layout is vertical rather
than a card grid.

Below that, in `--graphite`, always: the trust note. Tamper-evident within the issuing
organisation's storage; not an adversarial authenticity proof. Do not bury it and do not
soften it.

Five verification states, all designed:
- `trusted-match` — embedded manifest is internally valid and the whole-file hash matches
  the trusted published record in B2
- `trusted-mismatch` — an embedded manifest resolves to a trusted record, but the uploaded
  bytes do not match the recorded published file
- `self-consistent` — the embedded manifest validates internally but has no corresponding
  trusted Dara record. Do not label it verified or tampered.
- `matched-by-hash` — no embedded manifest, but the hash matched a known asset. Label it
  as such; do not present it as equivalent.
- `unknown` — no record. Copy: "No record of this file. It may have been generated
  elsewhere, or modified after generation." No shame, no dead end.

The API's `result` field still describes how provenance was discovered (`embedded`,
`matched-by-hash`, or `unknown`); its `verification` field carries the trust state above.

### `/share/[token]` — Client disclosure (public)

Redacted view. Asset, verification status, model and provider, timestamp. **No prompt, no
parameters.** A visible note that details were withheld by policy — the redaction is the
feature, so make it legible rather than looking like missing data. Alt text on this route
must be derived only from fields permitted by the redacted response; never reconstruct or
leak the prompt subject. The media URL must point to the token-scoped redacted derivative,
never to an ordinary published file with an unredacted embedded manifest.

### `/assets/[id]` — Asset detail

Hash hero, full lineage spine, the version tree including failed attempts, parameter
table, cost breakdown, and the regenerate action. Regeneration diff renders side by side
with a parameter diff below and an honest note that media models are not bit-deterministic
— the claim is reproducible conditions, not identical bytes.

## Components

| Component | Notes |
|---|---|
| `HashDisplay` | 8×8 grouping, three sizes, diff mode. The signature component — build it first and build it well. |
| `LineageSpine` | Vertical rule, node per generation, collapsible params |
| `StepStream` | SSE consumer, typed events, per-type rendering |
| `EstimateBar` | Live cost estimate with violation state |
| `PolicyBadge` | Allow / warn / block with violation popover |
| `VersionTree` | Attempts including failures, parent-linked |
| `LedgerTable` | Dense, sortable, inline magnitude bars |
| `TrustNote` | Reused everywhere provenance is displayed. One source of truth for that wording. |

## Data layer

- Every API call goes through Next.js route handlers under `app/api/`. The bearer token
  stays server-side. The browser never sees it.
- Zod-parse every response at the boundary. Types generated from the OpenAPI schema where
  practical, hand-written where not.
- SSE via `EventSource` against a Next.js route that proxies the FastAPI stream. Reconnect
  with `?after_seq=N`.
- No client-side state library. Server components for reads, `useState` for the run panel.

## Quality floor

Do not announce it, just meet it: responsive to 375px, visible keyboard focus on every
interactive element, `prefers-reduced-motion` respected, semantic landmarks, real `<table>`
markup for tabular data, alt text on generated assets that names the model and the prompt
subject. Lighthouse accessibility above 95.

## Copy rules

Active voice. A control names its own effect — "Run this brief," not "Submit." The action
keeps its name through the flow: the button says "Approve," the toast says "Approved."

Errors state what happened and what to do, in the interface's voice, without apology:

> This run would cost $2.40. The project limit is $2.00. Reduce variants to 2, or switch
> to a policy with a higher budget.

Never "Oops!" Never "Something went wrong."
