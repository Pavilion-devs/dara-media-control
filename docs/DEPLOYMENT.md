# DEPLOYMENT EVIDENCE

Verified on **2026-07-29**.

## Production topology

| Concern | Deployed choice | Evidence |
|---|---|---|
| Web | TierHive VPS `Dara`, public judge service | `https://diamonds-jessica-accidents-icq.trycloudflare.com` |
| Private preview | OpenAI Sites, owner-only | `https://dara-media-control.asaborodaniel.chatgpt.site` |
| API | TierHive VPS `Dara`, Ubuntu 24.04, London, UK | FastAPI is an always-on `dara-api` systemd service |
| HTTPS transport | Cloudflare tunnel terminating at `127.0.0.1:8000` | The API listener is loopback-only; provider and B2 credentials remain on the VPS |
| Persistence | Backblaze B2 `dara-media-control-2026`, `us-east-005` | Jobs, policies, assets, manifests, shares, and Parquet accounting all use this bucket |

This supersedes the original T-42 placeholder choices of Vercel plus Fly.io/Railway.
The user selected TierHive for the API and OpenAI Sites for the initial web application.
When the Sites workspace refused public publishing at the platform level, T-48 deployed
the same validated Vinext application as a separate loopback-only Node service on the
Dara VPS and exposed it through an independent HTTPS tunnel. The owner-only Sites
deployment remains a private preview. The deployed application region is London, not
US-East; B2 remains in `us-east-005`.

## Runtime configuration

- `dara-api` starts Uvicorn on `127.0.0.1:8000` and loads secrets from
  `/etc/dara-api.env`.
- `dara-web` starts the self-contained Vinext production server on
  `127.0.0.1:3000` and proxies to the API over loopback.
- `cloudflared-dara` is independent of the API lifecycle. Restarting or redeploying
  `dara-api` no longer restarts the tunnel or changes its hostname.
- `cloudflared-dara-web` is a separate always-on service for the public judge URL.
- OpenAI Sites stores `DARA_API_TOKEN` as a secret and `DARA_API_URL` as a runtime
  variable for the private preview. The VPS web service loads the same token from a
  root-readable environment file. Neither deployment ships it to the browser.
- Live generation, B2 access, Genblaze execution, policy checks, verification, and
  ledger queries all run on the VPS.
- OpenAI and Replicate credentials are server-side only. The production health endpoint
  reports both providers configured; Replicate's paid FLUX probe persisted a verified
  asset and manifest to B2 on 2026-07-30.

The current API and web transports are independent account-less Cloudflare quick
tunnels. They are stable across normal Dara service deployments, but a VPS reboot or an
intentional tunnel restart will issue new hostnames. Before the judging window, replace
them with named tunnels/custom domains or update the affected URL and redeploy. This is
an explicit transport limitation, not hidden application state.

TierHive's HAProxy control plane was inspected on 2026-07-30. It can provide regional
SSL termination for a user-controlled hostname after its DNS record is pointed at the
assigned proxy, but no domain is dedicated to Dara yet. Existing unrelated HAProxy
domains were left untouched; replacing the quick tunnel therefore requires an explicit
hostname choice and DNS authorization.

## Verification

The following checks passed against production:

1. `GET /healthz` returned HTTP 200 through the public HTTPS transport with B2 and
   OpenAI reported as configured.
2. Restarting `dara-api` left the `cloudflared-dara` process ID unchanged and the same
   public hostname healthy.
3. The Sites production deployment applied environment revision 5 successfully.
4. The production Ledger loaded live DuckDB-over-B2 data: 9 accounted runs,
   6 published assets, `$0.095000` spend, and a populated July 2026 monthly row.
5. The live monthly query regression found during deployment is covered by
   `test_spend_by_month_groups_timestamp_rows`.
6. The public TierHive web service returned HTTP 200 for Studio, Ledger, Verify, the
   seeded Asset page, and the anonymous ledger API from a cookie-free client.
7. A fresh browser tab rendered the deterministic Studio fixture, then loaded the live
   DuckDB-over-B2 Ledger with 9 runs and 6 published assets, the trusted Verify proof,
   and the seeded asset lineage without a sign-in redirect.
8. On 2026-07-30, a new anonymous 390×844 browser context loaded Studio, Ledger,
   Verify, and `/assets/ast_nw_003` without a sign-in wall, horizontal overflow,
   browser-console warnings, or errors. The temporary B2 cap was still active, so
   Ledger correctly rendered its dated `RECORDED PROOF` continuity state rather than
   labelling the snapshot live.

### B2 cap continuity check

