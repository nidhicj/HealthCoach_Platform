# PHASE-07: External Scheduler

**Unit**: Unit_001_HcCoreCycle
**Status**: Complete
**Verification date**: 2026-06-16 — see `docs/VERIFICATION.md` § P7
**Implements**: `SPEC-0001-hc-core-cycle.md` — pre-condition only (no new user-facing cycle stages; enables background hygiene that supports the snippet library quality over time)
**ADRs implemented**: ADR-0001 (background jobs row — external scheduler, no APScheduler), ADR-0006 (structured logging conventions for scheduled task events)

---

## 0. Prerequisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific not provided. Ready?

P6 (frontend) must be Complete and Verified before P7 begins.

---

## 1. Scope

P7 adds the ability for a daily external job (GitHub Actions cron) to hit a backend endpoint and run periodic maintenance tasks. The only task at MVP is **snippet retirement**: any `hc_style_snippets` row that has not been used in 180+ days gets `retired_at` stamped, removing it from future LLM prompt assembly.

Cloud Run containers run standard CPython and could support APScheduler, but an external scheduler keeps background-job concerns outside the web process and is simpler to monitor. The solution is an external caller — GitHub Actions — that sends an authenticated HTTP request to the Cloud Run endpoint daily.

**Not in scope**: adding new task types beyond snippet retirement, EasyCron as an alternative (GitHub Actions is sufficient at pilot scale and keeps the config in-repo), auto-un-retirement, per-HC cron schedules.

---

## 2. Deliverables to ship

| # | Artifact | What it does |
|---|---|---|
| 1 | `backend/src/api/scheduler.py` | `POST /internal/scheduled-tasks` endpoint — auth check + snippet retirement DB sweep + structured log |
| 2 | `backend/src/config.py` (modified) | New `scheduler_secret: str` field |
| 3 | `.env.example` (modified) | `SCHEDULER_SECRET` placeholder added |
| 4 | `backend/src/main.py` (modified) | Registers the scheduler router |
| 5 | `backend/tests/unit/test_scheduler.py` | Unit tests for `_should_retire()` (pure logic) and `_check_scheduler_token()` (auth logic) |
| 6 | `.github/workflows/scheduler.yml` | GitHub Actions cron — fires daily at 01:00 UTC (06:30 IST), hits the endpoint, fails the job on non-200 |

---

## 3. Decisions pre-made in ADRs

All decisions pre-decided in ADRs listed in the header.

**Architecture decision (ADR-0001 background jobs row)**: External scheduler keeps background-job concerns outside the web process. GitHub Actions is sufficient at pilot scale and keeps the config in-repo. This decision is already locked.

**Retirement heuristic**: 180 days of non-use. `COALESCE(last_used_at, created_at)` is the reference: snippets never injected into a prompt are judged by their creation date. This was noted in the build-plan P7 section. It is the MVP heuristic and may be tuned later without an ADR.

---

## 4. Bugs fixed mid-phase

None recorded. (Fill in after build.)

---

## 5. Source docs consulted

- `docs/build-plan.md §Phase 7` — deliverables and acceptance criteria
- `docs/decisions/0001-stack-selection.md` — background jobs row + open risk #4 (cron trigger broken)
- `docs/decisions/0006-observability.md` — structured log format, `event=` naming convention
- `backend/src/db/models/coaching.py` — `HcStyleSnippet` model with `last_used_at`, `created_at`, `retired_at` fields
- `backend/src/config.py` — Settings pattern for new env vars
- `backend/src/telemetry/log.py` — `get_logger` / `BoundLogger` usage

---

## 6. Verification

- **Verification date**: 2026-06-16
- **Verification record**: `docs/VERIFICATION.md` § P7
- **Test count at end of phase**: 63 passing (delta from P6 baseline: +11 — 2 config, 9 scheduler)
- **Key checks**: AC1 ✅ AC2 ✅ AC3 ✅ (unit-tested) — AC4/AC5 deferred to P9 smoke gate (requires populated dev DB).

---

## 7. Lessons learned

