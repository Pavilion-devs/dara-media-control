# Judge access

## Working URL

`https://usedara.xyz`

## Account

**No test account is required.**

Open the URL and use these routes directly:

1. **Studio** (`/studio`) — the default `Replay · recorded cost` is a verified
   production OpenAI image record persisted in B2. Select **Replay recorded run** to
   accelerate its original event history without contacting a provider or creating new
   spend. The selector also retains a clearly labelled deterministic QA
   fail-revise-pass fixture.
2. **Runs** (`/runs`) — shows live durable run history separately from the labelled
   production-proof and deterministic-fixture corpus. Expand a completed live record
   to inspect every attempt, issue a redacted disclosure, or explicitly authorize
   manifest-based regeneration and view its parameter diff.
3. **Policies** (`/policies`) — reads the active policy documents and every enforced
   constraint from the live engine.
4. **Ledger** (`/ledger`) — reads live aggregate accounting from immutable Parquet in Backblaze B2.
   No account is required and no prompt or secret is exposed.
5. **Verify** (`/verify`) — the page opens with a trusted published-record proof. Files
   are hashed locally first. Normal files are then streamed for full embedded-manifest
   inspection; an oversized file can use the trusted hash lookup without uploading the
   bytes. Verification never calls a generation provider.
6. **Assets** (`/assets/ast_nw_003`) — opens the seeded published-asset proof with its
   lineage, source hash, delivered hash, cost basis, and version history.

## Optional live generation

`Live OpenAI · spends` is not required to evaluate Dara. It is intentionally separate
from replay and requires a second confirmation showing the worst-case reservation, but
it does not require an account. Provider spend is bounded by a disabled-by-default
production switch, a pseudonymous visitor quota, pre-flight policy, and the independent
deployment-wide daily cap. Judges should use replay for the reliable, no-new-spend tour
unless the live action is explicitly enabled.

No API key, B2 credential, workspace bearer token, invite code, or supplied username and
password is needed anywhere in Dara. The URL was verified from a fresh browser tab and
a cookie-free HTTP client across Studio, Ledger, Verify, and the seeded Asset route.
