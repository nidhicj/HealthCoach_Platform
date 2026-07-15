# ADR-0008: Platform rename — Parivarthan → Tapas

**Status**: Proposed
**Date**: 2026-07-14
**Decision driver**: SoJo
**Supersedes**: n/a
**Relates to**: ADR-0001 (stack selection), ADR-0005 (auth strategy)

---

## Context

The platform is being renamed from "Parivarthan" to "Tapas." SoJo had already started a manual
find-and-replace (visible in the working tree: `docker-compose.yml`, `.env.example`,
`.dev.vars.example`, `backend/scripts/create_hc_user.py`, `backend/scripts/mock_p6/*.sh`, several
docs) and manually migrated the local Postgres data into a new `tapas_platform_postgres_data`
Docker volume (confirmed live — `tapas_dev` has all 22 application tables plus `alembic_version`).

A full-repo audit (`grep -rli parivarthan`, `git diff`, and read-only inspection of the running
Docker containers and the live GCP project `t-replica-361407`) found 33 files still containing
"parivarthan" and surfaced two things that are **not** simply cosmetic:

1. **Local dev DB is only half-renamed.** `DATABASE_URL` → `tapas_dev` is done, but
   `TEST_DATABASE_URL` still points at `parivarthan_test` — which does still exist as a live
   database on the current `tapas_platform-postgres-1` container (it rode along in SoJo's manual
   volume migration), so nothing is currently broken, but it's inconsistent and undocumented.

2. **`.github/workflows/deploy.yml` and `docs/ops/deployment.md` don't match production
   reality, independent of this rename.** Both reference a Cloud Run service called
   `parivarthan-api` / `parivarthan-backend`. `gcloud run services list` (read-only, verified live
   against project `t-replica-361407`) shows **no such service exists**. What's actually deployed
   and serving traffic is `hc-platform` and `hc-platform-backend`, each with real revision history
   (14 revisions on the backend). These files were already stale before this rename started —
   fixing them to match reality is bundled into this ADR since it's the same audit, but it is a
   **correctness fix to `hc-platform-*`, not a rename to `tapas-*`** (see Decision below).

### Forces at play

- **Consistency**: "get rid of parivarthan everywhere" is the goal, but blind find-and-replace
  across CI/deploy config risks pointing production tooling at a service name that was never real
  in the first place.
- **Blast radius**: local dev/code/docs renames are fully reversible and low-risk. Anything that
  touches the live Cloud Run services (`hc-platform`, `hc-platform-backend`) requires Google OAuth
  Console and DNS changes outside this repo's control — SoJo has explicitly deferred that.
- **Data safety**: SoJo already migrated local Postgres data by hand; this ADR must not re-touch
  that data, only the leftover naming inconsistency (`parivarthan_test`).
- **Historical accuracy vs. consistency**: `SESSION_LOG.md` / `HANDOVER-P3..P6.md` are dated
  records. SoJo chose consistency over preserving the old name in history.

---

## Decision

Rename "parivarthan" → "tapas" across local dev config, backend source, tests, and docs. Two
specific files (`deploy.yml`, `deployment.md`) get corrected to the **real** live service name
(`hc-platform-backend`) instead, since no `tapas-backend` or `parivarthan-backend` Cloud Run
service exists to rename. The live `hc-platform` / `hc-platform-backend` Cloud Run services
themselves are **explicitly out of scope** — not renamed, per SoJo's decision, since they were
never "parivarthan"-branded to begin with.

**Explicitly out of scope for this ADR:**
- Renaming the live `hc-platform` / `hc-platform-backend` Cloud Run services (would need new
  `.run.app` URLs, Google OAuth Console redirect URI updates, and DNS/Cloudflare Pages changes —
  none of which this repo controls).
- Renaming the GitHub repo (`nidhicj/HealthCoach_Platform` — already doesn't contain "parivarthan"
  or "tapas"; not raised by SoJo, treated as a separate decision).
- Pruning the orphaned Docker volumes/containers (`parivarthan_platform_postgres_data`,
  `parivarthan_platform-postgres-1`, `tapas_unit004_postgres_data`) — kept as a safety net per
  SoJo's choice; exact prune commands are listed below for later manual use.

---

## Rationale

1. **Local dev, backend source, tests, and docs get renamed** — these are entirely within this
   repo's control, fully reversible via git, and carry no external dependency.