(Fill in after build.)

---

## 8. Carry-over to subsequent phases

- `backend/src/api/scheduler.py` establishes the authenticated internal endpoint pattern. P8/P9 may add more tasks (e.g. a once-daily LLM cost digest) by appending to the same endpoint's task list — do not create a second scheduler endpoint.
- `scheduler_secret` in `Settings` is the P9 production secret to rotate. Note it in the smoke-gate checklist.
- The `.github/workflows/` directory and the `API_BASE_URL` / `SCHEDULER_SECRET` GitHub secrets are the two infrastructure items P9 must confirm work against the production Cloud Run service URL.

---

## Implementation plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement task-by-task. Steps use `- [ ]` syntax for tracking.

**Goal:** Add an authenticated `POST /internal/scheduled-tasks` endpoint that retires stale snippets; trigger it daily via GitHub Actions cron.

**Architecture:** One new router file (`scheduler.py`) with two extracted pure functions (`_check_scheduler_token`, `_should_retire`) so the business logic is unit-testable without a DB or HTTP layer. The DB sweep uses a single SQLAlchemy `UPDATE … WHERE … RETURNING` statement — idempotent by the `retired_at IS NULL` guard. GitHub Actions provides the external clock.

**Tech stack:** FastAPI router, SQLAlchemy 2.0 async `update()` + `func.coalesce()`, pydantic-settings, GitHub Actions `schedule:` trigger, `curl` for the HTTP call in CI.

---

### Task 1 — Config: add `scheduler_secret` setting

**Files:**
- Modify: `backend/src/config.py`
- Modify: `.env.example`
- Modify: `backend/tests/unit/test_config.py`

- [ ] **Step 1.1 — Write failing tests**

  Open `backend/tests/unit/test_config.py` and add at the bottom:

  ```python
  def test_scheduler_secret_defaults_to_empty_string():
      from src.config import Settings
      s = Settings(
          database_url="x",
          jwt_private_key="x",
          jwt_public_key="x",
          scheduler_secret="",
      )
      assert s.scheduler_secret == ""


  def test_scheduler_secret_accepts_value():
      from src.config import Settings
      s = Settings(
          database_url="x",
          jwt_private_key="x",
          jwt_public_key="x",
          scheduler_secret="super-secret",
      )
      assert s.scheduler_secret == "super-secret"
  ```

- [ ] **Step 1.2 — Run to confirm FAIL**

  ```bash
  cd backend && source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
  pytest tests/unit/test_config.py -v
  ```
  Expected: `FAILED — unexpected keyword argument 'scheduler_secret'` (field does not exist yet).

- [ ] **Step 1.3 — Add the field to Settings**

  In `backend/src/config.py`, add after the `app_version` line:

  ```python
  scheduler_secret: str = ""
  ```

- [ ] **Step 1.4 — Run to confirm PASS**

  ```bash
  pytest tests/unit/test_config.py -v
  ```
  Expected: all tests in that file pass.

- [ ] **Step 1.5 — Update `.env.example`**

  Add under the `# --- App ---` section:

  ```
  # --- Scheduler ---
  SCHEDULER_SECRET=<generate: openssl rand -hex 32>
  ```

- [ ] **Step 1.6 — Commit**

  ```bash
  git add backend/src/config.py .env.example backend/tests/unit/test_config.py
  git commit -m "feat(p7): add scheduler_secret setting"
  ```

---

### Task 2 — Retirement logic: pure functions with TDD

**Files:**
- Create: `backend/src/api/scheduler.py` (skeleton — pure functions only in this task)
- Create: `backend/tests/unit/test_scheduler.py`

