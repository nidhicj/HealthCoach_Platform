# PHASE-09: Pre-Pilot Smoke Gate

**Unit**: Unit_001_HcCoreCycle
**Status**: Part A — Complete (as-built). Part B — Infrastructure Setup (design complete, implementation pending). Part C — Blocked pending Part B.
**Verification date**: TBD — see `docs/VERIFICATION.md` § P9
**Implements**: `build-plan.md §Phase 9` acceptance criteria
**ADRs implemented**: ADR-0001 (stack — smoke gate + open follow-ups), ADR-0002 (runtime topology — Cloudflare platform features one-time setup), `domain/compliance-india.md` (DPDP hooks walkthrough)

---

## Changelog

| Version | Date | Author | What changed |
|---|---|---|---|
| v1.0 | pre-2026-06-23 | SoJo + Claude | Original plan drafted — Part A assumed GitHub Actions CI/CD |
| v1.1 | 2026-06-23 | SoJo + Claude | Part A rewritten to reflect as-built: Cloud Build trigger (not GitHub Actions). Service name corrected to `hc-platform`. `/healthz` → `/health` throughout. Part A marked complete. GitHub Actions references superseded — see §Part A As-Built. |
| v1.2 | 2026-06-23 | SoJo + Claude | Part B added: Infrastructure Setup design (Cloud SQL replaces Supabase, Cloud Run for frontend replaces Cloudflare Pages, CI/CD refactored to per-service triggers, backend renamed to `hc-platform-backend`). Existing smoke gate tasks moved to Part C. |
| v1.3 | 2026-06-23 | SoJo + Claude | Part B implementation plan added: 7 tasks (3 code, 4 GCP ops). Covers `backend/cloudbuild.yaml`, `frontend/Dockerfile` (standalone, repo-root context), `frontend/cloudbuild.yaml` (NEXT_PUBLIC_API_URL via availableSecrets build arg), Cloud SQL provisioning, migration run, frontend deploy, secret wiring. |

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

| Bug | Root cause | Fix |
|---|---|---|
| `/healthz` returns Google HTML 404 | GFE intercepts `/healthz` (Kubernetes reserved path) before request reaches container | Renamed route to `/health` in `main.py` |
| Cloud Build trigger deployed placeholder image | Auto-created trigger used buildpacks (`pack`) which can't build Python/uv project | Added `cloudbuild.yaml` with Docker steps; updated trigger to use it |
| Sentry `BadDsn` crashes container startup | `SENTRY_DSN` secret contained placeholder value `XXXXXXX`; Sentry SDK validates DSN format on init | Wrapped `sentry_sdk.init()` in `try/except Exception: pass` in `sentry.py` |
| `gcloud run services logs read` crashes CLI | Bug in gcloud SDK (`TypeError: sequence item 1: expected str instance, NoneType found`) | Workaround: use `gcloud logging read` directly |

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

- **`/healthz` is a reserved path on Cloud Run (GFE).** GFE absorbs `/healthz`, `/readyz`, `/livez` before they reach the container — Kubernetes internals. Use `/health` or `/api/health`. Test your health endpoint on the same running instance simultaneously with a known-good path — if one returns JSON and the other returns Google HTML 404, it's being intercepted.
- **Cloud Build trigger region is always "global".** The trigger shows "global" in Cloud Build history regardless of the Cloud Run service region. This is normal — trigger region ≠ deployment region. Outputs (image, service) land in the correct region per `cloudbuild.yaml`.
- **Buildpacks cannot build Python/uv projects.** The GCP "Connect to repo" auto-trigger uses buildpacks which expect `requirements.txt`. Any uv-managed project needs a `cloudbuild.yaml` with explicit Docker steps.
- **Secrets in Secret Manager are NOT automatically available to Cloud Run.** They must be explicitly mounted via `--update-secrets` flags on the service, and on every deploy command. The `cloudbuild.yaml` deploy step must include all `--update-secrets` flags.
- **Placeholder values in secrets crash the app on startup.** `SENTRY_DSN=XXXXXXX` passed the `if not dsn` guard but failed Sentry SDK's DSN parser. Always wrap third-party SDK init calls in `try/except` when the config may be a placeholder. Or set secrets to truly empty string.
- **GitHub Actions CI/CD was never the deployed approach.** `.github/workflows/deploy.yml` deploys to `parivarthan-api` which was deleted. The actual CI/CD path is Cloud Build trigger → `cloudbuild.yaml` → Cloud Run. The Actions workflow is dead code.

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

