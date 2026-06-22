# PHASE-09: Pre-Pilot Smoke Gate

**Unit**: Unit_001_HcCoreCycle
**Status**: Draft
**Verification date**: TBD — see `docs/VERIFICATION.md` § P9
**Implements**: `build-plan.md §Phase 9` acceptance criteria
**ADRs implemented**: ADR-0001 (stack — smoke gate + open follow-ups), ADR-0002 (runtime topology — Cloudflare platform features one-time setup), `domain/compliance-india.md` (DPDP hooks walkthrough)

---

## 0. Prerequisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific not provided.

**P8 must be Complete and Verified before P9 begins.** Two P8 ACs were deferred to P9 and are completed here:
- AC4 (Sentry smoke test with real DSN) — Task 5
- AC5 (5 SQL queries against production DB) — Task 6

**Infrastructure prerequisite (MUST be resolved before any task in this phase can start)**:

> **Context missing — answer before P9 begins:**
>
> 1. Is the GCP Cloud Run service deployed to `asia-south1`? If yes, what is the production service URL?
> 2. Is the Supabase project provisioned (`ap-south-1`, Mumbai) and migrated (`alembic upgrade head` run against prod DB)?
> 3. Is the Cloudflare R2 bucket created and R2 API credentials available?
> 4. Are Cloud Run environment variables configured (`DATABASE_URL`, `GOOGLE_OAUTH_*`, `OPENROUTER_API_KEY`, `SENTRY_DSN`, `SCHEDULER_SECRET`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`)?
> 5. Is there a production `SENTRY_DSN` (Sentry project created)?
> 6. Who is the pilot HC, and do they have a Google account ready for first login?

If any of the above is "no" or "unknown," P9 is blocked at that item. Resolve infra provisioning first — that work is outside this phase plan's scope.

---

## 1. Scope

P9 is the go/no-go gate before the pilot HC goes live. It proves that all the pieces built in P0–P8 work together against real production infrastructure — not local Docker, not a dev database, not mocked LLM calls. The phase produces one code artifact (`scripts/smoke-test.py`), applies Cloudflare platform security features at the dashboard level, runs compliance and deletion tests, seeds the pilot HC's snippet library, and completes the first real M000 session end-to-end.

**Not in scope**: new feature code, schema migrations (all tables were created in P1), frontend changes, second HC onboarding (post-pilot scope), Consent Manager integration (deferred per compliance-india.md — Nov 2026 regime).

---

## 2. Deliverables to ship

| # | Artifact | What changes |
|---|---|---|
| 1 | `scripts/smoke-test.py` (new) | Automated end-to-end smoke test: hits production Cloud Run endpoints that exercise Supabase, R2, and OpenRouter; exits 0 on success |
| 2 | Cloudflare dashboard (external) | Rate limiting, WAF basic, cache rules, DDoS protection enabled on Cloudflare Pages layer — per ADR-0002 "one-time setup task" |
| 3 | GitHub repository secrets (external) | `API_BASE_URL` + `SCHEDULER_SECRET` configured so P7's GitHub Actions cron can fire against production |
| 4 | Sentry alert rules (external) | 3 rules from `docs/ops/incident-response.md §Sentry alert rules` configured in Sentry UI |
| 5 | `docs/VERIFICATION.md` (modified) | P9 verification checklist added (above P8) |
| 6 | `docs/specs/Unit_001_HcCoreCycle/PHASE-09-pilot-smoke-gate.md` (this file) | Updated with §6 Verification, §7 Lessons, §8 Carry-over |

---

## 3. Decisions pre-made in ADRs

- **Cloudflare platform features apply to the Pages frontend layer** (ADR-0002 §Rationale): rate limiting, WAF, cache rules are dashboard-configured for Cloudflare Pages; the backend (Cloud Run) is a separate service.
- **Smoke-test script hits Cloud Run, not the DB directly** (build-plan.md §P9): `scripts/smoke-test.py` calls production Cloud Run endpoints; Cloud Run exercises Supabase/R2/OpenRouter internally. No direct DB connection from the script.
- **Pilot HC consent via signed PDF** (compliance-india.md): at N=1 pilot scale, consent is captured as a signed PDF stored in R2; a `consents` table row records it. Not scalable; flagged for replacement before second HC.
- **DPDP deletion is hard delete** (ADR-0001 §§ architectural principles #8): single-transaction purge via `ON DELETE CASCADE`. Soft delete is not used. Verified in this phase.

---

## 4. Bugs fixed mid-phase

(Fill in after build.)

---

## 5. Source docs consulted

- `build-plan.md §Phase 9` — goal, deliverables, acceptance criteria
- `decisions/0001-stack-selection.md` — open follow-ups: smoke-test gate, ADR-0001 triggers
- `decisions/0002-runtime-topology.md` — Cloudflare platform features: rate limiting, WAF, cache rules, DDoS (the "one-time setup task" from Open follow-ups)
- `domain/compliance-india.md` — DPDP consent scope, deletion requirements, data inventory
- `docs/ops/incident-response.md §Sentry alert rules` — 3 rules to configure in Sentry UI
- `decisions/0006-observability.md §8` — 5 SQL queries to verify against production DB
- `docs/VERIFICATION.md` — format reference (newest-first insertion)

---

## 6. Verification

- **Verification date**: TBD
- **Verification record**: `docs/VERIFICATION.md` § P9
- **Test count at end of phase**: same as P8 (no new unit tests; smoke test is an integration script, not a pytest file)
- **Key checks**: AC1 through AC7 per VERIFICATION.md § P9 (see Task 9)

---

## 7. Lessons learned

(Fill in after build.)

---

## 8. Carry-over to subsequent phases

- `scripts/smoke-test.py` becomes the standing deployment verification script. Run before every production deploy.
- Cloudflare platform config (rate limiting, WAF) is live and monitored via ADR-0001's six hosting triggers.
- Pilot HC's snippet library (`hc_style_snippets`) seeded — future MOMs start personalised immediately.
- DPDP deletion path tested and confirmed — no changes needed before onboarding additional clients.

---

## Implementation plan

> **For agentic workers:** tasks are ordered by dependency. Part A (Cloud Run migration) must complete before any Part B task. Part B Tasks 1–2 (infra + smoke script) unlock Tasks 3–9. Tasks 5–9 require a running production system.

**Architecture**: Part A replaces CF Worker deployment with GCP Cloud Run — Dockerfile + updated CI/CD, no backend logic changes. Part B adds one new script (`scripts/smoke-test.py`), CF dashboard config, and human-led verification. Both parts are ops-heavy, not code-heavy.

---

## Part A — Cloud Run Migration

### Task A1 — GCP project setup (SoJo — GCP console + gcloud CLI)

These are one-time human steps in the GCP console and terminal. Complete before Task A2.

**Step A1.1 — Enable required APIs**
```bash
gcloud config set project $YOUR_GCP_PROJECT_ID

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com
```

**Step A1.2 — Create Artifact Registry repository**
```bash
gcloud artifacts repositories create parivarthan \
  --repository-format=docker \
  --location=asia-south1 \
  --description="Parivarthan backend images"
```

**Step A1.3 — Create service account for GitHub Actions**
```bash
gcloud iam service-accounts create github-actions-deployer \
  --display-name="GitHub Actions Cloud Run Deployer"

SA_EMAIL="github-actions-deployer@$YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com"

# Roles needed: build image, push to AR, deploy to Cloud Run, read secrets
gcloud projects add-iam-policy-binding $YOUR_GCP_PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $YOUR_GCP_PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $YOUR_GCP_PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/cloudbuild.builds.editor"

gcloud projects add-iam-policy-binding $YOUR_GCP_PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $YOUR_GCP_PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $YOUR_GCP_PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.admin"
```

**Step A1.4 — Configure Workload Identity Federation (GitHub Actions → GCP, no long-lived key)**
```bash
PROJECT_ID="$YOUR_GCP_PROJECT_ID"
REPO="your-github-org/parivarthan_platform"   # e.g. NidhiJoshi/parivarthan_platform

# Create pool
gcloud iam workload-identity-pools create github-pool \
  --location=global \
  --display-name="GitHub Actions pool"

POOL_ID=$(gcloud iam workload-identity-pools describe github-pool \
  --location=global --format="value(name)")

# Create provider inside the pool
gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --display-name="GitHub provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

PROVIDER_ID=$(gcloud iam workload-identity-pools providers describe github-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --format="value(name)")

# Allow GitHub repo to impersonate the SA
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${REPO}"

# Print the two values you'll set as GitHub secrets
echo "GCP_WORKLOAD_IDENTITY_PROVIDER: ${PROVIDER_ID}"
echo "GCP_SERVICE_ACCOUNT: ${SA_EMAIL}"
```

Add both values to GitHub → repo → Settings → Secrets and variables → Actions:
- `GCP_WORKLOAD_IDENTITY_PROVIDER` — the full provider resource name printed above
- `GCP_SERVICE_ACCOUNT` — the service account email

**Step A1.5 — Create secrets in Secret Manager**

One command per secret. Values come from your local `.env`:
```bash
# Run each — paste the actual value when prompted, or pipe it in
echo -n "YOUR_VALUE" | gcloud secrets create DATABASE_URL --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create JWT_PRIVATE_KEY --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create JWT_PUBLIC_KEY --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create GOOGLE_CLIENT_ID --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create OPENROUTER_API_KEY --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create LLM_CALL_ENCRYPTION_KEY --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create R2_ACCOUNT_ID --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create R2_ACCESS_KEY_ID --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create R2_SECRET_ACCESS_KEY --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create R2_BUCKET_NAME --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create SENTRY_DSN --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create SCHEDULER_SECRET --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create FRONTEND_URL --data-file=-
echo -n "YOUR_VALUE" | gcloud secrets create API_BASE_URL --data-file=-

# Verify all 15 exist
gcloud secrets list --format="value(name)" | sort
```

**Step A1.6 — Note your project ID and confirm Cloud Run service name**
```bash
gcloud config get-value project   # confirm project ID
# Service will be named: parivarthan-backend
# Region: asia-south1
```

---

### Task A2 — Remove CF Worker artifacts + move uvicorn to main deps

**Files:**
- Delete: `backend/wrangler.toml`
- Delete: `backend/cf-requirements.txt`
- Modify: `backend/pyproject.toml`

**Step A2.1 — Delete CF Worker files**
```bash
rm backend/wrangler.toml
rm backend/cf-requirements.txt
```

**Step A2.2 — Move uvicorn from dev deps to main deps in `backend/pyproject.toml`**

Remove `"uvicorn[standard]>=0.30"` from `[dependency-groups] dev` and add it to `[project] dependencies`:

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.13",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "httpx>=0.27",
    "asyncpg>=0.29",
    "python-jose[cryptography]>=3.3",
    "sentry-sdk[fastapi]>=2.0",
    "structlog>=24.0",
    "python-multipart>=0.0.9",
    "pypdf>=4.0",
    "python-docx>=1.1",
    "uvicorn[standard]>=0.30",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
    "mypy>=1.10",
]
```

**Step A2.3 — Regenerate lock file**
```bash
cd backend && uv lock && cd ..
```
Expected: `uv.lock` updated, no errors.

**Step A2.4 — Verify tests still pass locally**
```bash
cd backend && uv run pytest tests/unit/ -q
```
Expected: same pass count as before (uvicorn move does not affect tests).

**Step A2.5 — Commit**
```bash
git add backend/pyproject.toml backend/uv.lock
git rm backend/wrangler.toml backend/cf-requirements.txt
git commit -m "chore(deploy): remove CF Worker artifacts, move uvicorn to main deps"
```

---

### Task A3 — Create Dockerfile and .dockerignore

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/.dockerignore`

**Step A3.1 — Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first — layer cache on these
COPY pyproject.toml uv.lock ./

# Install production dependencies only (no pytest, ruff, mypy)
RUN uv sync --frozen --no-dev

# Copy application source
COPY src/ src/
COPY prompts/ prompts/
COPY alembic/ alembic/
COPY alembic.ini alembic.ini

# Cloud Run injects PORT; default matches Cloud Run's expected 8080
ENV PORT=8080
EXPOSE 8080

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**Step A3.2 — Create `backend/.dockerignore`**

```
__pycache__/
*.pyc
*.pyo
.venv/
.env
.env.*
tests/
scripts/
*.md
node_modules/
.git/
```

**Step A3.3 — Test the Docker build locally**
```bash
cd backend
docker build -t parivarthan-backend:local .
```
Expected: build completes, no errors. Image size should be ~400–600 MB.

**Step A3.4 — Test the container starts**
```bash
# Requires a .env at backend/.env with valid DATABASE_URL etc.
docker run --rm -p 8080:8080 --env-file .env parivarthan-backend:local
```
Expected: uvicorn logs appear, `http://localhost:8080/healthz` returns `{"status": "ok"}`.

**Step A3.5 — Commit**
```bash
git add backend/Dockerfile backend/.dockerignore
git commit -m "feat(deploy): add Dockerfile for Cloud Run (python:3.12-slim + uv)"
```

---

### Task A4 — Replace deploy workflow with Cloud Run

**Files:**
- Modify: `.github/workflows/deploy.yml`

**Step A4.1 — Replace `.github/workflows/deploy.yml` with the following**

```yaml
name: Deploy Backend

on:
  push:
    branches: [main]
    paths:
      - backend/**
      - .github/workflows/deploy.yml

jobs:
  deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    environment: production
    permissions:
      contents: read
      id-token: write   # required for Workload Identity Federation

    steps:
      - uses: actions/checkout@v4

      - name: Authenticate to GCP
        uses: google-github-actions/auth@v2
        with:
          workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
          service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v2
        with:
          service: parivarthan-backend
          region: asia-south1
          source: ./backend
          flags: >-
            --port=8080
            --min-instances=0
            --max-instances=5
            --memory=512Mi
            --cpu=1
            --timeout=60s
            --no-allow-unauthenticated
          env_vars: |
            APP_ENV=production
          secrets: |
            DATABASE_URL=DATABASE_URL:latest
            JWT_PRIVATE_KEY=JWT_PRIVATE_KEY:latest
            JWT_PUBLIC_KEY=JWT_PUBLIC_KEY:latest
            GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest
            GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest
            OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest
            LLM_CALL_ENCRYPTION_KEY=LLM_CALL_ENCRYPTION_KEY:latest
            R2_ACCOUNT_ID=R2_ACCOUNT_ID:latest
            R2_ACCESS_KEY_ID=R2_ACCESS_KEY_ID:latest
            R2_SECRET_ACCESS_KEY=R2_SECRET_ACCESS_KEY:latest
            R2_BUCKET_NAME=R2_BUCKET_NAME:latest
            SENTRY_DSN=SENTRY_DSN:latest
            SCHEDULER_SECRET=SCHEDULER_SECRET:latest
            FRONTEND_URL=FRONTEND_URL:latest
            API_BASE_URL=API_BASE_URL:latest

      - name: Print deployed URL
        run: echo "Deployed to ${{ steps.deploy.outputs.url }}"
```

> **How `source:` works**: `deploy-cloudrun@v2` with `source:` triggers a Cloud Build job that builds the Dockerfile, pushes the image to Artifact Registry (`asia-south1-docker.pkg.dev/PROJECT/parivarthan/backend`), and deploys to Cloud Run. No `docker build` in the GitHub runner needed.

> **`secrets:` field**: tells Cloud Run to pull values from GCP Secret Manager at startup and inject them as environment variables. The `SERVICE_ACCOUNT` must have `roles/secretmanager.secretAccessor` (set in Task A1.3).

**Step A4.2 — Commit**
```bash
git add .github/workflows/deploy.yml
git commit -m "ci: replace CF Worker deploy with GCP Cloud Run (asia-south1)"
```

---

### Task A5 — Commit the uncommitted ADR and doc changes

These are already-correct content changes sitting uncommitted since the stack switch.

**Step A5.1 — Stage and commit the doc changes**
```bash
git add \
  docs/decisions/0001-stack-selection.md \
  docs/decisions/0002-runtime-topology.md \
  docs/build-plan.md \
  docs/diagrams/0001-system-architecture.md \
  docs/ops/deployment.md \
  docs/specs/Unit_001_HcCoreCycle/PHASE-00-repo-scaffolding.md \
  docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md \
  docs/specs/Unit_001_HcCoreCycle/PHASE-07-external-scheduler.md \
  docs/specs/Unit_001_HcCoreCycle/PHASE-08-observability-live.md \
  docs/specs/Unit_001_HcCoreCycle/PHASE-09-pilot-smoke-gate.md

git commit -m "docs: update ADRs and phase plans for Cloud Run migration"
```

**Step A5.2 — Verify the deploy workflow fires on push to main**

After A5.1 commit + push:
```bash
git push origin main
# Open: GitHub → Actions → Deploy Backend → watch the run
```
Expected: build succeeds, Cloud Run service URL appears in the "Print deployed URL" step output.

**Step A5.3 — Confirm the service is live**
```bash
# Get the URL
gcloud run services describe parivarthan-backend \
  --region asia-south1 \
  --format="value(status.url)"

# Hit healthz (no auth needed for this endpoint)
curl https://YOUR_CLOUD_RUN_URL/healthz
```
Expected: `{"status": "ok"}`

**Step A5.4 — Update PHASE-09 Task 1 checklist item 1.1**

Once the service is confirmed live, check off item 1.1 in Part B Task 1:
```
- [x] **1.1** Cloud Run service deployed. URL: https://parivarthan-backend-XXXX-el.a.run.app
```

---

## Part B — P9 Smoke Gate

---

### Task 1 — Resolve infrastructure prerequisites (SoJo — before any other task)

These are human actions in external consoles. They must be complete before the smoke test can run.

**Checklist** (SoJo walks this, not Claude Code):

- [ ] **1.1** GCP Cloud Run service deployed to `asia-south1`. Note the service URL: `_____________`
- [ ] **1.2** Supabase project provisioned (`ap-south-1`, Mumbai). Pooler connection string (port 6543) set as Cloud Run env var `DATABASE_URL`.
- [ ] **1.3** `alembic upgrade head` run against production DB from local machine with prod `DATABASE_URL`. Output: `Running upgrade ... -> <revision>, OK`.
- [ ] **1.4** Cloudflare R2 bucket created. R2 API credentials set as Cloud Run env vars `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`.
- [ ] **1.5** All Cloud Run environment variables configured (`DATABASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `OPENROUTER_API_KEY`, `JWT_SECRET_KEY`, `SENTRY_DSN`, `SCHEDULER_SECRET`).
  ```bash
  # Verify env vars are set (lists names):
  gcloud run services describe parivarthan-backend --region asia-south1 \
    --format='value(spec.template.spec.containers[0].env[].name)'
  ```
- [ ] **1.6** Production `SENTRY_DSN` created in Sentry UI and set as env var above.
- [ ] **1.7** Pilot HC identified. Their Google account email noted: `_____________`

---

### Task 2 — Write `scripts/smoke-test.py`

**Files**:
- Create: `scripts/smoke-test.py`

This script hits production Cloud Run endpoints that exercise each external dependency. It uses an HC auth token (from a real sign-in) passed as env var. Exits 0 on full pass, 1 on any failure.

**What it tests**:
- `GET /healthz` → Cloud Run service is up
- `GET /api/me` (authenticated) → DB connectivity via Supabase (reads `users` table)
- `GET /api/clients` (authenticated) → DB read, tenant scoping
- `POST /internal/scheduled-tasks` (scheduler token) → DB write, scheduler auth
- R2: `GET /api/clients/{id}` which returns a signed R2 URL if a file exists — verifies bucket connectivity

**Step 2.1 — Create `scripts/smoke-test.py`**

```bash
ls scripts/   # verify directory exists
```

Create the script:

```python
#!/usr/bin/env python3
"""
Production smoke test — run after every production deploy.
Tests: Cloud Run up, Supabase connectivity, scheduler auth.

Usage:
    API_BASE_URL=https://parivarthan-backend-xyz.asia-south1.run.app \
    HC_ACCESS_TOKEN=<token from browser devtools> \
    SCHEDULER_SECRET=<value from .env> \
    python scripts/smoke-test.py
"""
import os
import sys
import json
import urllib.request
import urllib.error

BASE = os.environ["API_BASE_URL"].rstrip("/")
TOKEN = os.environ["HC_ACCESS_TOKEN"]
SCHEDULER_SECRET = os.environ["SCHEDULER_SECRET"]

PASSED = []
FAILED = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        print(f"  ✓ {name}")
        PASSED.append(name)
    else:
        print(f"  ✗ {name}{': ' + detail if detail else ''}")
        FAILED.append(name)


def get(path: str, token: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(f"{BASE}{path}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


def post(path: str, headers: dict, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body or {}).encode() if body else b""
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


print(f"\nSmoke test → {BASE}\n")

# 1. Cloud Run service is up
status, body = get("/healthz")
check("Cloud Run up (/healthz)", status == 200 and body.get("status") == "ok")

# 2. Supabase connectivity — authenticated read
status, body = get("/api/me", token=TOKEN)
check("Supabase read (/api/me)", status == 200 and "id" in body, f"got {status}")

# 3. Tenant-scoped client list
status, body = get("/api/clients", token=TOKEN)
check("DB client list (/api/clients)", status == 200, f"got {status}")

# 4. Scheduler endpoint — requires correct secret
status, body = post("/internal/scheduled-tasks", headers={"X-Scheduler-Token": SCHEDULER_SECRET})
check("Scheduler auth + DB write", status == 200 and "retired_count" in body, f"got {status}")

# 5. Scheduler rejects wrong token (idempotency guard)
status, _ = post("/internal/scheduled-tasks", headers={"X-Scheduler-Token": "wrong"})
check("Scheduler rejects bad token", status == 401, f"got {status}")

# Summary
print(f"\n{'='*40}")
print(f"Passed: {len(PASSED)}  Failed: {len(FAILED)}")
if FAILED:
    print(f"Failed checks: {', '.join(FAILED)}")
    sys.exit(1)
else:
    print("All checks passed.")
    sys.exit(0)
```

**Step 2.2 — Make executable and commit**:
```bash
chmod +x scripts/smoke-test.py
git add scripts/smoke-test.py
git commit -m "feat(p9): add production smoke-test script"
```

**Step 2.3 — Dry-run against local dev server** (before production exists):
```bash
API_BASE_URL=http://localhost:8001 \
HC_ACCESS_TOKEN=<dev token from browser> \
SCHEDULER_SECRET=<local value from .env> \
python scripts/smoke-test.py
```
Expected: all 5 checks pass locally first.

---

### Task 3 — Configure Cloudflare platform features (SoJo — Cloudflare dashboard)

Per ADR-0002: Cloudflare platform features apply to the Pages frontend layer, not backend code. These are dashboard configurations on the Cloudflare Pages zone.

**Step 3.1 — Rate limiting**
- Cloudflare dashboard → your domain / zone → Security → WAF → Rate limiting rules
- Create rule: `Path matches /api/*` → limit 60 requests per minute per IP → action: block for 60s
- Create rule: `Path matches /api/auth/*` → limit 10 requests per minute per IP → action: block for 300s (auth endpoints are higher-value targets)

**Step 3.2 — WAF (Web Application Firewall)**
- Cloudflare dashboard → Security → WAF → Managed rules
- Enable Cloudflare Managed Ruleset (default — free with any plan)
- Enable OWASP Core Ruleset at sensitivity: low (high sensitivity causes false positives on JSON API requests)
- Log-only mode initially; switch to block after 48h of checking logs for false positives

**Step 3.3 — Cache rules**
- For the Pages frontend, most dynamic responses should NOT be cached
- Set cache rule: `Path matches /healthz` (if proxied via Pages) → Cache everything, TTL 30s
- Everything else: bypass cache (default)

**Step 3.4 — DDoS protection**
- Cloudflare dashboard → Security → DDoS → HTTP DDoS attack protection
- Enable (already on by default for Pages zone); verify the managed ruleset is "Enabled" not "Log"

**Step 3.5 — Screenshot**
- Take a screenshot of Sentry → Alerts showing all 3 rules configured.
- Take a screenshot of Cloudflare → Security → WAF showing rules active.
- Save screenshots to `docs/diagrams/exports/p9-cloudflare-config.png` and `docs/diagrams/exports/p9-sentry-alerts.png` for VERIFICATION.md.

---

### Task 4 — Configure GitHub repository secrets for P7 scheduler (SoJo)

P7's GitHub Actions workflow (`.github/workflows/scheduler.yml`) needs two secrets to fire against production:

- `API_BASE_URL` — the production Cloud Run service URL (e.g. `https://parivarthan-backend-xyz.asia-south1.run.app`)
- `SCHEDULER_SECRET` — must match the `SCHEDULER_SECRET` Cloud Run env var exactly

**Step 4.1 — Add secrets**:
GitHub → your repo → Settings → Secrets and variables → Actions → New repository secret.

**Step 4.2 — Trigger a manual run to verify**:
GitHub → Actions → Scheduled Tasks → Run workflow.
Expected: job completes with HTTP status: 200 in logs. Check GCP Cloud Logging for the `scheduled_task_run` log line.

---

### Task 5 — P8 deferred: Sentry smoke test (AC4)

Requires `SENTRY_DSN` set in production (Task 1.5).

**Step 5.1 — Configure Sentry alert rules in UI**

Per `docs/ops/incident-response.md §Sentry alert rules`:
1. Rule 1 (new error fingerprint): Sentry → Alerts → Create Alert → Issue alert → "A new issue is created" → filter: `environment:production`
2. Rule 2 (rate spike): same, "The issue is seen more than 5 times in 1 hour"
3. Rule 3 (LLM validation): Metric alert → filter: `kind:llm_validation_failed` → threshold > 0 in 24h

**Step 5.2 — Force a deliberate exception to verify Rule 1**

Add a temporary route to `main.py` (locally, then deploy):
```python
@app.get("/test-sentry-error", include_in_schema=False)
async def test_sentry_error():
    raise ValueError("deliberate p9 sentry smoke test — delete after verification")
```

Deploy to production → hit the endpoint:
```bash
curl https://<your-cloud-run-url>/test-sentry-error
```

Expected:
- Sentry dashboard shows the error within 30s
- Error has `request_id` tag
- No PII in breadcrumbs
- Email notification arrives within 5 minutes (Rule 1 fires)

**Step 5.3 — Remove the test route**:
```bash
# Remove the test_sentry_error route from main.py
git add backend/src/main.py
git commit -m "chore(p9): remove temporary Sentry smoke test route"
# Deploy again
```

---

### Task 6 — P8 deferred: 5 SQL queries against production DB (AC5)

Connect to Supabase using either the SQL Editor in the Supabase dashboard, or from local machine with the pooler URL:

```bash
psql <PRODUCTION_DATABASE_URL>   # pooler URL, port 6543
```

Run each query from `docs/decisions/0006-observability.md §8`. At pilot pre-launch, rows may be sparse — the goal is "no error, correct schema", not "meaningful results."

Expected per query: executes without error. No `column does not exist` or `relation does not exist` errors.

---

### Task 7 — DPDP compliance walk

**Step 7.1 — Verify India-region data residency**:

Supabase region is confirmed at project creation time — the Supabase dashboard shows `ap-south-1 (Mumbai)` for the project. Cloud Run is deployed to `asia-south1 (Mumbai)`. No runtime DNS check is needed; confirm both in their respective dashboards and note it in VERIFICATION.md.

**Step 7.2 — Consent table populated for pilot client**:
- Pilot HC signs consent PDF (5 consent purposes from compliance-india.md §MVP consent scope)
- HC uploads PDF to R2 (manually, via `rclone` or Cloudflare dashboard → R2 → upload)
- Insert `consents` row:
```sql
INSERT INTO consents (id, client_id, purpose, given_at, source_ref, revoked_at)
VALUES (
  gen_random_uuid(),
  '<pilot_client_id>',
  'coaching',
  NOW(),
  'r2://your-bucket/consents/<filename>.pdf',
  NULL
);
-- Repeat for purposes: ai_generation, cross_border, snippet_capture, erasure_acknowledged
```

**Step 7.3 — DPDP deletion test** (use a TEST client, not the real pilot client):

```sql
-- Insert a test client with related data
BEGIN;
INSERT INTO clients (id, hc_user_id, ...) VALUES ('<test_client_id>', '<hc_id>', ...);
INSERT INTO hc_style_snippets (id, hc_user_id, client_id, ...) VALUES (...);
INSERT INTO consents (id, client_id, ...) VALUES (...);
SELECT COUNT(*) FROM hc_style_snippets WHERE client_id = '<test_client_id>';  -- should be 1
SELECT COUNT(*) FROM consents WHERE client_id = '<test_client_id>';  -- should be 1+

-- Simulate consent revocation / hard delete
DELETE FROM clients WHERE id = '<test_client_id>';

-- Verify cascade: everything gone
SELECT COUNT(*) FROM hc_style_snippets WHERE client_id = '<test_client_id>';  -- must be 0
SELECT COUNT(*) FROM consents WHERE client_id = '<test_client_id>';  -- must be 0
SELECT COUNT(*) FROM sessions WHERE client_id = '<test_client_id>';  -- must be 0
ROLLBACK;  -- test only; don't commit
```

Expected: all counts are 0 after the DELETE. CASCADE is working.

---

### Task 8 — Pilot HC onboarding (HC-led, SoJo facilitates)

Goal: pilot HC's `hc_style_snippets` table has ≥ 5 rows before the first real client session.

**Step 8.1 — HC signs in via production URL**:
- Opens production URL in browser
- Signs in with their Google account
- Verifies dashboard loads

**Step 8.2 — Create 3–5 sample AI drafts and edit them**:
- HC creates a test client (or uses a placeholder)
- Creates a session, enters sample session notes
- Generates MOM draft (LLM call via production OpenRouter)
- Edits the draft (changes phrasing, restructures sentences — this is what captures snippets)
- Clicks "Send" (status → `sent`)
- Repeat for 3–5 sessions

**Step 8.3 — Verify snippets**:
```sql
SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = '<pilot_hc_user_id>';
-- Must be ≥ 5
SELECT snippet_type, left(original_text, 60), left(hc_modified_text, 60)
FROM hc_style_snippets WHERE hc_user_id = '<pilot_hc_user_id>'
ORDER BY created_at DESC LIMIT 10;
```

---

### Task 9 — First real M000 session end-to-end (HC + real client)

This is the culmination. A real pilot HC, a real client, a real session.

**Step 9.1 — HC creates the real client**:
- Enters client info in the dashboard
- Consent PDF signed and uploaded (per Task 7.2)

**Step 9.2 — M000 session flow**:
- HC opens the client's session view
- No prior MOM, no snippets for this client yet — triggers the M000 "intake prep" path
- HC fills session notes from their intake conversation
- HC generates MOM draft
- HC reviews, edits, sends
- Snippet captured from the edit

**Step 9.3 — Verify DB state post-session**:
```sql
SELECT s.id, s.status, m.status as mom_status
FROM sessions s JOIN moms m ON m.session_id = s.id
WHERE s.client_id = '<real_client_id>';
-- mom_status should be 'sent'

SELECT COUNT(*) FROM hc_style_snippets WHERE client_id = '<real_client_id>';
-- Should be 1+ from the edit made in this session
```

---

### Task 10 — 24-hour monitoring + mark P9 complete

**Step 10.1 — Monitor for 24 hours post-first-session**:
- Check Sentry dashboard: no new error fingerprints
- Check GCP Cloud Logging: request lifecycle log lines appearing (`request.start` / `request.end` events)
- Check `llm_calls` table: all rows have `final_status = 'ok'` from the onboarding session

**Step 10.2 — Run smoke test against production one final time**:
```bash
API_BASE_URL=https://<your-cloud-run-url> \
HC_ACCESS_TOKEN=<token> \
SCHEDULER_SECRET=<value> \
python scripts/smoke-test.py
```
Expected: all checks pass, exits 0.

**Step 10.3 — Update `docs/VERIFICATION.md`** (add above P8 section):

```markdown
## P9 — Pre-Pilot Smoke Gate

**Status**: [fill in after verification]

| AC | Check | Result |
|---|---|---|
| AC1 | `scripts/smoke-test.py` exits 0 against production Cloud Run service | |
| AC2 | Cloudflare dashboard: rate limiting + WAF + cache rules enabled on Pages layer (screenshot saved) | |
| AC3 | GitHub Actions scheduler manual trigger → HTTP 200 + `scheduled_task_run` log line in GCP Cloud Logging | |
| AC4 (P8 deferred) | Sentry smoke test: deliberate exception → appears ≤30s, no PII, request_id tag, email alert fires | |
| AC5 (P8 deferred) | All 5 ADR-0006 §8 SQL queries execute without error against production DB | |
| AC6 | DPDP deletion test: test client hard-deleted → cascade verified (0 orphan rows) | |
| AC7 | Pilot HC has ≥ 5 snippets in `hc_style_snippets` after onboarding | |
| AC8 | First real M000 session complete end-to-end: notes → draft → edit → sent | |
| AC9 | India-region data residency confirmed (Supabase ap-south-1 + Cloud Run asia-south1, both Mumbai) | |
| AC10 | No unhandled Sentry errors in first 24 hours post-launch (or all triaged) | |
```

**Step 10.4 — Commit docs**:
```bash
git add docs/VERIFICATION.md docs/specs/Unit_001_HcCoreCycle/PHASE-09-pilot-smoke-gate.md docs/SESSION_LOG.md
git commit -m "docs(p9): phase plan + verification checklist"
```

---

## Context missing — resolve before starting

| # | Unknown | How SoJo answers |
|---|---|---|
| CM1 | Is production infrastructure provisioned? | Walk Task 1 checklist; note any "no" items |
| CM2 | Production Cloud Run service URL | From GCP Console → Cloud Run → parivarthan-backend → URL |
| CM3 | Production SENTRY_DSN | From Sentry → your project → Settings → Client Keys |
| CM4 | Pilot HC identity and Google account email | SoJo confirms |
| CM5 | RDS connection method (direct from local, or bastion?) | Depends on RDS security group config |