- [ ] **Step 2.1 — Create the test file**

  Create `backend/tests/unit/test_scheduler.py`:

  ```python
  """Unit tests for scheduler pure-logic functions."""
  from datetime import datetime, timedelta, timezone

  import pytest

  from src.api.scheduler import _check_scheduler_token, _should_retire

  NOW = datetime.now(timezone.utc)


  # ── _should_retire ─────────────────────────────────────────────────────────


  def test_last_used_181_days_ago_should_retire():
      assert _should_retire(
          last_used_at=NOW - timedelta(days=181),
          created_at=NOW - timedelta(days=200),
          retired_at=None,
      ) is True


  def test_last_used_10_days_ago_should_not_retire():
      assert _should_retire(
          last_used_at=NOW - timedelta(days=10),
          created_at=NOW - timedelta(days=200),
          retired_at=None,
      ) is False


  def test_never_used_old_snippet_falls_back_to_created_at():
      """last_used_at is None → use created_at as reference."""
      assert _should_retire(
          last_used_at=None,
          created_at=NOW - timedelta(days=181),
          retired_at=None,
      ) is True


  def test_never_used_recent_snippet_not_retired():
      assert _should_retire(
          last_used_at=None,
          created_at=NOW - timedelta(days=10),
          retired_at=None,
      ) is False


  def test_already_retired_snippet_is_skipped():
      """Idempotency: a snippet with retired_at set is never re-processed."""
      assert _should_retire(
          last_used_at=NOW - timedelta(days=300),
          created_at=NOW - timedelta(days=300),
          retired_at=NOW - timedelta(days=1),
      ) is False


  def test_exactly_180_days_is_not_retired():
      """Boundary: 180 days exactly is NOT retired; 181+ is."""
      assert _should_retire(
          last_used_at=NOW - timedelta(days=180),
          created_at=NOW - timedelta(days=200),
          retired_at=None,
      ) is False


  # ── _check_scheduler_token ─────────────────────────────────────────────────


  def test_correct_token_does_not_raise():
      _check_scheduler_token(provided="abc123", expected="abc123")  # must not raise


  def test_wrong_token_raises():
      with pytest.raises(ValueError, match="invalid"):
          _check_scheduler_token(provided="wrong", expected="abc123")


  def test_empty_token_raises():
      with pytest.raises(ValueError, match="invalid"):
          _check_scheduler_token(provided="", expected="abc123")
  ```

