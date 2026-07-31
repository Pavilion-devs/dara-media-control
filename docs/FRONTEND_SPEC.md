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

- `/` — redirects directly to Studio's zero-spend deterministic replay, preserving the
  judge-entry acceptance criterion.
- `/about` — product overview. Explains the three pillars and links into Studio and
  Verify without leaking operator fixtures.
- `/verify` — public verification. Hashes locally first, checks the trusted hash index,
  and uploads only changed, foreign, or unknown files for full embedded-manifest
  inspection. The web boundary and FastAPI both accept up to 100 MB on the TierHive
  deployment.
- `/share/[token]` — public token-scoped disclosure with redacted provenance and a
  short-lived asset URL. It never renders prompt text, parameters, job IDs, or run IDs.

### Operator shell

- `/studio` — deterministic replay and explicit live generation. Policy simulation
  remains visible before the run starts; live events stream from the durable run.
- `/runs` — live B2-backed run history plus a separately labelled committed evidence
  corpus. Live records and fixture totals are never blended. Completed live runs can
  issue client disclosure links, explicitly authorize manifest-based regeneration,
  and render the original/child output plus recorded parameter diff.
- `/assets/[id]` — the seeded published-asset proof: lineage, source and delivered
  hashes, provider latency, cost basis, and version history.
- `/ledger` — live DuckDB-over-B2 accounting with an honestly labelled recorded-proof
  fallback during storage outages.
- `/policies` — the active policy documents, four enforcement points, constraints, and
  live-versus-committed source label.

There is no standalone Shares screen because the API does not list disclosure records.
Creation belongs to the completed live run that owns the trusted asset.

## Data boundaries

- Browser-facing product routes require no user account.
- Browser requests go through `app/api/`; the workspace bearer token remains on the
  web server.
- The web server HMACs the trusted proxy address into a pseudonymous actor ID for
  quotas and audit records. Raw IP addresses and ChatGPT identity are not persisted.
- Every JSON response is Zod-validated at the browser boundary.
- Run events use the SSE proxy and durable replay. Read screens fall back only to
  committed, explicitly labelled evidence.
- Verification is hybrid: local SHA-256 → hash lookup → streamed upload only when a
  full file inspection is still needed.

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