2. **CI/deploy config gets corrected to reality, not renamed** — inventing a `tapas-backend` Cloud
   Run target when no such service exists (and the real one is `hc-platform-backend`) would leave
   `deploy.yml` pointing at nothing, same as it does today with `parivarthan-api`. Fixing it to the
   real name is strictly better than either leaving it broken or renaming it to a third, still-wrong
   name.
3. **Live Cloud Run services stay `hc-platform*`** — per SoJo's explicit decision. They were never
   "parivarthan"-branded, so they're outside "get rid of parivarthan everywhere" by definition, and
   renaming them requires OAuth Console / DNS changes this repo can't make or verify.

---

## Consequences

### Positive
- Zero remaining "parivarthan" references anywhere in the repo (code, config, docs) once Tasks 1-5 land.
- Two pre-existing, unrelated bugs get fixed as a side effect: the wrong GitHub URL in the backend's
  User-Agent string, and `deploy.yml`/`deployment.md` pointing at a Cloud Run service that never existed.
- Local dev DB naming becomes fully consistent (`tapas_dev`, `tapas_test`).

### Negative / tradeoffs accepted
- Historical session logs and handover docs no longer reflect what the product was actually called
  at the time — accepted per SoJo's explicit choice, favoring consistency over historical accuracy.
- `Task 3` (deploy.yml/deployment.md) is held pending SoJo's confirmation of how `hc-platform-backend`
  is really deployed today, since that's unverifiable from this environment (`gh` not installed).
- The three orphaned Docker resources (`parivarthan_platform_postgres_data`,
  `parivarthan_platform-postgres-1`, `tapas_unit004_postgres_data`) are left in place, consuming
  disk, until SoJo prunes them manually.

### Things to revisit
- **Renaming `hc-platform`/`hc-platform-backend` to `tapas`/`tapas-backend`**: deferred. If SoJo
  wants this later, it needs its own ADR covering the OAuth redirect URI update, DNS/Cloudflare
  Pages repoint, and a deploy-then-verify-then-decommission-old-service sequence — not a
  find-and-replace.
- **GitHub repo rename**: not raised by SoJo; the repo is already named `HealthCoach_Platform`, not
  "parivarthan" or "tapas" — separate decision if wanted.

---

## Deferred cleanup (not part of this ADR — for SoJo to run manually when ready)

```bash
# Only after confirming tapas_dev/tapas_test are fully working end-to-end:
docker rm parivarthan_platform-postgres-1
docker volume rm parivarthan_platform_postgres_data
docker volume rm tapas_unit004_postgres_data
```

---

## References

- `docs/decisions/0001-stack-selection.md` — original local Postgres bootstrap instructions
- `docs/decisions/0005-auth-strategy.md` — JWT issuer/audience contract
- `docs/ops/deployment.md` — deployment runbook (Task 3 corrects this)
- `.github/workflows/deploy.yml` — CI deploy pipeline (Task 3 corrects this)

---

## Changelog

