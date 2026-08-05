# Deployment

> **Status**: Template. `DECIDE` and `FILL IN` markers below are deliberate gaps to resolve. Replace with actual values when the runbook becomes real.

> **Maturity**: MVP-stage. Manual deploys; no full CD pipeline yet.

---

## Environments

| Environment | Hostname | Backend | Frontend | DB | When used |
|---|---|---|---|---|---|
| Local dev | `localhost:8000` (backend), `localhost:3000` (frontend) | `uvicorn src.main:app --reload` | `npm run dev` | Local Docker Postgres | Daily development |
| Production | `https://app.tapas.fitness` (frontend-facing; fronted by Cloudflare Worker `tapas-domain-proxy`, see ADR-0009) | GCP Cloud Run (`asia-south1`) — backend has no public hostname, stays on raw `.run.app` | GCP Cloud Run (`asia-south1`) | Supabase Mumbai | Pilot HC + clients |

> **DECIDE**: do you want a separate staging environment between dev and production? At MVP scale (1 HC), arguments both ways: skipping it saves cost (~$25/mo of duplicated infra); having it would catch DPDP-relevant data shape issues before they hit real client data. Suggestion: skip until pilot has 2+ HCs, but smoke-test against production-config from day 1 (per build-plan P9).

---

## First-time setup

### Cloudflare (custom domain proxy only — frontend hosting itself is Cloud Run, not Cloudflare Pages)

> Superseded 2026-06-19 (frontend moved off Cloudflare Pages to Cloud Run, per ADR-0001) and again 2026-07-12 (custom domain added via a Cloudflare Worker, not Pages — see ADR-0009). Cloudflare's only role today is DNS + a Worker that fixes Cloud Run's Host-header routing; it does not host any app code.