## Part A — Cloud Run Migration (AS-BUILT — supersedes Tasks A1–A5)

> **v1.1 note**: Tasks A1–A5 below were the original plan and assumed GitHub Actions CI/CD via Workload Identity Federation. The actual execution took a different path. The as-built record is documented here. The original task steps are preserved below for reference but are superseded.

### Part A — As-Built Record (2026-06-23)

**What was done** (in execution order):

**A-actual-1: GCP APIs and secrets** — APIs already enabled (`run.googleapis.com`, `cloudbuild.googleapis.com`, `secretmanager.googleapis.com`, `artifactregistry.googleapis.com`). All 15 secrets created in Secret Manager via `gcloud secrets create`. Confirmed with `gcloud secrets list`.

**A-actual-2: Cloud Run service created via GCP Console "Connect to repo"** — Used the Cloud Run Console UI to create the service and connect it directly to GitHub repo `nidhicj/HealthCoach_Platform`. This automatically created a Cloud Build trigger (`rmgpgab-hc-platform-asia-south1-nidhicj-HealthCoach-Platformrvi`). Service name: `hc-platform` (not `parivarthan-backend` as planned). Region: `asia-south1`.

**A-actual-3: Trigger used buildpacks — failed** — The auto-created trigger used `gcr.io/k8s-skaffold/pack` (buildpacks) which cannot build a Python/uv project (expects `requirements.txt`). First CI deploy at 12:36 UTC produced `gcr.io/cloudrun/placeholder` image. Service was unreachable.

**A-actual-4: Dockerfile and `.dockerignore` created** — `backend/Dockerfile` (python:3.12-slim + uv, CMD uvicorn on port 8080) and `backend/.dockerignore` created as planned in original Task A3.

**A-actual-5: `cloudbuild.yaml` added to repo root** — Instead of updating the GitHub Actions workflow (original Task A4), a `cloudbuild.yaml` was added at repo root. Steps: (1) docker build from `./backend`, (2) push to Artifact Registry, (3) `gcloud run services update hc-platform` with all 15 `--update-secrets` flags. The trigger was updated via GCP Console to use this file instead of its inline buildpack steps.

**A-actual-6: `/healthz` → `/health` rename** — Discovered that `/healthz` is intercepted at the GFE (Google Frontend) layer before reaching the container — inherited Kubernetes reserved path. Renamed route to `/health` in `backend/src/main.py`.

**A-actual-7: Secrets mounted on running service** — `gcloud run services update hc-platform --update-secrets=...` run with all 15 secrets. Verified via `gcloud run services describe`.

**A-actual-8: Sentry crash fixed** — With real secrets mounted, the `SENTRY_DSN` secret contained a placeholder value (`XXXXXXX`). Sentry SDK's DSN parser threw `BadDsn` during app startup lifespan, crashing the container. Fixed by wrapping `sentry_sdk.init()` in `try/except Exception: pass` in `backend/src/telemetry/sentry.py`. App now starts even with a bad/placeholder DSN.

**A-actual-9: CI/CD verified end-to-end** — Push to `main` → Cloud Build trigger fires → `cloudbuild.yaml` runs → Docker build → Artifact Registry push → Cloud Run revision created → traffic shifts. Confirmed with revision `hc-platform-00007-78m` (healthy, serving 100% traffic).

**Final service state**:
- URL: `https://hc-platform-296472807958.asia-south1.run.app`
- Live revision: `hc-platform-00007-78m`
- All 15 secrets mounted as env vars
- `/health` endpoint returning `{"status": "ok"}`
- CI/CD: push to `main` auto-deploys

**What was NOT done in Part A** (superseded by actual approach):
- GitHub Actions Workload Identity Federation (Task A1.3, A1.4) — not needed; Cloud Build trigger uses compute service account directly
- `github-actions-deployer` service account — not created; Cloud Build uses `296472807958-compute@developer.gserviceaccount.com` which already has `roles/secretmanager.secretAccessor`
- `.github/workflows/deploy.yml` update (Task A4) — the existing workflow deploys to deleted service `parivarthan-api`. It is now dead code. Leave in place but do not rely on it.