| Date | Change | Reason |
|------|--------|--------|
| 2026-07-14 | Initial draft, Proposed. | Full-repo audit of platform rename from Parivarthan to Tapas; scope decisions made interactively with SoJo. |
| 2026-07-15 | Fix-up: untracked `docs/specs/Unit_005_PlatformFoundations/PHASE-01-hc-settings-profile.md` (kept content, removed from this branch's git history via `git rm --cached`); removed 2 redundant `parivarthan-*` lines from `.gitignore`; corrected Task 5 Step 3's verify wording and Step 5's commit command (named files instead of a directory-level `git add`). | Final whole-branch review found the Unit_005 file had been committed onto this branch despite its own explicit "do not commit here" instruction, root-caused to this ADR's own Task 5 Step 5 using `git add docs/` instead of naming files — exactly the anti-pattern every other task's dispatch was told to avoid. SoJo decided: untrack (not delete) the Unit_005 file; keep `frontend/.claude/settings.local.json` committed as-is (separate finding, no action needed). |

---

## Implementation plan

> **For agentic workers:** execute tasks in order. Each task ends with its own verification step —
> do not proceed to the next task until the current one's verification passes.

### Task 1 — Finish the local dev DB rename

**Files:**
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `docs/decisions/0001-stack-selection.md:323-326`

- [ ] **Step 1**: In `.env.example`, change:
  ```
  TEST_DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_test
  ```
  to:
  ```
  TEST_DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/tapas_test
  ```

- [ ] **Step 2**: Rename the live database (safe, reversible, no data loss — `ALTER DATABASE RENAME`
  does not touch table contents):
  ```bash
  docker exec tapas_platform-postgres-1 psql -U postgres -c "ALTER DATABASE parivarthan_test RENAME TO tapas_test;"
  ```
  Expected: `ALTER DATABASE`. If it errors with "database is being accessed by other users," no
  test run is currently connected — retry, or `SELECT pg_terminate_backend(pid) FROM
  pg_stat_activity WHERE datname = 'parivarthan_test';` first.

- [ ] **Step 3**: Add a trailing newline to `docker-compose.yml` (currently missing — cosmetic,
  bundled since the file is already touched).

- [ ] **Step 4**: In `docs/decisions/0001-stack-selection.md`, update lines 323-326 from:
  ```
  The `parivarthan_test` database must be created manually on first start (it is not auto-created by the image):
  docker exec parivarthan_platform-postgres-1 psql -U postgres -c "CREATE DATABASE parivarthan_test;"
  ```
  to:
  ```
  The `tapas_test` database must be created manually on first start (it is not auto-created by the image):
  docker exec tapas_platform-postgres-1 psql -U postgres -c "CREATE DATABASE tapas_test;"
  ```

- [ ] **Step 5: Verify**
  ```bash
  docker exec tapas_platform-postgres-1 psql -U postgres -l | grep tapas_test
  grep -c parivarthan .env.example docker-compose.yml docs/decisions/0001-stack-selection.md
  ```
  Expected: `tapas_test` listed; all three grep counts return `0`.

- [ ] **Step 6: Commit**
  ```bash
  git add .env.example docker-compose.yml docs/decisions/0001-stack-selection.md
  git commit -m "chore(db): finish parivarthan_test -> tapas_test rename"
  ```

---

### Task 2 — Backend Python package identity, JWT claims, User-Agent string

**Files:**
- Modify: `backend/pyproject.toml:2`
- Modify: `backend/src/auth/jwt_utils.py:9-10`
- Modify: `backend/src/lib/http.py:6`
- Modify: `backend/src/main.py:33`
- Modify: `backend/tests/integration/conftest.py:1,53`
- Modify: `backend/tests/unit/test_http.py:7,13`
- Modify: `backend/tests/unit/test_jwt_utils.py:36`
- Modify: `docs/decisions/0005-auth-strategy.md:98-99`

**Interfaces:** `_ISSUER`/`_AUDIENCE` in `jwt_utils.py` are compared literally against incoming
token claims — signer and verifier must change together (they're in the same file, so this is a
single-file consistency requirement, not cross-service).

- [ ] **Step 1**: `backend/pyproject.toml:2` — change `name = "parivarthan-backend"` to
  `name = "tapas-backend"`.

- [ ] **Step 2**: `backend/src/auth/jwt_utils.py:9-10` — change:
  ```python
  _ISSUER = "https://api.parivarthan.com"
  _AUDIENCE = "parivarthan-api"
  ```
  to:
  ```python
  _ISSUER = "https://api.tapas.com"
  _AUDIENCE = "tapas-api"
  ```
  (These are opaque comparison strings, not resolved URLs — renaming carries no functional risk as
  long as issuer and audience change together, which they do here.)

- [ ] **Step 3**: `backend/src/lib/http.py:6` — change:
  ```python
  _UA = "parivarthan-backend/{version} (+https://github.com/poshini/parivarthan-platform)"
  ```
  to:
  ```python
  _UA = "tapas-backend/{version} (+https://github.com/nidhicj/HealthCoach_Platform)"
  ```
  Note: the old URL (`github.com/poshini/parivarthan-platform`) was already wrong — `git remote -v`
  shows the real origin is `github.com/nidhicj/HealthCoach_Platform`. This fixes both problems at
  once. Flag to SoJo if the repo itself should also be renamed later (separate decision, not done here).

- [ ] **Step 4**: `backend/src/main.py:33` — change `title="Parivarthan API"` to `title="Tapas API"`.

- [ ] **Step 5**: Update the three test files to match:
  - `backend/tests/integration/conftest.py:1` — docstring `"""...Uses parivarthan_test database."""`
    → `"""...Uses tapas_test database."""`
  - `backend/tests/integration/conftest.py:53` — `"postgresql://postgres:localdevpassword@localhost:5432/parivarthan_test"`
    → `"postgresql://postgres:localdevpassword@localhost:5432/tapas_test"`
  - `backend/tests/unit/test_http.py:7` — `assert ua.startswith("parivarthan-backend/")` →
    `assert ua.startswith("tapas-backend/")`
  - `backend/tests/unit/test_http.py:13` — `assert "parivarthan-backend" in client.headers["user-agent"]`
    → `assert "tapas-backend" in client.headers["user-agent"]`
  - `backend/tests/unit/test_jwt_utils.py:36` — `assert claims.iss == "https://api.parivarthan.com"`
    → `assert claims.iss == "https://api.tapas.com"`

- [ ] **Step 6**: `docs/decisions/0005-auth-strategy.md:98-99` — update the example JWT payload:
  ```
  "iss": "https://api.parivarthan.com",
  "aud": "parivarthan-api",
  ```
  to:
  ```
  "iss": "https://api.tapas.com",
  "aud": "tapas-api",
  ```

- [ ] **Step 7**: Regenerate the lockfile. **Blocker**: `uv` is not installed in this environment
  (`which uv` returned nothing) — this step must run wherever `uv` is available:
  ```bash
  cd backend && uv lock && uv sync
  ```
  Expected: `uv.lock` regenerates with `name = "tapas-backend"` at the entry currently at line 731;
  no dependency version changes, only the package identity.

- [ ] **Step 8: Run the backend test suite**
  ```bash
  cd backend && uv run pytest tests/unit/test_http.py tests/unit/test_jwt_utils.py -v
  cd backend && uv run pytest tests/integration/ -v   # requires TEST_DATABASE_URL pointed at tapas_test (Task 1)
  ```
  Expected: all pass.

- [ ] **Step 9: Verify no residual references**
  ```bash
  grep -rn parivarthan backend/pyproject.toml backend/src/ backend/tests/ docs/decisions/0005-auth-strategy.md
  ```
  Expected: no output (besides `backend/uv.lock`, which is regenerated by Step 7, not hand-edited).

- [ ] **Step 10: Commit**
  ```bash
  git add backend/pyproject.toml backend/src/auth/jwt_utils.py backend/src/lib/http.py backend/src/main.py \
    backend/tests/integration/conftest.py backend/tests/unit/test_http.py backend/tests/unit/test_jwt_utils.py \
    backend/uv.lock docs/decisions/0005-auth-strategy.md
  git commit -m "chore(backend): rename parivarthan -> tapas in package identity, JWT claims, UA string"
  ```

---

### Task 3 — Align CI/deploy docs to actual production reality (not a "tapas" rename)

**Files:**
- Modify: `.github/workflows/deploy.yml:33,44,76`
- Modify: `docs/ops/deployment.md` (lines 31, 36, 40-41, 89, 91-92, 135, 137)

**This task does not rename anything to "tapas."** It fixes both files to reference the Cloud Run
service that's actually live (`hc-platform-backend`), since `parivarthan-api`/`parivarthan-backend`
never existed as a deployed service (verified via `gcloud run services list` against project
`t-replica-361407`).

- [ ] **Step 1**: **Hold before executing** — confirm with SoJo how `hc-platform-backend` actually
  gets deployed today. `gh` isn't installed in this environment so Actions run history couldn't be
  checked; if `deploy.yml` has simply never run successfully, editing it is safe. If deploys
  currently happen by hand (`gcloud run deploy` from someone's laptop, matching the exact commands
  in `deployment.md`), editing `deploy.yml` to point at `hc-platform-backend` may cause the *next*
  push to `main` to trigger an actual redeploy of the live service — confirm that's wanted before
  merging this task.

- [ ] **Step 2**: In `.github/workflows/deploy.yml`:
  - Line 33: `IMAGE="asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/parivarthan-api:${{ github.sha }}"`
    → `IMAGE="asia-south1-docker.pkg.dev/t-replica-361407/cloud-run-source-deploy/hc-platform-backend:${{ github.sha }}"`
  - Line 44: `service: parivarthan-api` → `service: hc-platform-backend`
  - Line 76: `echo "Deployed to https://parivarthan-api-296472807958.asia-south1.run.app"` →
    `echo "Deployed to https://hc-platform-backend-q5ooygb2fq-el.a.run.app"` (real URL, confirmed
    via `gcloud run services describe hc-platform-backend`)

- [ ] **Step 3**: In `docs/ops/deployment.md`, replace all `parivarthan-backend` /
  `parivarthan-prod` references (lines 31, 36, 40-41, 89, 91-92, 135, 137) with `hc-platform-backend`
  / the real project ID `t-replica-361407`.

- [ ] **Step 4: Verify**
  ```bash
  grep -n parivarthan .github/workflows/deploy.yml docs/ops/deployment.md
  ```
  Expected: no output.

- [ ] **Step 5: Commit** (only after Step 1's confirmation)
  ```bash
  git add .github/workflows/deploy.yml docs/ops/deployment.md
  git commit -m "fix(deploy): point deploy.yml and deployment.md at the actual live hc-platform-backend service"
  ```

---

### Task 4 — Frontend cleanup

**Files:**
- Modify: `frontend/tests/e2e/auth.spec.ts:30`
- Modify: `frontend/package.json:8`
- Modify: `frontend/tsconfig.json:38-39`
- Modify: `frontend/.claude/settings.local.json:11`
- Delete: `frontend/dev/shm/parivarthan-next/` (stray local build-cache dir)

- [ ] **Step 1**: `frontend/tests/e2e/auth.spec.ts:30` — this test was already broken independent of
  this rename (the sign-in page at `frontend/src/app/(public)/sign-in/page.tsx` already renders
  `Tapas` as its `h1`). Change:
  ```ts
  const wordmark = page.getByRole("heading", { name: /parivarthan/i });
  ```
  to:
  ```ts
  const wordmark = page.getByRole("heading", { name: /tapas/i });
  ```

- [ ] **Step 2**: `frontend/package.json:8` — change
  `"dev": "NEXT_DIST_DIR=/dev/shm/parivarthan-next next dev"` to
  `"dev": "NEXT_DIST_DIR=/dev/shm/tapas-next next dev"`.

- [ ] **Step 3**: `frontend/tsconfig.json:38-39` — change both
  `/dev/shm/parivarthan-next/types/**/*.ts` and `/dev/shm/parivarthan-next/dev/types/**/*.ts` to
  the `tapas-next` equivalents.

- [ ] **Step 4**: `frontend/.claude/settings.local.json:11` — this permission entry points at
  `/mnt/hdd/yourProjects/OnGoing/Poshini/parivarthan_platform/backend/**`, a path that no longer
  exists (the repo folder is now `tapas_unit004`). Update to
  `/mnt/hdd/yourProjects/OnGoing/Poshini/tapas_unit004/backend/**`.

- [ ] **Step 5**: Delete the stray build-cache directory:
  ```bash
  rm -rf frontend/dev/shm/parivarthan-next/
  ```
  (Confirm it's gitignored first: `git check-ignore frontend/dev/shm/parivarthan-next/` — if it's
  not ignored and is tracked, stop and ask before deleting.)

- [ ] **Step 6: Run the e2e test**
  ```bash
  cd frontend && npx playwright test tests/e2e/auth.spec.ts
  ```
  Expected: pass.

- [ ] **Step 7: Verify**
  ```bash
  grep -rn parivarthan frontend/tests/ frontend/package.json frontend/tsconfig.json frontend/.claude/settings.local.json
  ```
  Expected: no output.

- [ ] **Step 8: Commit**
  ```bash
  git add frontend/tests/e2e/auth.spec.ts frontend/package.json frontend/tsconfig.json frontend/.claude/settings.local.json
  git commit -m "chore(frontend): rename parivarthan -> tapas in build cache paths, fix stale e2e assertion and permission path"
  ```

---

### Task 5 — Docs sweep

**Files (per SoJo's decision, rename throughout including historical records):**
- `docs/SESSION_LOG.md`
- `docs/HANDOVER-P3.md`, `docs/HANDOVER-P4.md`, `docs/HANDOVER-P5.md`, `docs/HANDOVER-P6.md`
- `docs/VERIFICATION.md`
- `docs/SYNC-2026-05-07.md`
- `docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md`
- `docs/specs/Unit_001_HcCoreCycle/PHASE-07-external-scheduler.md`
- `docs/specs/Unit_001_HcCoreCycle/PHASE-09-pilot-smoke-gate.md`
- `docs/specs/Unit_001_HcCoreCycle/PHASE-10-improved-ui-ux.md`
- `docs/specs/Unit_002_SupplementRecommendations/PHASE-01-supplement-recommendations.md`
- `docs/specs/Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md`
- `docs/specs/Unit_004_OneStopSpot/PHASE-01-action-items-delivery.md`
- `docs/specs/Unit_004_OneStopSpot/PHASE-01c-diet-chart-send.md`
- `docs/specs/Unit_004_OneStopSpot/PHASE-01e-calendar-integration.md`
- `docs/specs/Unit_004_OneStopSpot/PHASE-01f-calendar-polish.md`
- `docs/specs/Unit_004_OneStopSpot/PHASE-02a-client-portal-foundation.md`
- `docs/specs/Unit_004_OneStopSpot/PHASE-02b-check-ins-lifecycle.md` (already partially edited — finish it)
- `docs/specs/Unit_004_OneStopSpot/PHASE-02c-free-messaging.md` (already partially edited — finish it)
- `docs/specs/Unit_004_OneStopSpot/SPEC-0001-one-stop-spot.md` (already partially edited — finish it)
- `docs/specs/Unit_005_PlatformFoundations/PHASE-01-hc-settings-profile.md`
- `prompts/starter_prompt_05.md`

These are prose mentions of the product name, not structural identifiers — a straight case-preserving
substitution is correct and low-risk (no code semantics involved). Use:

- [ ] **Step 1**: For each file above, replace case-preserving: `Parivarthan` → `Tapas`,
  `parivarthan` → `tapas`, `PARIVARTHAN` → `TAPAS`. Example using `sed` (review the diff of every
  file afterward — don't trust the substitution blindly):
  ```bash
  for f in docs/SESSION_LOG.md docs/HANDOVER-P3.md docs/HANDOVER-P4.md docs/HANDOVER-P5.md docs/HANDOVER-P6.md \
           docs/VERIFICATION.md docs/SYNC-2026-05-07.md \
           docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md \
           docs/specs/Unit_001_HcCoreCycle/PHASE-07-external-scheduler.md \
           docs/specs/Unit_001_HcCoreCycle/PHASE-09-pilot-smoke-gate.md \
           docs/specs/Unit_001_HcCoreCycle/PHASE-10-improved-ui-ux.md \
           docs/specs/Unit_002_SupplementRecommendations/PHASE-01-supplement-recommendations.md \
           docs/specs/Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md \
           docs/specs/Unit_004_OneStopSpot/PHASE-01-action-items-delivery.md \
           docs/specs/Unit_004_OneStopSpot/PHASE-01c-diet-chart-send.md \
           docs/specs/Unit_004_OneStopSpot/PHASE-01e-calendar-integration.md \
           docs/specs/Unit_004_OneStopSpot/PHASE-01f-calendar-polish.md \
           docs/specs/Unit_004_OneStopSpot/PHASE-02a-client-portal-foundation.md \
           docs/specs/Unit_004_OneStopSpot/PHASE-02b-check-ins-lifecycle.md \
           docs/specs/Unit_004_OneStopSpot/PHASE-02c-free-messaging.md \
           docs/specs/Unit_004_OneStopSpot/SPEC-0001-one-stop-spot.md \
           docs/specs/Unit_005_PlatformFoundations/PHASE-01-hc-settings-profile.md \
           prompts/starter_prompt_05.md; do
    sed -i 's/Parivarthan/Tapas/g; s/parivarthan/tapas/g; s/PARIVARTHAN/TAPAS/g' "$f"
  done
  ```

- [ ] **Step 2**: Add a one-line changelog/note to `docs/SESSION_LOG.md` and each `HANDOVER-P*.md`
  documenting the rename itself (not per SoJo's historical-preservation option — that was declined
  — but a rename this size still deserves a changelog entry per CLAUDE.md §1 rule 15).

- [ ] **Step 3: Verify**
  ```bash
  grep -rli parivarthan docs/ prompts/
  ```
  Expected: no output, except the intentional "renamed from Parivarthan to Tapas" mentions
  inside the Step 2 changelog notes themselves (`docs/SESSION_LOG.md`,
  `docs/HANDOVER-P3..P6.md`) — those are correct, not leftover.

- [ ] **Step 4: Read every changed file's diff before committing** — `sed` substitutions can
  mis-fire inside code blocks (e.g. a doc showing the *old* `docker exec parivarthan_platform-postgres-1`
  command as a "before" example in a changelog entry would get incorrectly rewritten). Spot-check
  `git diff` per file, not just the grep count.

- [ ] **Step 5: Commit**
  ```bash
  git add docs/SESSION_LOG.md docs/HANDOVER-P3.md docs/HANDOVER-P4.md docs/HANDOVER-P5.md docs/HANDOVER-P6.md \
    docs/VERIFICATION.md docs/SYNC-2026-05-07.md \
    docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md \
    docs/specs/Unit_001_HcCoreCycle/PHASE-07-external-scheduler.md \
    docs/specs/Unit_001_HcCoreCycle/PHASE-09-pilot-smoke-gate.md \
    docs/specs/Unit_001_HcCoreCycle/PHASE-10-improved-ui-ux.md \
    docs/specs/Unit_002_SupplementRecommendations/PHASE-01-supplement-recommendations.md \
    docs/specs/Unit_003_ClientDiscoveryPipeline/SPEC-0001-client-discovery-pipeline.md \
    docs/specs/Unit_004_OneStopSpot/PHASE-01-action-items-delivery.md \
    docs/specs/Unit_004_OneStopSpot/PHASE-01c-diet-chart-send.md \
    docs/specs/Unit_004_OneStopSpot/PHASE-01e-calendar-integration.md \
    docs/specs/Unit_004_OneStopSpot/PHASE-01f-calendar-polish.md \
    docs/specs/Unit_004_OneStopSpot/PHASE-02a-client-portal-foundation.md \
    docs/specs/Unit_004_OneStopSpot/PHASE-02b-check-ins-lifecycle.md \
    docs/specs/Unit_004_OneStopSpot/PHASE-02c-free-messaging.md \
    docs/specs/Unit_004_OneStopSpot/SPEC-0001-one-stop-spot.md \
    docs/specs/Unit_005_PlatformFoundations/PHASE-01-hc-settings-profile.md \
    prompts/starter_prompt_05.md
  git commit -m "docs: rename parivarthan -> tapas throughout, including historical records (per SoJo's decision)"
  ```
  **Do not use `git add docs/ prompts/`** — a directory-level add. This exact plan text
  originally did, and it silently swept an unrelated, out-of-scope, freshly-created Unit_005
  spec (`docs/specs/Unit_005_PlatformFoundations/PHASE-01-hc-settings-profile.md`) into this
  commit despite that file's own explicit "do not commit this on this branch" instruction — a
  real incident, caught only by the final whole-branch review, not any task-level review. Stage
  every file in this task's list by exact name, matching the discipline every other task in
  this ADR already required. (Note: `PHASE-01-hc-settings-profile.md` is listed here because
  its *content* rename is genuinely part of this task; whether it should be *committed* at all
  on this branch is a separate decision — see the ADR Changelog entry below for how that
  incident was actually resolved.)

---

### Task 6 — Final repo-wide verification

- [ ] **Step 1**: Confirm zero residual matches outside `.git/` and the (regenerated, not hand-edited) lockfile:
  ```bash
  grep -rli parivarthan . 2>/dev/null | grep -v '^\./\.git/'
  ```
  Expected: no output.

- [ ] **Step 2**: Bring the stack up clean and confirm it boots against `tapas_dev`:
  ```bash
  docker compose up -d
  cd backend && uv run uvicorn src.main:app --reload &
  curl -s http://localhost:8000/docs -o /dev/null -w "%{http_code}\n"   # expect 200
  cd frontend && npm run dev &
  ```
  Expected: backend serves docs at 200, frontend dev server starts without error.

- [ ] **Step 3**: Confirm the JWT round-trip still works end-to-end with the new issuer/audience —
  sign in via Google OAuth in the running frontend, confirm a session is created (per
  `docs/decisions/0005-auth-strategy.md` flow), confirm no 401s from claim mismatches.
