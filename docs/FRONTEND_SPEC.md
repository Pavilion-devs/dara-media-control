# FRONTEND SPEC

Dara uses the strict TypeScript App Router through Vinext. The interface has two
shells: public trust surfaces use a compact top navigation; operator surfaces use a
persistent sidebar. The UI must make governance, provenance, and cost legible without
presenting deterministic fixtures as live provider activity.

## Design system

The implementation is component-first:

- `components/ui/` contains ten general primitives: badges, buttons, copy rows,
  empty states, fields, panels, status blocks, steppers, theme controls, and class
  composition.
- `components/dara/` contains domain components for hashes, lineage, event streams,
  run phases, verification checks, data tables, and disclosure actions.
- `components/shell/` owns the brand, navigation model, public navbar, and operator
  sidebar.
- Route-specific interaction stays beside its page as `*-screen.tsx`; there is no
  shared monolithic screen component.

### Tokens

All colour is semantic and defined once in `app/globals.css`.

| Role | Light | Dark |
|---|---:|---:|
| Page | `#fdfdfc` | `#0c0c0d` |
| Surface | `#ffffff` | `#16161a` |
| Text | `#171717` | `#f5f5f5` |
| Accent | `#6366f1` | `#818cf8` |
| Verified | `#10b981` | `#34d399` |
| Blocked | `#ef4444` | `#f87171` |
| Pending | `#f59e0b` | `#fbbf24` |

Accent identifies selection and active controls. Verified, blocked, and pending carry
system state; they are never decoration. Dark mode follows the operating system until
the visitor makes an explicit choice. Reduced-motion preferences suppress animation.

### Type and shape

- Human-facing text: self-hosted **Manrope** through `next/font`.
- Recorded data, hashes, identifiers, models, timestamps, and money: self-hosted
  **Space Mono**.
- Panels and controls use restrained 12–16px radii, neutral surfaces, and semantic
  borders. Dense records remain tables or ordered streams rather than decorative card
  grids.
- Focus is always visible. Controls retain their action name throughout the flow.

## Route map

### Public shell

- `/` — returns a healthy response and opens the live-first Studio, preserving the
  judge-entry and infrastructure-health acceptance criteria.
- `/about` — product overview. Explains the three pillars and links into Studio and
  Verify without leaking operator fixtures.
- `/verify` — empty public verification flow. Hashes the selected file locally first,
  then streams normal files for
  full embedded-manifest inspection. If an edge rejects an oversized upload, Dara can
  look up the already-computed trusted hash without transmitting the file. The FastAPI
  boundary accepts up to 100 MB; deploy-time edge limits may be lower.
- `/share/[token]` — public token-scoped disclosure with redacted provenance and a
  short-lived asset URL. It never renders prompt text, parameters, job IDs, or run IDs.

### Operator shell

- `/studio` — an empty new-generation form backed by live projects, policies, estimates,
  generation, events, QA, publishing, and accounting. No recorded run or local estimate
  is substituted when the live control plane is unavailable. The provider call requires
  a second confirmation after the maximum reservation is shown.
- `/runs` — live B2-backed history for the active client projects only; internal smoke
  and recovery probes remain in storage but are not judge-facing. Completed live runs can
  issue client disclosure links, explicitly authorize manifest-based regeneration,
  and render the original/child output plus recorded parameter diff.
- `/assets` — live published assets derived from succeeded B2 records for active client projects.
- `/assets/[id]` — a live published-asset record: lineage, source and delivered hashes,
  provider, cost basis, and version history.
- `/ledger` — live DuckDB-over-B2 accounting scoped by an active-project selector, so
  operational probes are not mixed into client economics. An outage is visible and
  never replaced with a recorded snapshot.
- `/policies` — active policy documents and all four enforcement points. An outage is
  visible and never replaced with committed defaults.

There is no standalone Shares screen because the API does not list disclosure records.
Creation belongs to the completed live run that owns the trusted asset.

## Data boundaries

- Browser-facing product routes require no user account.
- Browser requests go through `app/api/`; the workspace bearer token remains on the
  web server.
- The web server HMACs the trusted proxy address into a pseudonymous actor ID for
  quotas and audit records. Raw IP addresses and ChatGPT identity are not persisted.
- Every JSON response is Zod-validated at the browser boundary.
- Run events use the SSE proxy and durable replay. Public product screens fail visibly
  when live data is unavailable; deterministic fixtures are restricted to tests.
- Verification is hybrid: local SHA-256 → streamed inspection for normal files →
  trusted hash lookup only when an edge cannot carry the file.

## Verification states

- `trusted-match` — exact published bytes match Dara's trusted record.
- `trusted-mismatch` — an embedded trusted record resolves, but the uploaded bytes
  differ.
- `self-consistent` — provenance is internally valid or matches a trusted source, but
  is not a trusted published-file match.
- `unknown` — no trusted record was found.

The whole-file hash remains the visual signature. It is grouped in eight-character
blocks, paired with lineage and explicit trust-boundary language. Dara claims
tamper-evidence within the issuing organisation's B2 boundary, not adversarial public
authenticity.

## Quality gate

The required local gate is:

```bash
npm run lint
npm test
```

`npm test` runs strict TypeScript checking, the five-stage Vinext production build, and
the rendered-application regressions. Supported Node.js is 22.13 or newer. The layouts
must remain usable at 375px, preserve keyboard focus, respect reduced motion, and never
hide product truth behind an unlabeled fixture fallback.
