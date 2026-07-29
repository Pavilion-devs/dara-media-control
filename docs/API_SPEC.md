# API SPEC

FastAPI, `/v1` prefix. JSON in, JSON out. OpenAPI at `/docs`.

## Auth

- **Public, no auth:** `POST /v1/verify`, `GET /v1/verify/{sha256}`, `GET /v1/share/{token}`, `GET /healthz`
- **Workspace token:** everything else. `Authorization: Bearer <KILN_API_TOKEN>`.
  There are no user accounts in this submission, but the API is not unauthenticated.
  One shared token protects the demo workspace; the frontend holds it server-side only
  and proxies through Next.js route handlers. It never reaches the browser.

## Error model

Every non-2xx returns the same envelope. The frontend renders `message` directly, so
write messages for a person.

```jsonc
{
  "error": {
    "code": "POLICY_BLOCKED",
    "message": "This run would cost $2.40, above the $2.00 limit for this project.",
    "details": { "violations": [ /* Violation[] */ ] },
    "request_id": "req_01J..."
  }
}
```

| HTTP | Code | When |
|---|---|---|
| 400 | `INVALID_REQUEST` | Malformed payload |
| 401 | `UNAUTHORIZED` | Missing or bad token |
| 404 | `NOT_FOUND` | Unknown id |
| 409 | `POLICY_BLOCKED` | Policy rejected the run — **no spend occurred** |
| 413 | `FILE_TOO_LARGE` | Verify upload over cap |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Verify got a container with no manifest handler |
| 429 | `RATE_LIMITED` | Includes `retry_after_s` |
| 502 | `PROVIDER_ERROR` | All models in a chain failed; includes the chain that was tried |
| 503 | `STORAGE_UNAVAILABLE` | B2 unreachable |

`409 POLICY_BLOCKED` is the one to get right — it is the response the demo depends on and
its `details.violations` drive the UI. Say plainly in the message that nothing was spent.

## Runs

### `POST /v1/runs`

```jsonc
// request
{
  "pipeline_id": "still-campaign",
  "project_id": "prj_northwind_q3",
  "policy_id": "pol_standard",        // optional; defaults to the project's policy
  "brief": {
    "prompt": "hero shot of a ceramic bowl on linen, morning light",
    "modality": "image",
    "aspect_ratio": "16:9",
    "variants": 3,
    "brand_notes": "warm, unfussy, no props competing with the product"
  },
  "mode": "live"                       // "live" | "demo"
}
```

`202` on accept:

```jsonc
{
  "job_id": "job_01J...",
  "status": "queued",
  "estimate": {
    "expected_usd": "0.180000",
    "worst_case_usd": "0.540000",
    "per_step": [ { "step": "expand", "usd": "0.001000" }, { "step": "image", "usd": "0.060000" } ],
    "unpriced_models": []
  },
  "events_url": "/v1/runs/job_01J.../events"
}
```

`409` when policy blocks. Persist the blocked job and policy event first, then return its
`job_id` and the estimate alongside the violations so the UI can show what it would have
cost. No daily-budget reservation and no provider call occurs.

### `GET /v1/runs/{job_id}`
Full job record (`DATA_MODEL.md`).

### `GET /v1/runs/{job_id}/events`
`text/event-stream`. Each message is a `StepEvent`. Send a comment heartbeat every 15s so
proxies do not close the connection. On reconnect, accept `?after_seq=N` and replay from
the persisted record — do not lose events on a flaky connection, which is exactly what a
judge on hotel wifi will have.

### `GET /v1/runs`
Filter by `project_id`, `status`, `pipeline_id`, date range. Cursor paginated.

### `POST /v1/runs/{job_id}/cancel`

### `POST /v1/regenerate/{job_id}`
Reconstructs from the manifest and starts a new run linked by `parent_run_id`. Policy is
re-evaluated — a regeneration can breach a budget that has tightened since. The new Dara
job also records `parent_job_id`; Genblaze's corresponding run records
`parent_run_id`. Same `202` shape.

### `GET /v1/runs/{job_id}/diff?against={other_job_id}`
Parameter diff plus both asset references, for the regeneration comparison view.

## Assets

### `GET /v1/assets/{asset_id}`
Asset record plus its lineage chain.

### `POST /v1/assets/{asset_id}/approve`
Keeps the Genblaze-bound source object unchanged, embeds the manifest into a local
candidate derivative, computes `published_sha256`, and re-extracts the manifest to
validate the candidate. The `PRE_PUBLISH` gate evaluates that prepared candidate before
Dara writes it under `published/`, writes SHA index pointers for both source and published
hashes, and marks the asset approved.

## Verify — public

### `POST /v1/verify`
`multipart/form-data`, field `file`. Cap at 100MB, stream to a temp file, never buffer
whole. Rate limit 10/min/IP.