---

### Task A1 — GCP project setup (SoJo — GCP console + gcloud CLI) [SUPERSEDED — see As-Built above]

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
curl https://YOUR_CLOUD_RUN_URL/health
```
Expected: `{"status": "ok"}`

**Step A5.4 — Update PHASE-09 Task 1 checklist item 1.1**

Once the service is confirmed live, check off item 1.1 in Part B Task 1:
```
- [x] **1.1** Cloud Run service deployed. URL: https://parivarthan-backend-XXXX-el.a.run.app
```

---

## Part B — Infrastructure Setup

> **Design approved**: 2026-06-23. Implementation plan to follow via `writing-plans` skill before any code is written.
> **Why this Part exists**: Part A landed the backend on Cloud Run but left two blocking gaps — no real database and no frontend hosting. Part B resolves both before the smoke gate (Part C) can run.

### B.1 What changed from the original plan

| Original plan | Actual decision | Reason |
|---|---|---|
| Supabase (AWS ap-south-1) for Postgres | **Cloud SQL** (GCP asia-south1) | Auth already handled by FastAPI backend (Google OAuth). Supabase's main advantages (Auth, Studio) are irrelevant. Cloud SQL gives private GCP-internal connectivity, unified billing, and Cloud SQL Insights for troubleshooting. Cost at pilot: ~$10–13/month (db-f1-micro) vs Supabase Pro $25/month. |
| Cloudflare Pages for frontend | **Cloud Run** (`hc-platform-frontend`, asia-south1) | Next.js 16 uses App Router with dynamic routes (`[clientId]`, `[sessionId]`) — cannot statically export. Must run a Node server. Cloud Run is the natural fit given existing backend infrastructure. Firebase Hosting deferred to custom-domain stage. |
| Single Cloud Build trigger (any file → backend deploy) | **Two independent triggers** | One trigger per service, each scoped to its source folder. A docs-only commit does not redeploy either service. |
| Backend service named `hc-platform` | **`hc-platform-backend`** | Symmetry with `hc-platform-frontend`. Rename happens before the frontend is wired up (no live references to break). |

---

### B.2 Target architecture

```
                     ┌─────────────────────────────────────────────┐
                     │             GCP asia-south1                  │
                     │                                              │
Browser ──HTTPS──▶  Cloud Run: hc-platform-frontend (Next.js 16)  │
                     │         │ NEXT_PUBLIC_API_URL (Secret Mgr)  │
                     │         ▼                                    │
                   Cloud Run: hc-platform-backend (FastAPI)         │
                     │         │ Cloud SQL connector (private)      │
                     │         ▼                                    │
                   Cloud SQL: parivarthan-db (Postgres 16)          │
                     │                                              │
                   Secret Manager · Artifact Registry · Cloud Build │
                     └─────────────────────────────────────────────┘
```

All services in project `t-replica-361407`, region `asia-south1`. No public internet between Cloud Run and Cloud SQL.

---

### B.3 Cloud SQL

- **Instance name**: `parivarthan-db`
- **Engine**: Postgres 16
- **Tier**: `db-f1-micro` (shared vCPU, 614 MB RAM) — sufficient for pilot; upgrade is zero-downtime
- **Region**: `asia-south1` (Mumbai) — satisfies DPDP data residency
- **Connectivity from Cloud Run**: Cloud SQL connector via instance connection name. No VPC connector required; the Python driver (`asyncpg`) handles auth + TLS automatically with the connection string format: `postgresql+asyncpg://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE`
- **Local dev / migrations**: `cloud-sql-proxy` binary opens `localhost:5432`; Alembic runs against it normally. One-time tool install per developer machine.
- **Deletion protection**: enabled at instance creation — prevents `gcloud sql instances delete` accidents
- **Secret to update**: `DATABASE_URL` in Secret Manager → Cloud SQL connector URL format
- **First migration**: `alembic upgrade head` run locally via proxy before any Part C task starts

---

### B.4 Frontend Cloud Run service

- **Service name**: `hc-platform-frontend`
- **Region**: `asia-south1`
- **Runtime**: `next start -p 8080` (Cloud Run expects port 8080)
- **Dockerfile**: `frontend/Dockerfile` — multi-stage, `node:22-alpine` builder → slim runner
- **Secrets / env vars via Secret Manager**:
  - `NEXT_PUBLIC_API_URL` → backend Cloud Run URL (new secret to create)
