# Deployment

> **Status**: Template. `DECIDE` and `FILL IN` markers below are deliberate gaps to resolve. Replace with actual values when the runbook becomes real.

> **Maturity**: MVP-stage. Manual deploys; no full CD pipeline yet.

---

## Environments

| Environment | Hostname | Backend | Frontend | DB | When used |
|---|---|---|---|---|---|
| Local dev | `localhost:8787` (backend), `localhost:3000` (frontend) | `pywrangler dev` | `npm run dev` | Local Docker Postgres | Daily development |
| Production | **FILL IN**: actual prod URL once domain is configured (e.g. `app.healthcoach.in`) | Cloudflare Worker | Cloudflare Pages | AWS RDS Mumbai | Pilot HC + clients |

> **DECIDE**: do you want a separate staging environment between dev and production? At MVP scale (1 HC), arguments both ways: skipping it saves cost (~$25/mo of duplicated infra); having it would catch DPDP-relevant data shape issues before they hit real client data. Suggestion: skip until pilot has 2+ HCs, but smoke-test against production-config from day 1 (per build-plan P9).

---

## First-time setup

### Cloudflare

1. Create Cloudflare account (Free tier sufficient for prototype scale).
2. Create Worker via `pywrangler init` in the `backend/` directory.
3. **DECIDE**: which Cloudflare account / zone owns the Worker. If using a custom domain, configure DNS at the registrar.
4. **FILL IN**: Worker name (suggestion: `healthcoach-prod`).
5. Set all production secrets per `secrets-management.md` (one `pywrangler secret put` per secret).
6. Configure Pages project for frontend: connect to GitHub repo, build command `npm run build`, build output `out/` (or as ADR-0001 specifies).
7. Per `decisions/0002-runtime-topology.md`: enable rate limiting, WAF, basic cache rules at Cloudflare dashboard. **FILL IN**: actual rate limit thresholds (suggestion: 100 req/min per IP for unauthenticated paths, 600 req/min per authenticated user).

### AWS

1. **DECIDE**: AWS account ownership (personal account at MVP, organization later).
2. Provision RDS Postgres in `ap-south-1` (Mumbai). **FILL IN**: instance class (suggestion: `db.t4g.micro` for MVP, ~$15-20/mo).
3. Provision S3 bucket in `ap-south-1`. **FILL IN**: bucket name (suggestion: `healthcoach-prod-content`).
4. **DECIDE**: VPC configuration. RDS Mumbai is reached over the Internet from Cloudflare Workers — Mumbai-region access is via public endpoint with security group restricting source IPs. **FILL IN**: which IP ranges are allowed (Cloudflare Workers source IPs are wide; alternatives include AWS PrivateLink which adds cost and complexity). Suggestion at MVP: open to public IPs but require strong DB password + connection-pool-side defense.
5. Create IAM user/role for backend's S3 access. **DECIDE**: per `secrets-management.md`, IAM role assumption preferred over long-lived keys.

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
uv run pywrangler dev
# Run tests
uv run pytest
# Deploy
uv run pywrangler deploy
```

After deploy:
1. Hit `/health` on production URL → expect 200.
2. Check Cloudflare Workers dashboard → bundle size logged. **FILL IN**: target bundle size threshold to alert on (per ADR-0001 trigger evaluation; current Free tier limit is 3 MiB compressed).
3. Smoke test: hit one auth endpoint, verify JWT issued.

### Frontend

```bash
cd frontend
npm run build
```

Cloudflare Pages auto-deploys on push to `main` (if configured). Otherwise: `npx wrangler pages deploy ./out`.

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

> **DECIDE**: how migrations apply to production. Options: (a) manually from a maintainer's laptop (current default), (b) a one-shot Worker endpoint that runs migrations on POST with admin token, (c) a CI step. At MVP, (a) is fine; revisit when team > 1.

---

## Rollback

### Backend

```bash
uv run pywrangler deployments list
uv run pywrangler rollback <deployment_id>
```

Cloudflare Workers retain prior deployments (10 most recent on Free, 100 on Paid).

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
| `pywrangler deploy` fails with `bundle too large` | Bundle past 3 MiB Free / 10 MiB Paid | Trim deps; check ADR-0002 trigger; consider Paid tier upgrade or runtime split |
| `pywrangler deploy` fails with `module not found` for a Pyodide-incompatible package | ADR-0001 trigger #3 | Per ADR-0002, this routes to DO Bangalore migration |
| Worker deploys but `/health` returns 500 | Likely missing secret or DB connection issue | Check Cloudflare Workers Logs; verify all secrets per `secrets-management.md` |
| Worker deploys but cold start > 3s | Approaching ADR-0001 trigger #1 | Investigate via Cloudflare metrics; consult ADR-0002 if sustained |
| Migration fails partway through | Default Alembic behavior: stops, partial state | Manually inspect DB; either complete the migration's intent in SQL or rollback the partial change; never leave partial state |

---

## Pre-pilot deploy checklist

> Per `build-plan.md` Phase 9. **FILL IN** the actual values when each is verified.

- [ ] Production Worker deployed; `/health` returns 200
- [ ] Production Pages deployed; HC can sign in
- [ ] All secrets configured (count: 8 — verify against `secrets-management.md`)
- [ ] DB migrations applied; `\dt` in psql shows all tables
- [ ] Cloudflare rate limit, WAF, cache rules enabled (screenshot recorded — **FILL IN**: where the screenshot lives)
- [ ] Smoke test (`scripts/smoke-test.py`) passes against production-config
- [ ] DNS resolves correctly: **FILL IN** actual hostname
- [ ] HTTPS active and certificate valid
- [ ] Sentry receiving events (verified by triggering a deliberate test error)
- [ ] First HC seeded with 5+ snippet examples per ADR-0003 cold-start mitigation

---

## Things to revisit

- **CD pipeline** when manual deploys become a bottleneck. GitHub Actions → `pywrangler deploy` is the natural next step.
- **Blue/green or canary deploy** when production traffic is high enough that bad deploys affect real users.
- **Database migration automation** when manual is too risky.

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-04-28 | Initial template. | Deploy procedure needs to exist before first deploy. |