```jsonc
{
  "result": "embedded",        // "embedded" | "matched-by-hash" | "unknown"
  "verification": "trusted-match",
  // "trusted-match" | "trusted-mismatch" | "self-consistent" | "unknown"
  "storage_status": "available", // "available" | "unavailable"
  "verified": true,            // true only for trusted-match
  "uploaded_sha256": "b741...",
  "expected_published_sha256": "b741...",
  "manifest": {
    "canonical_hash": "a71e...",
    "hash_matches": true,
    "run_id": "run_...",
    "created_at": "...",
    "steps": [
      { "provider": "openai", "model": "gpt-image-2", "modality": "image",
        "prompt": "...", "params": { "...": "..." }, "cost_usd": "0.010000" }
    ],
    "parent_run_id": null,
    "redacted": false
  },
  "lineage": [ { "run_id": "...", "at": "...", "relationship": "parent" } ],
  "trust_note": "Tamper-evident within the issuing organisation's storage. Not an adversarial authenticity proof."
}
```

Ship `trust_note` in the response body. Precision about the trust model is a feature and
the judges will recognise it as one. `Manifest.verify_hash()` checks canonical manifest
integrity and `Manifest.verify()` checks declared source-hash coverage; neither hashes
the uploaded embedded bytes. A `trusted-match` additionally requires a B2 AssetRef and an exact
`uploaded_sha256 == published_sha256` comparison.

On tamper: `verification: "trusted-mismatch"`, `verified: false`, plus
`expected_published_sha256` and `uploaded_sha256` so the UI can render a
character-level diff. If the manifest is internally valid but its run/asset does not
exist in trusted B2 state, return `self-consistent`; do not label it tampered or verified.
If B2 is temporarily unavailable, an embedded upload may return `self-consistent` with
`storage_status: "unavailable"` and a retryable warning. A no-manifest/hash-only request
returns `503 STORAGE_UNAVAILABLE`; it must not convert an unavailable lookup into
`unknown`.

### `GET /v1/verify/{sha256}`
Lookup by hash without uploading. Serves the "I have the hash from a share link" path.

## Ledger

### `GET /v1/ledger/summary`
Headline aggregates: total spend, spend prevented by policy, cost per approved asset,
waste ratio, run count, failover count. Cache 60s.

### `GET /v1/ledger/query`
`?q=spend_by_model&from=2026-07-01&to=2026-07-31&project_id=...`

`q` must be one of the allowlisted ids in `DATA_MODEL.md`. **Reject anything else with
`400`. Never interpolate user input into SQL** — parameters bind into a fixed template.

```jsonc
{
  "query": "spend_by_model",
  "columns": ["model", "provider", "runs", "total_usd", "mean_usd"],
  "rows": [ ["gpt-image-2", "openai", 9, "0.095000", "0.010556"] ],
  "generated_at": "..."
}
```

## Policies and projects

`GET|POST /v1/policies`, `GET|PUT /v1/policies/{id}`, `POST /v1/policies/{id}/simulate`.

`simulate` is worth building: post a policy plus a brief, get the decision without running
anything. It makes the governance layer explorable in the demo without spending.

`GET|POST /v1/projects`, `GET|PUT /v1/projects/{id}`.

## Sharing

### `POST /v1/shares`
```jsonc
{ "job_id": "job_...", "asset_ids": ["ast_..."], "expires_in_days": 30 }
```
Applies `EmbedPolicy` pointer redaction, writes a three-field redacted pointer sidecar,
returns
`{ "token": "shr_...", "url": "https://.../share/shr_..." }`.

Create a separate token-scoped copy from trusted source bytes for every shared asset,
compute `shared_sha256`, and store its key, hash, and pointer-sidecar key on the Share
record. Never serve the ordinary published derivative on a redacted route because its
embedded manifest may contain the stripped fields. Add the exact shared hash to
`index/sha/`; mint its download URL only when the share is read.

### `GET /v1/share/{token}` — public
Redacted manifest, a public or freshly presigned asset URL, and verification status.
Never the job id or Genblaze run id, never the prompt when redaction is on. Increments
`view_count`.

## Models and health

### `GET /v1/models`
Registry contents: provider, model id, modality, pricing, availability from the last
probe. Backs the studio's model picker and shows the registry customisation is real.

### `GET /healthz`
```jsonc
{ "ok": true, "b2": "configured", "genblaze_core": "0.3.8",
  "providers": { "openai": "configured", "replicate": "unconfigured" },
  "demo_mode_available": true }
```

## Conventions

- ISO 8601 UTC with `Z`, always.
- Money as six-place decimal strings with a `_usd` suffix. Python parses them as
  `Decimal`; never perform policy or billing arithmetic with binary floats.
- Cursor pagination: `?cursor=&limit=` → `{ "items": [], "next_cursor": null }`.
- `X-Request-Id` echoed on every response and included in error envelopes.
- Structured JSON logs with `request_id`, `job_id`, `tenant_id` on every line.