- **Scaling**: `min-instances=0` for pilot (cold start ~1–2 s acceptable); raise to 1 if coaches report sluggish first load (~$5–10/month)
- **URL**: free `*.run.app` with managed SSL — no load balancer needed
- **Backend CORS**: `FRONTEND_URL` secret updated to the frontend `*.run.app` URL after first deploy

---

### B.5 CI/CD — two independent triggers

| Trigger name | `includedFiles` filter | `cloudbuild.yaml` | Deploys to |
|---|---|---|---|
| `backend-deploy` | `backend/**` | `backend/cloudbuild.yaml` | `hc-platform-backend` |
| `frontend-deploy` | `frontend/**`, `scripts/**` | `frontend/cloudbuild.yaml` | `hc-platform-frontend` |

`scripts/**` is included in the frontend trigger because `scripts/build-theme.mjs` runs as a Next.js prebuild step — a change there must rebuild the frontend image.

The existing root-level `cloudbuild.yaml` is retired; each service owns its own build file.

---

### B.6 Backend rename: `hc-platform` → `hc-platform-backend`

Cloud Run does not support rename. Sequence:

1. Update `backend/cloudbuild.yaml` with new service name → push → Cloud Build creates `hc-platform-backend` as a new service
2. Verify `/health` on the new `*.run.app` URL
3. Delete `hc-platform` (`gcloud run services delete hc-platform --region asia-south1`)
4. Update Secret Manager: any secret referencing the old backend URL → new URL

This must happen before the frontend is deployed (nothing is yet pointing at the old URL from a live frontend).

---

### B.7 Migration path to Firebase Hosting (future — custom domain stage)

When a custom domain is ready:

1. `firebase init hosting` — add Firebase to the project
2. Configure `firebase.json` rewrites: static assets from Firebase CDN; SSR routes proxy to `hc-platform-frontend` Cloud Run service
3. Update `FRONTEND_URL` secret → Firebase custom domain (CORS updates on next backend deploy)
4. `hc-platform-frontend` Cloud Run service continues running — Firebase adds the CDN layer in front

Zero changes to Next.js code. The Cloud Run service is not retired; Firebase proxies to it.

---

### B.8 Definition of done for Part B

- [ ] `hc-platform-backend` Cloud Run service live; `/health` returns `{"status": "ok"}`; old `hc-platform` service deleted
- [ ] `backend/cloudbuild.yaml` and `frontend/cloudbuild.yaml` both in repo; root `cloudbuild.yaml` retired
- [ ] Two Cloud Build triggers created and scoped (`backend/**` / `frontend/**` + `scripts/**`)
- [ ] Cloud SQL `parivarthan-db` instance live in asia-south1; deletion protection on
- [ ] `DATABASE_URL` secret updated to Cloud SQL connector format; `alembic upgrade head` run successfully
- [ ] `frontend/Dockerfile` builds and passes local smoke (`curl localhost:3000` returns 200)
- [ ] `hc-platform-frontend` Cloud Run service live at its `*.run.app` URL
- [ ] `NEXT_PUBLIC_API_URL` secret set; `FRONTEND_URL` secret updated to frontend URL
- [ ] End-to-end sign-in flow works in browser against production services

---

## Part B — Implementation plan

> **For agentic workers:** Tasks 1–3 are code changes (Claude). Tasks 4–7 are GCP ops (SoJo — requires `gcloud` CLI and GCP Console). Complete Tasks 1–3 and push before starting Task 4.

**Goal:** Rename backend service, provision Cloud SQL, deploy frontend Cloud Run service, wire all secrets.

**GCP project:** `t-replica-361407` — `asia-south1` throughout.

**Global constraints:**
- All `gcloud` commands target `--region=asia-south1` and `--project=t-replica-361407`
- Cloud SQL instance connection name: `t-replica-361407:asia-south1:parivarthan-db`
- Backend image repo: `asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-backend`
- Frontend image repo: `asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-frontend`
- No secrets in code; all values via Secret Manager

---

### Task 1: Write `backend/cloudbuild.yaml`

**Files:**
- Create: `backend/cloudbuild.yaml`
- Delete (after Task 5 confirms backend deploys): `cloudbuild.yaml` (repo root)

