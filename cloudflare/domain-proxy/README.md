# tapas-domain-proxy

A Cloudflare Worker that fronts `app.tapas.fitness` and rewrites the `Host`
header of every request to the real Cloud Run origin
(`hc-platform-frontend-*.run.app`).

## Why this exists

Cloud Run doesn't give each service a dedicated IP — many customers'
services share the same front-door IPs, and Google's front door decides
which service to serve purely by reading the `Host` header. Cloudflare's DNS
proxy forwards the *original* hostname (`app.tapas.fitness`) by default, so
without this Worker, Cloud Run doesn't recognize the request and returns a
generic 404.

The "native" fixes for this were both ruled out:
- Cloudflare Origin Rules → Host Header override is **Enterprise-plan only**.
- Cloud Run's native Domain Mapping feature **doesn't support `asia-south1`**.

See `docs/decisions/0008-custom-domain-cloudflare-worker.md` for the full
decision record.

## Prerequisites

- `tapas.fitness` zone active in Cloudflare (Free plan is sufficient —
  Workers' 100k requests/day free tier is ample at pilot scale).
- DNS record `app.tapas.fitness` → `CNAME` → the frontend Cloud Run hostname,
  **proxied** (orange cloud) — required for a Worker Route to intercept it.

## Deploy

No `package.json`/build step needed — this is a plain, dependency-free ES
module.

```bash
cd cloudflare/domain-proxy
npx wrangler login    # one-time per machine, opens a browser for OAuth
npx wrangler deploy
```

If the Cloudflare account has more than one zone/account, `wrangler` may
prompt to select one — pick the account that owns `tapas.fitness`.

## Verify

```bash
# Should return 200 (or a Next.js redirect), not Google's generic 404 page
curl -sI https://app.tapas.fitness/ | head -5

# Should show "server: cloudflare" — confirms it's still proxied
```

Check Cloud Run logs to confirm requests are arriving with the rewritten
Host header:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="hc-platform-frontend"' \
  --project=t-replica-361407 --limit=20 --format=json
```

## Updating the origin

If the frontend Cloud Run service is ever redeployed under a different
hostname (region move, service rename), update `ORIGIN_HOSTNAME` in
`wrangler.toml` and redeploy — no code change needed.
