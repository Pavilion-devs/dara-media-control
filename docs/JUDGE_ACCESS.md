# Judge access

## Working URL

`https://diamonds-jessica-accidents-icq.trycloudflare.com`

## Account

**No test account is required.**

Open the URL and use these routes directly:

1. **Studio** — the default `Demo replay · $0` is a committed deterministic fixture.
   Select **Run verified demo** to replay the QA fail-revise-pass event stream. It does
   not contact an AI provider.
2. **Ledger** — reads live aggregate accounting from immutable Parquet in Backblaze B2.
   No account is required and no prompt or secret is exposed.
3. **Verify** — the page opens with a trusted published-record proof. Uploading a file
   calls only Dara's verifier; it never calls a generation provider.
4. **Assets** — opens the seeded lineage and regeneration view.

## Optional live generation

`Live OpenAI · spends` is not required to evaluate Dara. It is intentionally separate
from demo replay and may request **Sign in with ChatGPT** before it can spend provider
credits. Judges should use demo replay for the reliable, zero-cost product tour.

No API key, B2 credential, workspace bearer token, invite code, or supplied username and
password is needed anywhere in the judge path. The URL was verified from a fresh browser
tab and a cookie-free HTTP client across Studio, Ledger, Verify, and the seeded Asset
route.