- [ ] **Step 1.1 — Create `backend/cloudbuild.yaml`**

```yaml
steps:
  - name: gcr.io/cloud-builders/docker
    id: Build
    args:
      - build
      - -t
      - asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-backend:$COMMIT_SHA
      - ./backend

  - name: gcr.io/cloud-builders/docker
    id: Push
    args:
      - push
      - asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-backend:$COMMIT_SHA

  - name: gcr.io/google.com/cloudsdktool/cloud-sdk:slim
    id: Deploy
    entrypoint: gcloud
    args:
      - run
      - deploy
      - hc-platform-backend
      - --platform=managed
      - --image=asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-backend:$COMMIT_SHA
      - --region=asia-south1
      - --allow-unauthenticated
      - --add-cloudsql-instances=t-replica-361407:asia-south1:parivarthan-db
      - --update-secrets=DATABASE_URL=DATABASE_URL:latest
      - --update-secrets=JWT_PRIVATE_KEY=JWT_PRIVATE_KEY:latest
      - --update-secrets=JWT_PUBLIC_KEY=JWT_PUBLIC_KEY:latest
      - --update-secrets=GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest
      - --update-secrets=GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest
      - --update-secrets=OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest
      - --update-secrets=LLM_CALL_ENCRYPTION_KEY=LLM_CALL_ENCRYPTION_KEY:latest
      - --update-secrets=R2_ACCOUNT_ID=R2_ACCOUNT_ID:latest
      - --update-secrets=R2_ACCESS_KEY_ID=R2_ACCESS_KEY_ID:latest
      - --update-secrets=R2_SECRET_ACCESS_KEY=R2_SECRET_ACCESS_KEY:latest
      - --update-secrets=R2_BUCKET_NAME=R2_BUCKET_NAME:latest
      - --update-secrets=SENTRY_DSN=SENTRY_DSN:latest
      - --update-secrets=SCHEDULER_SECRET=SCHEDULER_SECRET:latest
      - --update-secrets=FRONTEND_URL=FRONTEND_URL:latest
      - --update-secrets=API_BASE_URL=API_BASE_URL:latest
      - --quiet

images:
  - asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-backend:$COMMIT_SHA

options:
  logging: CLOUD_LOGGING_ONLY
```

> Note: `gcloud run deploy` (not `services update`) creates the service if absent, updates if present. This handles the rename cleanly.
> `--add-cloudsql-instances` mounts the Cloud SQL unix socket at `/cloudsql/t-replica-361407:asia-south1:parivarthan-db` inside the container — required for the DATABASE_URL format in Task 6.

- [ ] **Step 1.2 — Commit**

```bash
git add backend/cloudbuild.yaml
git commit -m "ci(backend): add backend/cloudbuild.yaml for hc-platform-backend service"
```

---

### Task 2: Add `output: 'standalone'` to `next.config.ts`

Standalone mode bundles only what `next start` needs — image drops from ~1.5 GB to ~300 MB.

**Files:**
- Modify: `frontend/next.config.ts`

- [ ] **Step 2.1 — Update `frontend/next.config.ts`**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  trailingSlash: true,
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
};

export default nextConfig;
```

- [ ] **Step 2.2 — Verify build still works locally**

```bash
cd frontend && npm run build
```

Expected: `.next/standalone/` directory created with `server.js` inside.

- [ ] **Step 2.3 — Commit**

```bash
git add frontend/next.config.ts
git commit -m "feat(frontend): enable standalone output for Docker"
```

---

### Task 3: Write `frontend/Dockerfile` and `frontend/cloudbuild.yaml`

Docker build context is **repo root** (not `./frontend`) so `scripts/build-theme.mjs` is accessible during `npm run build`.

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/.dockerignore`
- Create: `frontend/cloudbuild.yaml`

- [ ] **Step 3.1 — Create `frontend/Dockerfile`**

```dockerfile
# Build context: repo root (docker build -f frontend/Dockerfile .)
FROM node:22-alpine AS builder
WORKDIR /repo

# scripts/ must be present before npm run build (prebuild calls build-theme.mjs)
COPY scripts/ ./scripts/

COPY frontend/package.json frontend/package-lock.json ./frontend/
WORKDIR /repo/frontend
RUN npm ci

COPY frontend/ .

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

FROM node:22-alpine AS runner
ENV NODE_ENV=production
WORKDIR /app

COPY --from=builder /repo/frontend/.next/standalone ./
COPY --from=builder /repo/frontend/.next/static ./.next/static
COPY --from=builder /repo/frontend/public ./public

ENV PORT=8080
EXPOSE 8080
CMD ["node", "server.js"]
```

