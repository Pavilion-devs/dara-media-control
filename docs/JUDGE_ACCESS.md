# Judge access

## Working URL

`https://diamonds-jessica-accidents-icq.trycloudflare.com`

## Account

**No test account is required.**

Open the URL and use these routes directly:

1. **Studio** (`/studio`) — the default `Demo replay · $0` is a committed deterministic fixture.
   Select **Run verified demo** to replay the QA fail-revise-pass event stream. It does
   not contact an AI provider.
2. **Runs** (`/runs`) — shows live durable run history separately from the labelled
   production-proof and deterministic-fixture corpus.
3. **Policies** (`/policies`) — reads the active policy documents and every enforced
   constraint from the live engine.
4. **Ledger** (`/ledger`) — reads live aggregate accounting from immutable Parquet in Backblaze B2.
   No account is required and no prompt or secret is exposed.
5. **Verify** (`/verify`) — the page opens with a trusted published-record proof. Files
   are hashed locally, checked by hash, then uploaded only when full manifest inspection
   is needed. Verification never calls a generation provider.
6. **Assets** (`/assets/ast_nw_003`) — opens the seeded lineage and regeneration view.

## Optional live generation

`Live OpenAI · spends` is not required to evaluate Dara. It is intentionally separate
from demo replay, but it does not require an account. Provider spend is bounded by a
disabled-by-default production switch, a pseudonymous visitor quota, pre-flight policy,
and the durable daily cap. Judges should use demo replay for the reliable, zero-cost
product tour unless the live action is explicitly enabled.

No API key, B2 credential, workspace bearer token, invite code, or supplied username and
password is needed anywhere in Dara. The URL was verified from a fresh browser tab and
a cookie-free HTTP client across Studio, Ledger, Verify, and the seeded Asset route.
