# Deployment

> **Status**: Template. `DECIDE` and `FILL IN` markers below are deliberate gaps to resolve. Replace with actual values when the runbook becomes real.

> **Maturity**: MVP-stage. Manual deploys; no full CD pipeline yet.

---

## Environments

| Environment | Hostname | Backend | Frontend | DB | When used |
|---|---|---|---|---|---|
| Local dev | `localhost:8000` (backend), `localhost:3000` (frontend) | `uvicorn src.main:app --reload` | `npm run dev` | Local Docker Postgres | Daily development |
| Production | **FILL IN**: actual prod URL once domain is configured (e.g. `app.healthcoach.in`) | GCP Cloud Run (`asia-south1`) | Cloudflare Pages | Supabase Mumbai | Pilot HC + clients |

> **DECIDE**: do you want a separate staging environment between dev and production? At MVP scale (1 HC), arguments both ways: skipping it saves cost (~$25/mo of duplicated infra); having it would catch DPDP-relevant data shape issues before they hit real client data. Suggestion: skip until pilot has 2+ HCs, but smoke-test against production-config from day 1 (per build-plan P9).

---

## First-time setup

### Cloudflare (frontend only)

1. Create Cloudflare account (Free tier sufficient for prototype scale).
2. Configure Pages project for frontend: connect to GitHub repo, build command `npm run build`, build output `.next/` (or `out/` for static export — confirm with ADR-0001 frontend stack).
3. **DECIDE**: which Cloudflare account / zone owns the Pages project. If using a custom domain, configure DNS at the registrar.
4. Enable rate limiting, WAF, basic cache rules at Cloudflare dashboard (for the Pages/frontend layer). **FILL IN**: actual rate limit thresholds (suggestion: 100 req/min per IP for unauthenticated paths).

### GCP Cloud Run (backend)

1. Create a GCP project. **FILL IN**: project ID (suggestion: `parivarthan-prod`).
2. Enable Cloud Run API and Artifact Registry API.
3. Build and push the Docker image:
   ```bash
   cd backend
   gcloud builds submit --tag gcr.io/<PROJECT_ID>/parivarthan-backend:latest
   ```
4. Deploy to Cloud Run in `asia-south1`:
   ```bash
   gcloud run deploy parivarthan-backend \
     --image gcr.io/<PROJECT_ID>/parivarthan-backend:latest \
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
docker build -t parivarthan-backend:latest .
# Deploy to Cloud Run (requires gcloud auth)
gcloud run deploy parivarthan-backend \
  --image gcr.io/<PROJECT_ID>/parivarthan-backend:latest \
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
```

Cloudflare Pages auto-deploys on push to `main` (if configured). Otherwise: `npx wrangler pages deploy ./.next`.

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
gcloud run revisions list --service parivarthan-backend --region asia-south1
# Route 100% traffic back to a prior revision
gcloud run services update-traffic parivarthan-backend \
  --region asia-south1 \
  --to-revisions <REVISION_NAME>=100
```

GCP Cloud Run retains all prior revisions; traffic split is instant.

### Frontend

Cloudflare Pages: from dashboard, select prior deployment → "Rollback to this deployment".

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
| 2026-06-19 | Backend changed from Cloudflare Workers (`pywrangler`) to GCP Cloud Run (`gcloud run deploy`). DB changed from AWS RDS to Supabase. First-time setup, deploy procedure, rollback, failure modes all updated. Supabase keep-alive step added to pre-pilot checklist. | Stack migration per ADR-0001 changelog 2026-06-19. |
| 2026-04-28 | Initial template. | Deploy procedure needs to exist before first deploy. |
