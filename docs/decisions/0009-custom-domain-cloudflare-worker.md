# ADR-0009: Custom Domain via Cloudflare Worker Reverse Proxy

**Status**: Accepted
**Date**: 2026-07-12
**Decision driver**: SoJo
**Supersedes**: n/a
**Relates to**: ADR-0002 (runtime topology — Cloud Run region choice), ADR-0005 (auth strategy — `API_BASE_URL`/redirect_uri, BFF proxy)

---

## Context

The platform was reachable only via raw Cloud Run URLs (`hc-platform-frontend-*.run.app`). SoJo purchased `tapas.fitness` to give the product a real public domain — partly cosmetic (raw Cloud Run URLs look untrustworthy in the Google OAuth consent screen, and can't be shared publicly per the landing-page plan), partly because `docs/diagrams/0001-system-architecture.md` already carried a placeholder anticipating "Cloudflare as reverse proxy when domain is set up."

Only the **frontend** needs the custom domain. Per ADR-0005's 2026-06-24 amendment, the browser never talks to the backend directly — the Next.js BFF proxy (`frontend/src/app/api/[...path]/route.ts`) makes all browser requests same-origin. The backend stays on its raw `.run.app` URL indefinitely.

DNS was pointed at Cloudflare (`tapas.fitness` nameservers → Cloudflare, zone Active), with `CNAME app → hc-platform-frontend-296472807958.asia-south1.run.app`, proxied. This alone was not sufficient: `https://app.tapas.fitness/` returned Google's generic 404 page. Root cause, confirmed directly (not assumed): Cloudflare proxies the request correctly, but by default forwards the *original* `Host: app.tapas.fitness` header to the origin. Cloud Run doesn't give each service a dedicated IP — many customers' services share front-door IPs, and Google's front door routes purely by reading the `Host` header. It didn't recognize `app.tapas.fitness`, so it returned its own 404 rather than reaching `hc-platform-frontend`.

### Forces at play

- **Cost**: must stay on free/near-free infrastructure at pilot (single-HC) stage — no committed revenue yet to justify recurring infra spend.
- **Region constraint**: backend and frontend are pinned to `asia-south1` (ADR-0002, DPDP data-residency). Any fix that requires a region change is a much bigger change than a domain-routing problem warrants.
- **No new vendor lock-in** beyond what's already committed (Cloudflare DNS, GCP Cloud Run).
- **Must not break the existing BFF/cookie/CORS auth model** (ADR-0005) mid-fix — sign-in must keep working throughout.
- **"No vibe-coded infrastructure"** (CLAUDE.md rule 8) — whatever fixes this needs to be reviewable and version-controlled, not a one-off dashboard click that leaves no trail.

---

## Decision

Deploy a small Cloudflare Worker (`cloudflare/domain-proxy/`, service name `tapas-domain-proxy`) that intercepts `app.tapas.fitness/*` and re-fetches the origin with both the fetch target and the `Host` header rewritten to the real Cloud Run hostname (`hc-platform-frontend-296472807958.asia-south1.run.app`, configurable via a `wrangler.toml` variable, not hardcoded in the script). Everything else — method, headers, streaming body, cookies — passes through unmodified; this is a transparent reverse proxy, not a content transform.

Deployed via `npx wrangler deploy` (no `package.json`/build step — the script has zero dependencies), version-controlled in this repo per CLAUDE.md rule 8.

---

## Rationale

1. **Free-tier compatible**: Cloudflare Workers' free plan includes 100k requests/day, ample at single-pilot-HC scale, at $0 incremental cost.
2. **Standard, documented pattern**: rewriting the Host header via a Worker is Cloudflare's own recommended workaround for exactly this scenario (origin routes by Host header, Origin Rules' native Host-override is gated to a plan tier you don't have).
3. **No region change required**: unlike Cloud Run's native Domain Mapping fix, this doesn't touch `asia-south1`.
4. **Small, reviewable surface**: ~30 lines of dependency-free JS, easy to audit, easy to reason about failure modes.

---

## Consequences

### Positive
- $0 incremental cost at pilot scale.
- Reviewable, git-tracked infrastructure — matches CLAUDE.md rule 8.
- Solves the routing problem without touching region or introducing a new hosting product (e.g. Firebase Hosting).
- `ORIGIN_HOSTNAME` is a `wrangler.toml` variable, not a code literal — a future region move or service rename is a one-line config change, not a code change.

### Negative / tradeoffs accepted
- Adds a Cloudflare Worker as a new moving part in the request path — one more thing that can fail or need monitoring.
- 100k req/day free-tier ceiling — a non-issue at pilot scale, but a real constraint if traffic grows.
- Worker deploy is manual (`npx wrangler login && npx wrangler deploy`), not yet CI-automated.
- Does not add WAF or rate-limiting — the architecture diagram's placeholder for that is only partially resolved by this ADR (routing is fixed; WAF/rate-limiting remains unconfigured).

### Things to revisit
- If request volume approaches the 100k/day free-tier ceiling: evaluate Workers Paid ($5/mo, 10M requests included) before anything more drastic.
- If Cloud Run ever adds `asia-south1` support to native Domain Mapping: re-evaluate dropping the Worker in favor of the first-party feature.
- If a global HTTPS Load Balancer becomes justified for other reasons (e.g. Cloud Armor WAF at scale): the Worker's job could be absorbed into that migration.
- CI-automating the Worker deploy, if manual deploys become a bottleneck.

### Cutover risk notes and rollback (secrets rotation, executed 2026-07-12)

At the time `API_BASE_URL`/`FRONTEND_URL` were rotated to `https://app.tapas.fitness`, one real user was already signed in via the raw `hc-platform-frontend-*.run.app` URL. Assessed impact and rollback path, for the record:

**What actually changed for that user**: nothing, in practice. Their refresh-token cookie was already set on the old frontend origin and doesn't move or invalidate when backend secrets change. Normal usage (page loads, data fetches, token refresh) goes through the same-origin BFF proxy → server-to-server call to the backend — this path never triggers a browser CORS check and never builds a `redirect_uri`, so it's unaffected by either secret. Confirmed post-cutover: the old `.run.app` frontend URL still returns 200.

**Real edge cases, both low-severity**:
1. If that user's session fully expires and they sign in again from the old `.run.app` URL, Google will redirect them to `app.tapas.fitness` afterward instead of back to the old URL — not a failure, just an unannounced domain switch. Works fine since that redirect URI is registered.
2. The forced Cloud Run revision redeploy (needed to make the new secret values take effect — see §2 of the implementation) wipes the in-memory PKCE `_state_store`. Anyone mid-OAuth-handshake (clicked "Sign in," hasn't completed Google's consent screen) at the exact moment of redeploy would hit an invalid-state error and need to retry from scratch — no data loss, just a retry. This in-memory/multi-instance-unsafe state store is a pre-existing gap already documented in ADR-0005, not newly introduced here; window of exposure was seconds, at single-pilot-user scale.

**Rollback, if needed**:
```bash
# Find the previous secret version numbers
gcloud secrets versions list API_BASE_URL --project=t-replica-361407
gcloud secrets versions list FRONTEND_URL --project=t-replica-361407

# Point the backend back at the previous versions, forcing a new revision immediately
gcloud run services update hc-platform-backend --region=asia-south1 --project=t-replica-361407 \
  --update-secrets=API_BASE_URL=API_BASE_URL:<previous_version>,FRONTEND_URL=FRONTEND_URL:<previous_version>
```
The old `.run.app` OAuth redirect URIs were deliberately kept registered in Google Console (not removed during this migration), so rollback doesn't require re-adding anything there. If the secret revert isn't fast enough, Cloud Run retains all prior revisions — `gcloud run revisions list --service hc-platform-backend --region asia-south1` + `gcloud run services update-traffic ... --to-revisions <prior>=100` routes back directly.

---

## Options considered

### Option 1 — Cloudflare Worker reverse proxy [chosen]
See Decision/Rationale above.

### Option 2 — Cloudflare Origin Rules (Host Header override)
The "native" Cloudflare fix for this exact problem. **Why not chosen**: confirmed against Cloudflare's own documentation to be **Enterprise-plan only** — not usable on the Free plan, and Enterprise pricing is not justified at pilot scale.

### Option 3 — Cloud Run native Domain Mapping
GCP's first-party fix — attaches a custom domain directly at Cloud Run's serving layer, no Host-header workaround needed. **Why not chosen**: confirmed against live Cloud Run documentation to **not support `asia-south1`** (available in 10 other regions; even where available, Google's own docs describe it as "not production-ready, preview only" due to latency/hairpin-routing issues). Moving region to unlock this would be a disproportionate change for a domain-routing problem, and would reopen ADR-0002's data-residency decision.

### Option 4 — GCP HTTPS Load Balancer + Serverless NEG
Google's recommended production path for attaching a custom domain to Cloud Run — region-agnostic, adds Cloud CDN and Cloud Armor (WAF) as a byproduct. **Why not chosen (for now)**: a global external Application Load Balancer has a non-trivial minimum cost (~$18+/month for the forwarding rule alone, before any traffic), not justified at single-pilot-HC scale. Listed in "Things to revisit" above as the natural upgrade path if WAF/CDN needs materialize.

### Option 5 — Firebase Hosting reverse proxy
Previously the documented intended migration path (`docs/specs/Unit_001_HcCoreCycle/PHASE-09-pilot-smoke-gate.md` §B.7, written before this ADR). **Why not chosen**: introduces a second GCP-adjacent hosting product with its own config surface (`firebase.json` rewrites, a separate deploy pipeline) to solve a problem the Worker solves with ~30 lines of JS and zero new paid infrastructure. Superseded by this ADR — see the corrective note added to that phase document.

---

## References

- ADR-0002 — Runtime topology (Cloud Run region choice, `asia-south1`)
- ADR-0005 — Auth strategy (`API_BASE_URL`/redirect_uri semantics, BFF proxy, amended alongside this ADR)
- `docs/diagrams/0001-system-architecture.md` — updated alongside this ADR
- `cloudflare/domain-proxy/README.md` — operational how-to
- Cloudflare Workers docs: https://developers.cloudflare.com/workers/
- Cloudflare Origin Rules plan availability: https://developers.cloudflare.com/rules/origin-rules/features/
- Cloud Run custom domain mapping (region support): https://docs.cloud.google.com/run/docs/mapping-custom-domains

---

## Changelog

| Date | Change | Reason |
|------|--------|--------|
| 2026-07-12 | Initial draft. | `app.tapas.fitness` 404'd via plain CNAME; Cloudflare's native fix is Enterprise-only, GCP's native fix doesn't cover `asia-south1` — needed a documented decision for the workaround chosen. |
