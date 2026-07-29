# DEPLOYMENT EVIDENCE

Verified on **2026-07-29**.

## Production topology

| Concern | Deployed choice | Evidence |
|---|---|---|
| Web | OpenAI Sites, owner-only | `https://dara-media-control.asaborodaniel.chatgpt.site` |
| API | TierHive VPS `Dara`, Ubuntu 24.04, London, UK | FastAPI is an always-on `dara-api` systemd service |
| HTTPS transport | Cloudflare tunnel terminating at `127.0.0.1:8000` | The API listener is loopback-only; provider and B2 credentials remain on the VPS |
| Persistence | Backblaze B2 `dara-media-control-2026`, `us-east-005` | Jobs, policies, assets, manifests, shares, and Parquet accounting all use this bucket |

This supersedes the original T-42 placeholder choices of Vercel plus Fly.io/Railway.
The user selected TierHive for the API and OpenAI Sites for the web application. The
deployed API region is London, not US-East; B2 remains in `us-east-005`. The repository
documents the measured deployment instead of claiming the original providers or region.

## Runtime configuration

- `dara-api` starts Uvicorn on `127.0.0.1:8000` and loads secrets from
  `/etc/dara-api.env`.
- `cloudflared-dara` is independent of the API lifecycle. Restarting or redeploying
  `dara-api` no longer restarts the tunnel or changes its hostname.
- OpenAI Sites stores `DARA_API_TOKEN` as a secret and `DARA_API_URL` as a runtime
  variable. Neither value is shipped to the browser.
- Live generation, B2 access, Genblaze execution, policy checks, verification, and
  ledger queries all run on the VPS.

The current transport is an account-less Cloudflare quick tunnel. It is stable across
normal Dara API deployments, but a VPS reboot or an intentional `cloudflared-dara`
restart will issue a new hostname. Before the judging window, replace it with a named
tunnel/custom domain or update `DARA_API_URL` and redeploy the saved Sites version after
such an event. This is an explicit transport limitation, not hidden application state.

## Verification

The following checks passed against production:

1. `GET /healthz` returned HTTP 200 through the public HTTPS transport with B2 and
   OpenAI reported as configured.
2. Restarting `dara-api` left the `cloudflared-dara` process ID unchanged and the same
   public hostname healthy.
3. The Sites production deployment applied environment revision 5 successfully.
4. The signed-in production Ledger loaded live DuckDB-over-B2 data: 9 accounted runs,
   6 published assets, `$0.095000` spend, and a populated July 2026 monthly row.
5. The live monthly query regression found during deployment is covered by
   `test_spend_by_month_groups_timestamp_rows`.

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
systemctl is-active dara-api cloudflared-dara
curl -fsS http://127.0.0.1:8000/healthz
journalctl -u dara-api -n 100 --no-pager
journalctl -u cloudflared-dara -n 100 --no-pager
```

After any host or tunnel restart, confirm the public health endpoint and the production
Ledger before presenting Dara.