1. Create Cloudflare account (Free tier — sufficient; Workers' 100k req/day free tier covers pilot scale).
2. Buy the domain at a registrar (currently Porkbun), add it as a zone in Cloudflare, point the registrar's nameservers at the two Cloudflare gives you.
3. DNS record: `CNAME app → hc-platform-frontend-<project-number>.asia-south1.run.app`, **proxied** (orange cloud) — required for the Worker route below to intercept it.
4. Deploy the Worker: `cd cloudflare/domain-proxy && npx wrangler login && npx wrangler deploy` (see `cloudflare/domain-proxy/README.md`). This rewrites the Host header so Cloud Run's front door recognizes the custom domain — without it, the domain 404s even though DNS resolves correctly (ADR-0009 has the full diagnosis).
5. Verify: `curl -I https://app.tapas.fitness/` returns 200 (not Google's generic 404 page).
6. **Not yet configured**: WAF, rate limiting, Cloud Armor — the Worker above fixes routing only. See `docs/diagrams/0001-system-architecture.md` "What's NOT in this architecture" for the current state and upgrade triggers.

### GCP Cloud Run (backend)

1. GCP project: `t-replica-361407` (live — confirmed 2026-07-30; this doc previously said "FILL IN, suggestion parivarthan-prod," a placeholder that was never reconciled with the real project once it existed).
2. Enable Cloud Run API and Artifact Registry API.
3. Build and push the Docker image:
   ```bash
   cd backend
   gcloud builds submit --tag gcr.io/t-replica-361407/hc-platform-backend:latest
   ```
4. Deploy to Cloud Run in `asia-south1`:
   ```bash
   gcloud run deploy hc-platform-backend \
     --image gcr.io/t-replica-361407/hc-platform-backend:latest \
     --region asia-south1 \
     --platform managed \
     --allow-unauthenticated \
     --port 8080
   ```
5. Set all production secrets as Cloud Run environment variables or via Secret Manager. **FILL IN**: variable list per `secrets-management.md`.
6. **DECIDE**: `min-instances` setting. Default `0` (scale to zero, free). Set `1` if cold-start p95 becomes user-visible (adds ~$10/month).

### Supabase (database)

1. Create Supabase account (free).
2. Create new project — **select `ap-south-1` (Mumbai)** as the region. This is the DPDP-compliant choice.
3. Copy the connection string (use the **pooler** URL on port 6543, not direct port 5432) into `DATABASE_URL` env var.
4. Copy the `SUPABASE_URL` and `SUPABASE_ANON_KEY` into repo secrets for the keep-alive workflow (`.github/workflows/supabase-keepalive.yml`).
5. Run migrations against Supabase:
   ```bash
   DATABASE_URL=<supabase_pooler_url> uv run alembic upgrade head
   ```

### OpenRouter

1. Create OpenRouter account.
2. Purchase $10 credit to unlock 1000 reqs/day free tier (per ADR-0001).
3. Generate API key. Store as `OPENROUTER_API_KEY` Cloudflare secret.
4. Configure no-training/no-retention settings at account level (per ADR-0001).

### Google OAuth

1. Create Google Cloud project. **FILL IN**: project name (suggestion: `healthcoach-prod`).
2. Enable Google Sign-In API.
3. Create OAuth 2.0 credentials.
4. Configure authorized redirect URIs: production callback URL + local dev URL.
5. Store client ID and secret as Cloudflare secrets.

---

## Deploy procedure

### Backend

```bash
cd backend
# Verify local boots first
uvicorn src.main:app --reload
# Run tests
uv run pytest
# Build Docker image
docker build -t hc-platform-backend:latest .
# Deploy to Cloud Run (requires gcloud auth)
gcloud run deploy hc-platform-backend \
  --image gcr.io/t-replica-361407/hc-platform-backend:latest \
  --region asia-south1 \
  --platform managed
```

After deploy:
1. Hit `/healthz` on the Cloud Run service URL → expect `{"status":"ok"}`.
2. Check GCP Cloud Logging → JSON log lines should appear.
3. Smoke test: hit one auth endpoint, verify JWT issued.

### Frontend

```bash
cd frontend
npm run build
# Build/push/deploy to Cloud Run — see frontend/cloudbuild.yaml (gcloud builds submit
# + gcloud run deploy hc-platform-frontend), same pattern as the backend above.
```

The Cloudflare Worker (`cloudflare/domain-proxy/`) does **not** need redeploying on ordinary frontend deploys — it references the frontend by its stable Cloud Run *service* hostname, which doesn't change across revisions. Only redeploy the Worker if the service is renamed or moved to a different region.

### Database migrations

```bash
cd backend
# Create migration locally
uv run alembic revision --autogenerate -m "<description>"
# Review the generated SQL
# Apply locally first
uv run alembic upgrade head
# Test against local
# Apply to production (via Worker or via local with prod DATABASE_URL temporarily)
DATABASE_URL=<prod_url> uv run alembic upgrade head
```

> **DECIDE**: how migrations apply to production. Options: (a) manually from a maintainer's laptop (current default), (b) a one-shot Cloud Run endpoint that runs migrations on POST with admin token, (c) a CI step. At MVP, (a) is fine; revisit when team > 1.

---

## Rollback

### Backend

```bash
# List recent Cloud Run revisions
gcloud run revisions list --service hc-platform-backend --region asia-south1
# Route 100% traffic back to a prior revision
gcloud run services update-traffic hc-platform-backend \
  --region asia-south1 \
  --to-revisions <REVISION_NAME>=100
```

GCP Cloud Run retains all prior revisions; traffic split is instant.

### Frontend

Frontend is Cloud Run too (`hc-platform-frontend`), not Cloudflare Pages — this section previously described the retired Cloudflare Pages flow, inconsistent with this same doc's own Environments table above. Same rollback mechanism as the backend:

```bash
gcloud run revisions list --service hc-platform-frontend --region asia-south1
gcloud run services update-traffic hc-platform-frontend \
  --region asia-south1 \
  --to-revisions <REVISION_NAME>=100
```

### Database

Migration rollback is dangerous. **Default policy**: forward-only fixes. If a migration is bad:
1. Write a new migration that fixes the issue.
2. Apply it.
3. Do NOT `alembic downgrade` against production unless data loss is acceptable.

> **DECIDE**: under what circumstances `alembic downgrade` is permitted in production. Default suggestion: never; document any exception in a post-mortem.

---

## Failure modes during deploy

| Symptom | Likely cause | Fix |
|---|---|---|
| `gcloud run deploy` fails with image not found | Docker image not pushed to Artifact Registry | Run `gcloud builds submit` first; verify image tag matches deploy command |
| Cloud Run service deploys but `/healthz` returns 500 | Missing env var or DB connection issue | Check GCP Cloud Logging; verify all env vars/secrets per `secrets-management.md` |
| Cloud Run cold start p95 > 3s (sustained) | Scale-to-zero cold path too slow | Set `min-instances: 1` on the Cloud Run service (~$10/month); monitor after |
| Supabase connection refused | Free-tier project paused (inactive >1 week) | Log in to Supabase dashboard → unpause project. Data is intact. Check keep-alive workflow is running. |
| Migration fails partway through | Default Alembic behaviour: stops, partial state | Manually inspect DB via Supabase SQL editor; complete the migration intent in SQL or rollback the partial change; never leave partial state |

---

## Pre-pilot deploy checklist

> Per `build-plan.md` Phase 9. **FILL IN** the actual values when each is verified.

- [ ] Cloud Run service deployed (`asia-south1`); `/healthz` returns 200
- [ ] Production Pages deployed (Cloudflare); HC can sign in
- [ ] All secrets/env vars configured — verify against `secrets-management.md`
- [ ] DB migrations applied to Supabase; Supabase SQL editor `\dt` shows all tables
- [ ] Cloudflare rate limit, WAF, cache rules enabled for Pages layer (screenshot recorded — **FILL IN**: where the screenshot lives)
- [ ] GitHub Actions `supabase-keepalive.yml` workflow enabled and last run successful
- [ ] Smoke test (`scripts/smoke-test.py`) passes against production Cloud Run service
- [ ] DNS resolves correctly: **FILL IN** actual hostname
- [ ] HTTPS active and certificate valid
- [ ] Sentry receiving events (verified by triggering a deliberate test error)
- [ ] First HC seeded with 5+ snippet examples per ADR-0003 cold-start mitigation

---

## Things to revisit

- **CD pipeline** when manual deploys become a bottleneck. GitHub Actions → `gcloud run deploy` (or Cloud Build trigger) is the natural next step.
- **Blue/green or canary deploy** when production traffic is high enough that bad deploys affect real users.
- **Database migration automation** when manual is too risky.

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-07-30 | Fixed `parivarthan-backend`/`parivarthan-api` references (never a real service — `gcloud run services list` confirms only `hc-platform`/`hc-platform-backend` exist) to the real service names throughout. Filled in the real GCP project ID (`t-replica-361407`, was a "FILL IN" placeholder). Corrected the Frontend rollback section, which still described the retired Cloudflare Pages flow despite this doc's own Environments table already saying frontend is Cloud Run. **Not fixed in this pass, deliberately**: `.github/workflows/deploy.yml` itself — ADR-0008 Task 3 explicitly holds that file pending SoJo's confirmation of current deploy mechanics, since editing it could trigger a real redeploy on the next push to `main`. | Found during a docs-currency audit; ADR-0008 had already independently identified this exact mismatch but left Task 3 unexecuted. |
| 2026-07-12 | Production hostname filled in (`https://app.tapas.fitness`). "Cloudflare (frontend only)" section rewritten — it described the retired Cloudflare Pages flow; Cloudflare's actual role today is DNS + a Worker (`cloudflare/domain-proxy/`) fixing Cloud Run's Host-header routing, not app hosting. Frontend deploy procedure corrected (was still describing `wrangler pages deploy`). | ADR-0009 — custom domain added via Cloudflare Worker reverse proxy. |
| 2026-06-19 | Backend changed from Cloudflare Workers (`pywrangler`) to GCP Cloud Run (`gcloud run deploy`). DB changed from AWS RDS to Supabase. First-time setup, deploy procedure, rollback, failure modes all updated. Supabase keep-alive step added to pre-pilot checklist. | Stack migration per ADR-0001 changelog 2026-06-19. |
| 2026-04-28 | Initial template. | Deploy procedure needs to exist before first deploy. |