On 2026-07-29, Backblaze returned HTTP 403 with `AccessDenied: download bandwidth or
transaction (Class B) cap exceeded` while DuckDB opened the remote Parquet objects. The
API correctly returned `LEDGER_UNAVAILABLE`; Studio, Verify, Assets, and the Ledger page
remained reachable. The Backblaze console showed 2,572 Class B transactions against the
2,500 daily cap. Raising that cap requires a payment method; no billing information was
entered during deployment.

The web client now falls back to a committed snapshot of the last verified live
DuckDB-over-B2 result: 9 runs, 6 approved assets, `$0.095000` spend, `$0.015000`
prevented spend, the exact model aggregate, month aggregate, and six observed project
groups. It labels this state **RECORDED PROOF**, dates the snapshot, and leaves
per-project spend blank because that value was not preserved in the verification
screenshot. It never labels the snapshot live or invents missing numbers.

The API also applies five-minute retry cooldowns after a ledger initialization or
query-execution failure. One request records the authoritative B2 error; repeated
public polling during the cap window returns the same honest unavailable state without
reopening DuckDB or issuing another remote Parquet scan.

The read path was hardened after the incident. The browser now requests one combined
dashboard endpoint instead of four concurrent ledger endpoints. DuckDB produces the
summary, model, project, and month views in one `GROUPING SETS` query over Parquet in B2;
the API reuses that result for 60 seconds and serializes cold singleton initialization.
The allowlisted query endpoints remain available for focused analysis.

This continuity path does not supersede the live ledger requirement.

At 2026-07-30 00:01 UTC, Backblaze opened the new daily accounting window. An API-only
restart cleared the previous cooldown while the public web-service and web-tunnel
process IDs remained unchanged. The first controlled public dashboard request returned
HTTP 200 from a fresh DuckDB-over-B2 query: 9 runs, 6 approved assets, `$0.095000`
spend, `$0.015000` prevented spend, the model/month aggregates, and all six exact
project totals. A clean judge-facing browser then rendered `LIVE · DUCKDB OVER B2`
with no warnings or errors. The recorded-proof path remains available for a future B2
outage or cap event, but live ledger continuity is restored for recording and
submission.

### Fresh-clone and dependency audit

Commit `1cb5b13` was cloned anonymously from the public GitHub repository into a new
temporary directory on 2026-07-29. The README sequence was executed without using the
working tree: copy `.env.example`, create a Python 3.12 virtual environment, install the
API editable package, and run `npm ci`. The published verification commands then passed:

- 72 Python unit tests, including 17 subtests;
- ESLint with the React Hooks and TypeScript recommended rule sets;
- the five-stage Vinext production build and all five rendered-page tests; and
- generated provider/model inventory from `api/dara/providers.py`.

`npm audit` reported zero production or development dependency advisories. Next.js,
React, the RSC runtime, Vite, Wrangler, and the Cloudflare Vite plugin are pinned to the
tested patch releases in `package-lock.json`; patched nested PostCSS and Sharp releases
are enforced through package overrides. Empty Drizzle starter scaffolding was removed:
Dara has no application database, matching the deployed one-bucket architecture.

On 2026-07-30, the no-sign-in hardening, rebuilt UI, live run history, and hybrid
hash/upload verification passed the expanded local gate: 78 Python tests, ESLint,
TypeScript checking, the five-stage Vinext build, and nine rendered-application tests.
The web regression includes the shipped 1.1 MB proof crossing the Vinext request
boundary without the former 413. The next production deployment will publish these
changes together after the branch is frozen.

## Latency

Eight HTTPS health samples from the build workstation configured for Africa/Lagos:

```text
0.505515  0.400988  0.413141  0.493894
0.477979  0.494545  0.443065  0.500326 seconds
```

- Median: **486 ms**
- p95 (nearest-rank): **506 ms**
- Request-triggered cold start: **none**; the API is an always-on systemd service
- Controlled API restart to application readiness: **13 seconds**

That latency is acceptable for the interactive control-plane calls in the demo. Media
generation remains dominated by provider execution time and streams progress separately.

## Operator checks

```bash
systemctl is-active dara-api dara-web cloudflared-dara cloudflared-dara-web
curl -fsS http://127.0.0.1:8000/healthz
journalctl -u dara-web -n 100 --no-pager
journalctl -u dara-api -n 100 --no-pager
journalctl -u cloudflared-dara -n 100 --no-pager
journalctl -u cloudflared-dara-web -n 100 --no-pager
```

After any host or tunnel restart, confirm the public health endpoint and the production
Ledger before presenting Dara.
