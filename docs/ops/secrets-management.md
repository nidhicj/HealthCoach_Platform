# Secrets Management

> **Status**: Template. Each `DECIDE` and `FILL IN` marker below is a deliberate gap for SoJo to resolve. Replace each with the actual decision/value when made. Do not leave gaps unresolved when this becomes a real runbook.

> **Maturity**: MVP-stage. Tighten as scale and team size grow.

> **Known stale content (2026-07-12)**: this entire document was written for the original Cloudflare Workers backend (`pywrangler secret put`, AWS RDS/S3) and was never updated for the GCP Cloud Run + Secret Manager migration (ADR-0001, 2026-06-19). Only the `API_BASE_URL`/`FRONTEND_URL` inventory rows and the "GCP Secret Manager — worked example" subsection under Rotation procedure (both added 2026-07-12, ADR-0009) reflect actual current mechanics. Everything else — the Storage rules section, "Adding a new secret," local dev setup (`pywrangler dev`), and the rest of the inventory table — describes the retired Cloudflare Workers process and needs a full pass. Flagged as an out-of-scope follow-up, not fixed here.

---

## Secret inventory

Every secret the platform uses. If you add a new one, add it here in the same commit.

| Secret name | Used by | Storage | Rotation cadence | Notes |
|---|---|---|---|---|
| `DATABASE_URL` | Backend → AWS RDS Mumbai | Cloudflare Secret (Worker), `.dev.vars` (local) | **DECIDE**: rotation policy. Default suggestion: every 90 days, immediately on suspected leak | Format: `postgresql+asyncpg://user:pass@host:port/db` |
| `JWT_SIGNING_KEY` | Backend (auth) | Cloudflare Secret | **DECIDE**: rotation policy. Default suggestion: every 180 days; rotation invalidates all live JWTs (not refresh tokens) | HS256 symmetric key, 32+ random bytes |
| `OPENROUTER_API_KEY` | Backend (LLM service) | Cloudflare Secret | **DECIDE**: rotation policy. Default: rotate on suspected leak only | Tied to OpenRouter account credit balance |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Backend (auth callback) | Cloudflare Secret | **DECIDE**: rotation policy. Default: every 365 days | Paired with public `GOOGLE_OAUTH_CLIENT_ID` |
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | Backend (S3 reads/writes) | Cloudflare Secret | **DECIDE**: prefer IAM role over long-lived keys; if keys, rotate every 90 days | **DECIDE**: which IAM policy? Suggestion: scoped to single S3 bucket, no other AWS access |
| `SENTRY_DSN` | Backend (observability) | Cloudflare Secret | Rotate on suspected leak only | Per-environment DSN (prototype vs scale) |
| `EXTERNAL_SCHEDULER_TOKEN` | Backend (scheduler endpoints) | Cloudflare Secret AND scheduler (GitHub Actions or EasyCron) | **DECIDE**: rotation policy. Default: every 180 days | Shared secret in `X-Scheduler-Token` header |
| `ZOOM_WEBHOOK_SECRET` (if/when Zoom integration ships) | Backend (webhook verification) | Cloudflare Secret | Rotate on suspected leak only | Out of MVP scope per `specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` |
| `API_BASE_URL` | Backend (`backend/src/auth/router.py`) — builds the Google OAuth `redirect_uri` for all 3 flows (HC login, Calendar connect, Client invite) | **GCP Secret Manager** (current, accurate — not Cloudflare) | Update only when the frontend's public hostname changes | Value: `https://app.tapas.fitness` as of ADR-0009. Despite the name, this is the **frontend's** public URL, not the backend's — historical naming from before the BFF-proxy redesign, see ADR-0005 §Amendment 2026-06-24 |
| `FRONTEND_URL` | Backend (`backend/src/main.py`) — CORS `allow_origins` | **GCP Secret Manager** (current, accurate — not Cloudflare) | Same cadence as `API_BASE_URL` — should always match it | Value: `https://app.tapas.fitness` as of ADR-0009 |

---

## Storage rules

- **Production**: Cloudflare Secrets only. Set via `pywrangler secret put <NAME>`. Never via dashboard for repeatability — but **DECIDE**: dashboard is acceptable for one-off emergency rotation.
- **Local dev**: `backend/.dev.vars` file. Listed in `.gitignore`. Each dev populates from `.dev.vars.example`.
- **CI**: GitHub Actions secrets (or equivalent). Scoped to specific workflows.
- **Never**: in code, in repo, in chat, in logs, in error messages, in commit messages, in screenshots.

---

## Adding a new secret

1. Add row to the inventory table above.
2. Add to `.dev.vars.example` with placeholder value.
3. Set in production via `pywrangler secret put <NAME>`.
4. Verify the deployed Worker can read it (one health-check call).
5. Commit the inventory + `.dev.vars.example` change.

---

## Rotation procedure

For any secret:

1. Generate new value.
2. Stage: set new value in production (Cloudflare Secrets).
3. Verify: health check confirms Worker reads new value.
4. Cutover: any process holding the old value (e.g., GitHub Actions for `EXTERNAL_SCHEDULER_TOKEN`) updated.
5. Invalidate old value at the source (revoke OpenRouter key, rotate Google OAuth client secret, etc.).
6. Update `SESSION_LOG.md` with rotation entry.

### GCP Secret Manager — worked example (`API_BASE_URL` / `FRONTEND_URL`, 2026-07-12)

The generic procedure above is written for the (retired) Cloudflare Secrets model. Here's what actually rotating a GCP Secret Manager–backed secret looks like, using the ADR-0009 custom-domain cutover as the concrete example:

```bash
# 1. Stage the new value
echo -n "https://app.tapas.fitness" | \
  gcloud secrets versions add API_BASE_URL --project=t-replica-361407 --data-file=-
echo -n "https://app.tapas.fitness" | \
  gcloud secrets versions add FRONTEND_URL --project=t-replica-361407 --data-file=-

# 2. Verify the new version landed
gcloud secrets versions access latest --secret=API_BASE_URL --project=t-replica-361407

# 3. Force cutover — IMPORTANT: Cloud Run resolves `:latest` secret references at
#    container startup, not per-request. Existing warm instances keep the OLD value
#    until naturally recycled (unbounded window). Force a new revision explicitly:
gcloud run services update hc-platform-backend \
  --region=asia-south1 --project=t-replica-361407 \
  --update-secrets=API_BASE_URL=API_BASE_URL:latest,FRONTEND_URL=FRONTEND_URL:latest

# 4. Verify the new revision is live
gcloud run services describe hc-platform-backend --region=asia-south1 --project=t-replica-361407 \
  --format="value(status.latestReadyRevisionName)"
```

Note: `.github/workflows/deploy.yml` deploys a differently-named, seemingly-orphaned service (`parivarthan-api`, not `hc-platform-backend`) — pushing to `main` does **not** reliably force the correct service's redeploy. Target `hc-platform-backend` directly via `gcloud run services update` as above. (This CI/service-naming inconsistency is itself unresolved — flagged for a separate follow-up.)

---

## Suspected compromise procedure

> **DECIDE**: who is the on-call for secret incidents? At MVP it's SoJo. Document this elsewhere when scale changes.

1. **Immediate**: rotate the secret following the Rotation procedure above.
2. **Audit**: query `audit_log` and `llm_calls` and Cloudflare Workers Logs for usage of the compromised secret in the last 30 days. **FILL IN**: actual queries to use, once the audit_log schema is confirmed in code.
3. **Notify**: if customer data may have been accessed via the compromised secret, follow `compliance-india.md` breach procedure (deferred per current scope; **FILL IN** when DPDP Rules enforcement requires it).
4. **Post-mortem**: within 7 days of incident, write a post-mortem in `docs/post-mortems/YYYY-MM-DD-<incident>.md`. **DECIDE**: post-mortems folder structure if it doesn't exist yet.

---

## Local dev setup

For a new dev (or new machine):

1. Clone repo.
2. `cp backend/.dev.vars.example backend/.dev.vars`
3. Populate `.dev.vars` with personal dev secrets:
   - **FILL IN**: where dev secrets come from. Options: shared 1Password vault (DECIDE), individual dev creates own (Google OAuth dev client, OpenRouter $0 account, local Postgres URL), or a `make dev-secrets` script that generates a working set.
4. Verify: `uv run pywrangler dev` boots and `/health` returns 200.

---

## Anti-patterns to avoid

- Hardcoding any secret in `wrangler.toml` (it's committed to repo)
- Logging request bodies that may include tokens (auth callback responses, refresh requests)
- Including secrets in error messages returned to client (defense-in-depth: scrub at API boundary)
- Putting `OPENROUTER_API_KEY` in client-side code under any circumstances (it's backend-only)
- Reusing `JWT_SIGNING_KEY` across environments (each env has its own; prevents cross-env token replay)

---

## Things to revisit

- **Move from long-lived AWS keys to IAM role assumption** when the deployment pattern supports it.
- **Introduce a secrets manager** (AWS Secrets Manager, Doppler, Infisical) when team grows beyond 1 or rotation cadence becomes onerous.
- **Audit log of secret reads** if compliance scope expands to require it. Cloudflare Workers do not log secret reads natively; would need application-level instrumentation.

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-07-12 | Added `API_BASE_URL`/`FRONTEND_URL` inventory rows (GCP Secret Manager, current values `https://app.tapas.fitness`) and a real GCP Secret Manager worked-example rotation procedure. Flagged the rest of this doc as stale Cloudflare-Workers-era content (full rewrite out of scope). | ADR-0009 custom-domain cutover — these two secrets were actually rotated as part of that change. |
| 2026-04-28 | Initial template. | Secrets inventory needs to exist before any are created. |