- [ ] **Step 2.2 — Run to confirm FAIL**

  ```bash
  cd backend && pytest tests/unit/test_scheduler.py -v
  ```
  Expected: `ImportError: cannot import name '_check_scheduler_token' from 'src.api.scheduler'` (file doesn't exist yet).

- [ ] **Step 2.3 — Create `backend/src/api/scheduler.py` with pure functions**

  ```python
  """Scheduler endpoint — authenticated background tasks per build-plan.md §P7."""
  from datetime import datetime, timedelta, timezone

  from fastapi import APIRouter, HTTPException, Request, status
  from pydantic import BaseModel
  from sqlalchemy import and_, func, update

  from src.api.deps import DbDep
  from src.config import get_settings
  from src.db.models.coaching import HcStyleSnippet
  from src.telemetry.log import get_logger

  router = APIRouter(prefix="/internal", tags=["scheduler"])

  RETIREMENT_THRESHOLD_DAYS = 180


  # ── pure functions (unit-testable without DB or HTTP) ─────────────────────


  def _should_retire(
      last_used_at: datetime | None,
      created_at: datetime,
      retired_at: datetime | None,
      threshold_days: int = RETIREMENT_THRESHOLD_DAYS,
  ) -> bool:
      """Return True if the snippet should be retired in this sweep."""
      if retired_at is not None:
          return False  # already retired — idempotent guard
      reference = last_used_at if last_used_at is not None else created_at
      cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)
      return reference < cutoff


  def _check_scheduler_token(provided: str, expected: str) -> None:
      """Raise ValueError if the provided token does not match the expected secret."""
      if not provided or provided != expected:
          raise ValueError("invalid scheduler token")


  # ── endpoint ──────────────────────────────────────────────────────────────


  class SchedulerResult(BaseModel):
      tasks_run: list[str]
      retired_count: int


  @router.post("/scheduled-tasks", response_model=SchedulerResult)
  async def run_scheduled_tasks(request: Request, db: DbDep) -> SchedulerResult:
      try:
          _check_scheduler_token(
              provided=request.headers.get("X-Scheduler-Token", ""),
              expected=get_settings().scheduler_secret,
          )
      except ValueError:
          raise HTTPException(
              status_code=status.HTTP_401_UNAUTHORIZED,
              detail="Invalid scheduler token",
          )

      logger = get_logger(request_id=getattr(request.state, "request_id", "scheduler"))

      cutoff = datetime.now(timezone.utc) - timedelta(days=RETIREMENT_THRESHOLD_DAYS)
      now = datetime.now(timezone.utc)

      stmt = (
          update(HcStyleSnippet)
          .where(
              and_(
                  HcStyleSnippet.retired_at.is_(None),
                  func.coalesce(HcStyleSnippet.last_used_at, HcStyleSnippet.created_at)
                  < cutoff,
              )
          )
          .values(retired_at=now)
          .returning(HcStyleSnippet.id)
      )
      result = await db.execute(stmt)
      await db.commit()
      retired_count = len(result.fetchall())

      logger.info(
          "scheduled_task_run",
          task="snippet_retirement",
          retired_count=retired_count,
          threshold_days=RETIREMENT_THRESHOLD_DAYS,
      )

      return SchedulerResult(tasks_run=["snippet_retirement"], retired_count=retired_count)
  ```

- [ ] **Step 2.4 — Run to confirm PASS**

  ```bash
  cd backend && pytest tests/unit/test_scheduler.py -v
  ```
  Expected: all 9 tests pass.

- [ ] **Step 2.5 — Commit**

  ```bash
  git add backend/src/api/scheduler.py backend/tests/unit/test_scheduler.py
  git commit -m "feat(p7): scheduler endpoint + retirement logic (TDD)"
  ```

---

### Task 3 — Register router in `main.py`

**Files:**
- Modify: `backend/src/main.py`

- [ ] **Step 3.1 — Add import and router registration**

  In `backend/src/main.py`, add the import alongside the other router imports:

  ```python
  from src.api.scheduler import router as scheduler_router
  ```

  And add after the last `app.include_router(...)` call:

  ```python
  app.include_router(scheduler_router)
  ```

- [ ] **Step 3.2 — Verify the full backend test suite still passes**

  ```bash
  cd backend && pytest tests/unit/ -v
  ```
  Expected: all existing tests plus the 9 new scheduler tests pass. Zero failures.

- [ ] **Step 3.3 — Verify the app boots**

  ```bash
  cd backend && uvicorn src.main:app --port 8000 &
  sleep 2
  curl -s http://localhost:8000/healthz
  # Expected: {"status":"ok","version":"0.1.0"}
  curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/internal/scheduled-tasks
  # Expected: 401
  kill %1
  ```

- [ ] **Step 3.4 — Commit**

  ```bash
  git add backend/src/main.py
  git commit -m "feat(p7): register scheduler router"
  ```

---

### Task 4 — GitHub Actions workflow

**Files:**
- Create: `.github/workflows/scheduler.yml`

- [ ] **Step 4.1 — Create the `.github/workflows/` directory and workflow file**

  ```bash
  mkdir -p /mnt/hdd/yourProjects/OnGoing/Poshini/parivarthan_platform/.github/workflows
  ```

  Create `.github/workflows/scheduler.yml`:

  ```yaml
  name: Scheduled Tasks

  on:
    schedule:
      - cron: '0 1 * * *'   # 01:00 UTC = 06:30 IST, daily
    workflow_dispatch:        # manual trigger for local testing

  jobs:
    run-scheduled-tasks:
      runs-on: ubuntu-latest
      timeout-minutes: 5

      steps:
        - name: Trigger snippet retirement sweep
          run: |
            HTTP_STATUS=$(curl -s -o /tmp/response.json -w "%{http_code}" \
              -X POST "${{ secrets.API_BASE_URL }}/internal/scheduled-tasks" \
              -H "X-Scheduler-Token: ${{ secrets.SCHEDULER_SECRET }}" \
              -H "Content-Type: application/json")
            echo "HTTP status: $HTTP_STATUS"
            cat /tmp/response.json
            if [ "$HTTP_STATUS" != "200" ]; then
              echo "Scheduled task endpoint returned $HTTP_STATUS — failing job"
              exit 1
            fi
  ```

- [ ] **Step 4.2 — Verify the YAML is valid**

  ```bash
  python3 -c "import yaml; yaml.safe_load(open('.github/workflows/scheduler.yml'))" && echo "YAML valid"
  ```
  Expected: `YAML valid`

- [ ] **Step 4.3 — Document required GitHub secrets**

  The workflow needs two secrets set in the GitHub repo:
  - `API_BASE_URL` — the production Cloud Run service URL (e.g. `https://parivarthan-backend-xyz.asia-south1.run.app`)
  - `SCHEDULER_SECRET` — matches `SCHEDULER_SECRET` set in Cloud Run environment variables

  These are set in GitHub → repo → Settings → Secrets and variables → Actions. This is a P9 (smoke gate) task; the workflow file can be committed now and the secrets added during P9.

- [ ] **Step 4.4 — Commit**

  ```bash
  git add .github/workflows/scheduler.yml
  git commit -m "feat(p7): GitHub Actions daily scheduler cron"
  ```

---

### Task 5 — Run full test suite + acceptance criteria walkthrough

- [ ] **Step 5.1 — Full backend unit test run**

  ```bash
  cd backend && pytest tests/unit/ -v
  ```
  Expected: all tests pass. Count should be 45 (baseline) + 9 (new scheduler) = 54.
  Note: baseline was 45 per SESSION_LOG 2026-05-12. Adjust if it has changed.

- [ ] **Step 5.2 — Walk acceptance criteria from `build-plan.md §Phase 7`**

  **AC1**: External scheduler hits the endpoint and gets 200.
  ```bash
  # Start backend
  cd backend && uvicorn src.main:app --port 8000 &
  # Set a test secret in env
  export SCHEDULER_SECRET=test-local-secret
  # Hit with correct token
  curl -s -X POST http://localhost:8000/internal/scheduled-tasks \
    -H "X-Scheduler-Token: test-local-secret" | python3 -m json.tool
  # Expected: {"tasks_run":["snippet_retirement"],"retired_count":0}
  kill %1
  ```

  **AC2**: Wrong token → 401.
  ```bash
  cd backend && uvicorn src.main:app --port 8000 &
  curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/internal/scheduled-tasks \
    -H "X-Scheduler-Token: wrong"
  # Expected: 401
  curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/internal/scheduled-tasks
  # Expected: 401 (no header)
  kill %1
  ```

  **AC3**: Idempotency — running twice produces same state (covered by `test_already_retired_snippet_is_skipped` unit test for logic; the `retired_at IS NULL` guard in the SQL statement ensures DB-level idempotency).

  **AC4**: Snippet retirement — 200-day-old snippet gets `retired_at` set. Run manually against local dev DB if available:
  ```sql
  -- Insert a 200-day-old snippet
  INSERT INTO hc_style_snippets
    (hc_user_id, snippet_type, original_text, created_at, last_used_at)
  VALUES
    ((SELECT id FROM users LIMIT 1), 'edit', 'test', NOW() - INTERVAL '200 days', NOW() - INTERVAL '200 days');
  ```
  Then hit the endpoint with the correct token and verify `retired_at` is now set on that row.

  **AC5**: Recent snippet stays unretired — same test with a snippet `last_used_at = NOW() - INTERVAL '10 days'`. Verify `retired_at` remains NULL after the sweep.

- [ ] **Step 5.3 — Update VERIFICATION.md**

  Add a `## P7 — External Scheduler` section to `docs/VERIFICATION.md` and tick the ACs that passed.

- [ ] **Step 5.4 — Final commit: mark phase Complete**

  ```bash
  git add docs/VERIFICATION.md docs/specs/Unit_001_HcCoreCycle/PHASE-07-external-scheduler.md
  git commit -m "docs(p7): mark P7 Complete, verification record"
  ```
