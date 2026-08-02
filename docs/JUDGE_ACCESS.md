# Judge access

## Working URL

`https://usedara.xyz`

## Account

**No test account is required.**

Open the URL and use these routes directly:

1. **Studio** (`/studio`) — starts as an empty live generation. Select a project and
   policy, enter a prompt, and read the active model-registry estimate. The first click
   shows the maximum reservation; the second authorizes the OpenAI call. Nothing is
   preloaded or replayed.
2. **Runs** (`/runs`) — shows only durable B2 run history. Expand a completed live record
   to inspect every attempt, issue a redacted disclosure, or explicitly authorize
   manifest-based regeneration and view its parameter diff.
3. **Policies** (`/policies`) — reads the active policy documents and every enforced
   constraint from the live engine.
4. **Ledger** (`/ledger`) — reads live aggregate accounting from immutable Parquet in Backblaze B2.
   No account is required and no prompt or secret is exposed.
5. **Verify** (`/verify`) — starts empty and waits for the exact file being evaluated.
   Files are hashed locally first. Normal files are then streamed for full embedded-manifest
   inspection; an oversized file can use the trusted hash lookup without uploading the
   bytes. Verification never calls a generation provider.
6. **Assets** (`/assets`) — lists published assets from succeeded live B2 runs. Open any
   asset to inspect its lineage, source hash, delivered hash, cost basis, and version
   history.

## Live generation safeguards

Generation does not require an account, but it never runs on a single accidental click.
The second confirmation shows the worst-case reservation. Provider spend remains bounded
by the production kill switch, a pseudonymous visitor quota, pre-flight policy, and the
independent deployment-wide daily cap. Runs, Assets, Policies, Ledger, and Verify can be
evaluated from existing live B2 records without creating new spend.

No API key, B2 credential, workspace bearer token, invite code, or supplied username and
password is needed anywhere in Dara. The URL is verified from a fresh browser tab and
a cookie-free HTTP client across Studio, Runs, Assets, Policies, Ledger, and Verify.