- [ ] **Step 3.2 — Create `frontend/.dockerignore`**

```
node_modules/
.next/
out/
.env
.env.*
*.md
tests/
playwright-report/
test-results/
dev/
.git/
```

- [ ] **Step 3.3 — Smoke-test the Docker build locally**

Requires the `NEXT_PUBLIC_API_URL` build arg. Use the existing backend URL for the test:

```bash
cd /path/to/parivarthan_platform   # repo root
docker build \
  -f frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_API_URL=https://hc-platform-296472807958.asia-south1.run.app \
  -t hc-platform-frontend:local \
  .
```

Expected: build completes, no errors. Image created.

- [ ] **Step 3.4 — Verify container starts**

```bash
docker run --rm -p 8080:8080 hc-platform-frontend:local
# In another terminal:
curl http://localhost:8080
```

Expected: HTTP 200 (sign-in page HTML).

- [ ] **Step 3.5 — Create `frontend/cloudbuild.yaml`**

`NEXT_PUBLIC_API_URL` is baked into the JS bundle at build time (Next.js inlines `NEXT_PUBLIC_*` vars). It must be passed as a `--build-arg`, not a Cloud Run runtime env var. Cloud Build's `availableSecrets` block reads it from Secret Manager.

```yaml
availableSecrets:
  secretManager:
    - versionName: projects/t-replica-361407/secrets/NEXT_PUBLIC_API_URL/versions/latest
      env: NEXT_PUBLIC_API_URL

steps:
  - name: gcr.io/cloud-builders/docker
    id: Build
    secretEnv:
      - NEXT_PUBLIC_API_URL
    args:
      - build
      - -f
      - frontend/Dockerfile
      - --build-arg
      - NEXT_PUBLIC_API_URL=$$NEXT_PUBLIC_API_URL
      - -t
      - asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-frontend:$COMMIT_SHA
      - .

  - name: gcr.io/cloud-builders/docker
    id: Push
    args:
      - push
      - asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-frontend:$COMMIT_SHA

  - name: gcr.io/google.com/cloudsdktool/cloud-sdk:slim
    id: Deploy
    entrypoint: gcloud
    args:
      - run
      - deploy
      - hc-platform-frontend
      - --platform=managed
      - --image=asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-frontend:$COMMIT_SHA
      - --region=asia-south1
      - --allow-unauthenticated
      - --quiet

images:
  - asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-frontend:$COMMIT_SHA

options:
  logging: CLOUD_LOGGING_ONLY
```

- [ ] **Step 3.6 — Commit**

```bash
git add frontend/Dockerfile frontend/.dockerignore frontend/cloudbuild.yaml
git commit -m "ci(frontend): add Dockerfile (standalone, scripts/ context) and cloudbuild.yaml"
```

- [ ] **Step 3.7 — Push all three tasks to main**

```bash
git push origin main
```

Cloud Build will fire the existing backend trigger (it still points at root `cloudbuild.yaml` at this point — that's fine; it re-deploys `hc-platform` one last time, which is harmless). After Task 5, the trigger is updated.

---

### Task 4: Create `NEXT_PUBLIC_API_URL` secret (SoJo — GCP Console / gcloud)

The frontend `cloudbuild.yaml` reads this secret at build time. Must exist before Task 5's trigger fires.

- [ ] **Step 4.1 — Create the secret**

```bash
echo -n "https://hc-platform-backend-296472807958.asia-south1.run.app" \
  | gcloud secrets create NEXT_PUBLIC_API_URL \
    --data-file=- \
    --project=t-replica-361407
```

> Use the **new** backend URL (`hc-platform-backend-*`), not the current one. The backend rename in Task 5 will make this URL live.

- [ ] **Step 4.2 — Verify**

```bash
gcloud secrets versions access latest --secret=NEXT_PUBLIC_API_URL --project=t-replica-361407
```

Expected: prints the backend URL.

---

### Task 5: Rename backend service + update Cloud Build trigger (SoJo — gcloud)

- [ ] **Step 5.1 — Update the existing Cloud Build trigger to use `backend/cloudbuild.yaml`**

GCP Console → Cloud Build → Triggers → find the existing trigger (`rmgpgab-hc-platform-*`) → Edit:
- **Build configuration**: change from Cloud Build configuration file `cloudbuild.yaml` → `backend/cloudbuild.yaml`
- **Included files filter**: add `backend/**`
- Save

- [ ] **Step 5.2 — Trigger a manual build to create `hc-platform-backend`**

```bash
gcloud builds submit \
  --no-source \
  --config=backend/cloudbuild.yaml \
  --project=t-replica-361407 \
  --substitutions=COMMIT_SHA=manual-rename
```

> This runs `backend/cloudbuild.yaml` which calls `gcloud run deploy hc-platform-backend` — creates the new service.
>
> **Wait:** Cloud SQL (`parivarthan-db`) must exist before this deploy lands, because `--add-cloudsql-instances` references it. If Cloud SQL isn't provisioned yet, remove `--add-cloudsql-instances` from `backend/cloudbuild.yaml` temporarily, deploy, then add it back after Task 6.

- [ ] **Step 5.3 — Verify new backend is live**

```bash
NEW_URL=$(gcloud run services describe hc-platform-backend \
  --region=asia-south1 --project=t-replica-361407 \
  --format="value(status.url)")
curl "$NEW_URL/health"
```

Expected: `{"status": "ok"}`

- [ ] **Step 5.4 — Delete old `hc-platform` service**

```bash
gcloud run services delete hc-platform \
  --region=asia-south1 \
  --project=t-replica-361407 \
  --quiet
```

- [ ] **Step 5.5 — Delete root `cloudbuild.yaml`**

```bash
git rm cloudbuild.yaml
git commit -m "ci: retire root cloudbuild.yaml — each service now owns its own"
git push origin main
```

---

### Task 6: Provision Cloud SQL + run migrations (SoJo — gcloud)

- [ ] **Step 6.1 — Create the Cloud SQL instance**

```bash
gcloud sql instances create parivarthan-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=asia-south1 \
  --project=t-replica-361407 \
  --deletion-protection \
  --no-backup
```

Expected: takes 3–5 minutes. Instance status becomes `RUNNABLE`.

- [ ] **Step 6.2 — Create database and user**

```bash
gcloud sql databases create parivarthan \
  --instance=parivarthan-db \
  --project=t-replica-361407

# Generate a strong password — store it, you'll need it for the URL
DB_PASS=$(openssl rand -base64 32 | tr -d /=+ | cut -c1-24)
echo "DB password: $DB_PASS"   # copy this somewhere safe

gcloud sql users create hc_app \
  --instance=parivarthan-db \
  --password="$DB_PASS" \
  --project=t-replica-361407
```

- [ ] **Step 6.3 — Update `DATABASE_URL` secret**

Cloud SQL unix socket URL format (works with `--add-cloudsql-instances` on Cloud Run):

```bash
DB_URL="postgresql+asyncpg://hc_app:${DB_PASS}@/parivarthan?host=/cloudsql/t-replica-361407:asia-south1:parivarthan-db"

echo -n "$DB_URL" | gcloud secrets versions add DATABASE_URL \
  --data-file=- \
  --project=t-replica-361407
```

- [ ] **Step 6.4 — Run migrations via Cloud SQL Auth Proxy**

Install `cloud-sql-proxy` if not already installed:
```bash
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.1/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy
```

Start the proxy in one terminal:
```bash
./cloud-sql-proxy t-replica-361407:asia-south1:parivarthan-db --port=5432
```

In another terminal, run migrations:
```bash
cd /path/to/parivarthan_platform
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
DATABASE_URL="postgresql+asyncpg://hc_app:${DB_PASS}@localhost/parivarthan" \
  alembic -c backend/alembic.ini upgrade head
```

Expected: `Running upgrade ... -> <revision>, OK` for each migration. No errors.

- [ ] **Step 6.5 — Redeploy backend to pick up new DATABASE_URL**

```bash
git commit --allow-empty -m "chore: trigger backend redeploy for Cloud SQL DATABASE_URL"
git push origin main
```

Wait for Cloud Build to complete, then verify:
```bash
NEW_URL=$(gcloud run services describe hc-platform-backend \
  --region=asia-south1 --project=t-replica-361407 \
  --format="value(status.url)")
curl -H "Authorization: Bearer <any-token>" "$NEW_URL/api/clients"
```

Expected: `401 Unauthorized` (not a 500 — confirms DB is reachable).

---

### Task 7: Create frontend trigger + deploy + wire FRONTEND_URL (SoJo — GCP Console / gcloud)

- [ ] **Step 7.1 — Create the frontend Cloud Build trigger**

GCP Console → Cloud Build → Triggers → Create trigger:
- **Name**: `frontend-deploy`
- **Event**: Push to a branch → `^main$`
- **Source**: same GitHub repo
- **Included files filter**: `frontend/**,scripts/**`
- **Build configuration**: Cloud Build configuration file → `frontend/cloudbuild.yaml`
- Save

- [ ] **Step 7.2 — Trigger first frontend deploy**

```bash
git commit --allow-empty -m "ci: trigger first frontend deploy"
git push origin main
```

Wait for Cloud Build to complete (both backend and frontend triggers will fire; backend trigger has `backend/**` filter and won't match — only frontend trigger fires).

- [ ] **Step 7.3 — Get frontend URL + verify**

```bash
FE_URL=$(gcloud run services describe hc-platform-frontend \
  --region=asia-south1 --project=t-replica-361407 \
  --format="value(status.url)")
echo "$FE_URL"
curl -L "$FE_URL"
```

Expected: HTTP 200, sign-in page HTML returned.

- [ ] **Step 7.4 — Update `FRONTEND_URL` secret to new frontend URL**

```bash
echo -n "$FE_URL" | gcloud secrets versions add FRONTEND_URL \
  --data-file=- \
  --project=t-replica-361407
```

- [ ] **Step 7.5 — Redeploy backend to pick up new FRONTEND_URL (CORS)**

```bash
git commit --allow-empty -m "chore: trigger backend redeploy for updated FRONTEND_URL"
git push origin main
```

- [ ] **Step 7.6 — End-to-end smoke test**

Open `$FE_URL` in a browser:
1. Sign-in page loads ✓
2. Click "Continue with Google" → Google OAuth page ✓
3. Sign in → redirected back to `/auth/callback` → redirected to `/dashboard` ✓
4. Dashboard loads with no network errors in DevTools console ✓

If Step 3 fails: check backend logs in GCP Console → Cloud Logging → filter `resource.labels.service_name="hc-platform-backend"` for auth errors.

---

## Part C — P9 Smoke Gate

---

### Task 1 — Resolve infrastructure prerequisites (SoJo — before any other task)

These are human actions in external consoles. They must be complete before the smoke test can run.

**Checklist** (SoJo walks this, not Claude Code):

- [x] **1.1** GCP Cloud Run service deployed to `asia-south1`. URL: `https://hc-platform-296472807958.asia-south1.run.app` — live revision `hc-platform-00007-78m` ✅ 2026-06-23
- [ ] **1.2** Supabase project provisioned (`ap-south-1`, Mumbai). Pooler connection string (port 6543) set as `DATABASE_URL` secret in Secret Manager. `alembic upgrade head` run against prod DB. **BLOCKED — next stage.**
- [ ] **1.3** `alembic upgrade head` run against production DB from local machine with prod `DATABASE_URL`. Output: `Running upgrade ... -> <revision>, OK`. **BLOCKED pending 1.2.**
- [x] **1.4** Cloudflare R2 bucket created. R2 credentials set in Secret Manager (`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ACCOUNT_ID`) and mounted on Cloud Run service. ✅ 2026-06-23
- [x] **1.5** All 15 Cloud Run secrets configured in Secret Manager and mounted as env vars on `hc-platform` service. Verified via `gcloud run services describe`. ✅ 2026-06-23
  ```bash
  gcloud run services describe hc-platform --region asia-south1 \
    --format='value(spec.template.spec.containers[0].env[].name)'
  ```
- [ ] **1.6** Production `SENTRY_DSN` created in Sentry UI and secret updated. **BLOCKED — next stage.** (Current placeholder causes silent error suppression — app does not crash since v1.1 fix, but errors are invisible.)
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
status, body = get("/health")
check("Cloud Run up (/health)", status == 200 and body.get("status") == "ok")

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
