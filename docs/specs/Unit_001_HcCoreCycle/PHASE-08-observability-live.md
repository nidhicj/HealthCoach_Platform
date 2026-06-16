# PHASE-08: Observability Live

**Unit**: Unit_001_HcCoreCycle
**Status**: Complete (code); live verification deferred to P9
**Verification date**: TBD — see `docs/VERIFICATION.md` § P8 (to be created after verification)
**Implements**: `build-plan.md §Phase 8` acceptance criteria
**ADRs implemented**: ADR-0006 (primary — observability strategy, structured logs, Sentry, PII redaction, 5 SQL queries, alert rules)

---

## 0. Prerequisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific not provided.

P7 (External Scheduler) must be Complete and Verified before P8 begins.

---

## 1. Scope

P8 closes the gap between observability *code being in place* and observability *actually working*. Most of the machinery was built incrementally across P0–P7 (Sentry init, PII scrubber, structured logger, X-Request-ID). What is missing:

1. **Request lifecycle log lines** — every HTTP request logs a `request.start` event (method, path, ip, ua) and a `request.end` event (status code, duration_ms). These are the "behavior" signal in ADR-0006 §2 and are what you read in the Cloudflare Workers Logs dashboard to understand what the app is doing.
2. **Sentry `request_id` tag** — the middleware that stamps `request_id` on every request must also set `sentry_sdk.set_tag("request_id", ...)` so that a Sentry error can be cross-referenced with its Cloudflare log lines using a single UUID.
3. **Sentry alert rules** — three rules specified in ADR-0006 §7; currently not documented in `docs/ops/incident-response.md` with actionable setup steps.
4. **Live verification** — confirm errors reach Sentry, PII stays out, and the 5 SQL queries in ADR-0006 §8 produce sensible results against the local dev DB.

**Not in scope**: frontend Sentry SDK (`@sentry/nextjs` — deferred to P9 production config), Logpush to S3 (deferred post-pilot), Metabase/Grafana dashboard tool (deferred post-pilot), distributed tracing (out of scope per ADR-0006 §10).

---

## 2. Deliverables to ship

| # | Artifact | What changes |
|---|---|---|
| 1 | `backend/src/main.py` (modified) | `request_id_middleware` gains request lifecycle log lines + Sentry `request_id` tag |
| 2 | `backend/tests/unit/test_request_logging.py` (new) | 3 unit tests asserting `request.start` / `request.end` log lines are emitted with the right fields |
| 3 | `docs/ops/incident-response.md` (modified) | New `## Sentry alert rules` section with actionable setup steps for the 3 rules from ADR-0006 §7 |
| 4 | `docs/VERIFICATION.md` (modified) | P8 live-verification checklist (PII test, Sentry smoke test, 5 SQL queries, alert rule walkthrough) |

---

## 3. Decisions pre-made in ADRs

All code decisions pre-decided in ADR-0006. Relevant extracts:

- **Standard log fields** (ADR-0006 §2): `ts`, `level`, `request_id`, `user_id`, `hc_id`, `role`, `event`, `ms`, `ip` (truncated), `ua` (≤200 chars), `extra`.
- **IP truncation** (ADR-0006 §3): IPv4 → zero last octet (`x.x.x.0`); IPv6 → zero to /48. `scrub()` already handles this for the `ip` key automatically.
- **Sentry tag** (ADR-0006 §4): `sentry_sdk.set_tag("request_id", request_id)` — set after the middleware generates/reads the ID.
- **Alert rules** (ADR-0006 §7): 3 rules — new error fingerprint, rate >5/hour same fingerprint, any `kind=llm_validation_failed` during pilot.
- **5 SQL queries** (ADR-0006 §8): already written; verified at P8 against local dev DB.

---

## 4. Bugs fixed mid-phase

None recorded. (Fill in after build.)

---

## 5. Source docs consulted

- `docs/decisions/0006-observability.md` — primary; §2 (log fields), §3 (PII), §4 (request_id), §7 (alerts), §8 (SQL queries)
- `docs/build-plan.md §Phase 8` — acceptance criteria
- `backend/src/main.py` — existing `request_id_middleware` to extend
- `backend/src/telemetry/log.py` — `get_logger` / `BoundLogger` pattern
- `backend/src/telemetry/scrub.py` — confirms `ip` key is already handled by scrubber

---

## 6. Verification

- **Verification date**: 2026-06-16 (code); live AC4/AC5 deferred to P9
- **Verification record**: `docs/VERIFICATION.md` § P8
- **Test count at end of phase**: 66 passing (delta: +3 request logging tests)
- **Key checks**: AC1 ✅ AC2 ✅ AC3 ✅ AC6 ✅ — AC4 (Sentry smoke) and AC5 (SQL queries vs populated DB) deferred to P9 smoke gate.

---

## 7. Lessons learned

(Fill in after build.)

---

## 8. Carry-over to subsequent phases

- `request_id_middleware` is the single place all observability signals are stitched together. P9 smoke gate walks it once to confirm the three-way correlation (Sentry ↔ Cloudflare Logs ↔ `llm_calls`) actually works in production.
- `docs/ops/incident-response.md §Sentry alert rules` is a P9 item to action: the rules are documented here; SoJo configures them in Sentry UI once a production DSN exists.
- The 5 SQL queries in ADR-0006 §8 are promoted to a real dashboard tool post-pilot. For now they live in the ADR and are run ad-hoc against prod RDS.

---

## Implementation plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement task-by-task.

**Goal:** Wire request lifecycle logging and Sentry request_id tag into the existing middleware; document alert rules; write a live-verification checklist.

**Architecture:** One change to `request_id_middleware` in `main.py` — 12 lines. The `scrub()` function already handles IP truncation via the `ip` key; no scrubber changes needed. Sentry tag set with a try/except so it's a no-op when Sentry isn't initialized (e.g. dev without a DSN).

**Tech stack:** FastAPI middleware, `time.monotonic()`, existing `get_logger` / `BoundLogger`, `sentry_sdk.set_tag`.

---

### Task 1 — Enhance `request_id_middleware` with lifecycle logging + Sentry tag

**Files:**
- Modify: `backend/src/main.py`
- Create: `backend/tests/unit/test_request_logging.py`

- [ ] **Step 1.1 — Write failing tests first**

  Create `backend/tests/unit/test_request_logging.py`:

  ```python
  """Tests for request lifecycle log lines emitted by request_id_middleware."""
  import json

  import pytest
  from httpx import ASGITransport, AsyncClient

  from src.main import app


  @pytest.mark.asyncio
  async def test_request_emits_start_log_line(capsys: pytest.CaptureFixture[str]) -> None:
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          await client.get("/healthz")
      lines = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines() if l]
      events = [l["event"] for l in lines]
      assert "request.start" in events


  @pytest.mark.asyncio
  async def test_request_emits_end_log_line(capsys: pytest.CaptureFixture[str]) -> None:
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          await client.get("/healthz")
      lines = [json.loads(l) for l in capsys.readouterr().out.strip().splitlines() if l]
      end = next((l for l in lines if l["event"] == "request.end"), None)
      assert end is not None
      assert "status" in end["extra"]
      assert "ms" in end["extra"]
      assert end["extra"]["status"] == 200


  @pytest.mark.asyncio
  async def test_request_id_echoed_in_response_header(capsys: pytest.CaptureFixture[str]) -> None:
      async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
          resp = await client.get("/healthz", headers={"X-Request-ID": "test-req-123"})
      assert resp.headers["x-request-id"] == "test-req-123"
  ```

- [ ] **Step 1.2 — Run to confirm FAIL**

  ```bash
  cd backend && pytest tests/unit/test_request_logging.py -v
  ```
  Expected: `FAILED — assert 'request.start' in []` (middleware not logging yet).

- [ ] **Step 1.3 — Implement: enhance `request_id_middleware` in `main.py`**

  Replace the existing middleware function with this (add `import time` at the top of the file alongside existing imports, and add `from src.telemetry.scrub import scrub` — check if already imported):

  ```python
  import time
  ```

  Replace the `request_id_middleware` function:

  ```python
  @app.middleware("http")
  async def request_id_middleware(request: Request, call_next: Any) -> Response:
      request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
      request.state.request_id = request_id

      try:
          import sentry_sdk
          sentry_sdk.set_tag("request_id", request_id)
      except Exception:
          pass

      logger = get_logger(request_id=request_id)
      ip = request.client.host if request.client else ""
      ua = (request.headers.get("user-agent", "") or "")[:200]

      logger.info("request.start", method=request.method, path=request.url.path, ip=ip, ua=ua)

      started = time.monotonic()
      response: Response = await call_next(request)
      ms = round((time.monotonic() - started) * 1000)

      logger.info("request.end", method=request.method, path=request.url.path, status=response.status_code, ms=ms)

      response.headers["X-Request-ID"] = request_id
      return response
  ```

  Note: `ip` is passed as a key named `ip` — `scrub()` already truncates it via the `ip` key handler in `scrub.py`. No manual scrubbing needed here.

- [ ] **Step 1.4 — Run to confirm PASS**

  ```bash
  cd backend && pytest tests/unit/test_request_logging.py -v
  ```
  Expected: all 3 tests pass.

- [ ] **Step 1.5 — Full unit suite green**

  ```bash
  cd backend && pytest tests/unit/ -q
  ```
  Expected: 66 passed (63 baseline + 3 new).

- [ ] **Step 1.6 — Commit**

  ```bash
  git add backend/src/main.py backend/tests/unit/test_request_logging.py
  git commit -m "feat(p8): request lifecycle logging + Sentry request_id tag"
  ```

---

### Task 2 — Document Sentry alert rules in `incident-response.md`

**Files:**
- Modify: `docs/ops/incident-response.md`

- [ ] **Step 2.1 — Add `## Sentry alert rules` section**

  Find the section after `## Detection sources` and add:

  ```markdown
  ## Sentry alert rules

  Three rules per ADR-0006 §7. Configure in: Sentry → project → Alerts → Create Alert Rule.

  ### Rule 1 — New error fingerprint
  - **Trigger**: first occurrence of any new issue fingerprint in `production` environment
  - **Action**: email SoJo immediately
  - **Sentry UI path**: Alert type = Issue; When = "A new issue is created"; Filter = environment:production

  ### Rule 2 — Error rate spike
  - **Trigger**: same issue fingerprint fires >5 times in 1 hour
  - **Action**: email SoJo (escalation)
  - **Sentry UI path**: Alert type = Issue; When = "The issue is seen more than 5 times in 1h"

  ### Rule 3 — LLM validation failure (pilot-critical)
  - **Trigger**: any event tagged `kind=llm_validation_failed` during pilot
  - **Action**: email SoJo; log for same-day review
  - **Sentry UI path**: Alert type = Metric; Event type = Errors; Filter = `kind:llm_validation_failed`; Threshold = count > 0 in 24h
  - **Why**: free-model chain is brittle per ADR-0001 risk #8; every validation failure during pilot must be reviewed to catch prompt regressions early.

  **Verification**: after configuring, trigger Rule 1 deliberately (force an exception in a deployed Worker with production DSN) and confirm email arrives within 5 minutes.
  ```

- [ ] **Step 2.2 — Commit**

  ```bash
  git add docs/ops/incident-response.md
  git commit -m "docs(p8): add Sentry alert rules setup to incident-response.md"
  ```

---

### Task 3 — Live verification (SoJo runs this — requires Sentry DSN + running backend)

These are not code steps; they are verification steps you walk through. Record results in `docs/VERIFICATION.md` § P8.

**AC1 — Structured log lines appear with all standard fields**

```bash
cd backend
# Start backend locally with any valid .env
uvicorn src.main:app --port 8000 2>/dev/null &
# Make a request and capture its log output
curl -s http://localhost:8000/healthz
kill %1
```
Expected in stdout: two JSON lines — one with `"event":"request.start"` (has `method`, `path`, `ip`, `ua`) and one with `"event":"request.end"` (has `method`, `path`, `status`, `ms`).

**AC2 — Snippet content does NOT appear in any log line (grep test)**

```bash
# Run a few requests, capture stdout to a file, then grep
cd backend
uvicorn src.main:app --port 8000 > /tmp/logs.json 2>/dev/null &
sleep 1
curl -s http://localhost:8000/healthz
kill %1
grep -i "snippet\|original_text\|hc_modified_text" /tmp/logs.json && echo "LEAK" || echo "CLEAN"
```
Expected: `CLEAN`.

**AC3 — PII does not appear in log lines**

Same log capture, then:
```bash
grep -iE "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" /tmp/logs.json && echo "EMAIL LEAK" || echo "CLEAN"
```
Expected: `CLEAN`.

**AC4 — Force deliberate exception → appears in Sentry, no PII**

Requires `SENTRY_DSN` set in `.env`. Add a temporary route to `main.py`:
```python
@app.get("/test-error")
async def test_error():
    raise ValueError("deliberate test exception for P8 verification")
```
Hit it: `curl http://localhost:8000/test-error`. Check Sentry dashboard within 30s. Verify:
- Error fingerprint appears
- No email/phone/name in breadcrumbs
- `request_id` tag is present on the event

Remove the test route after verification. Do not commit it.

**AC5 — Run all 5 SQL queries from ADR-0006 §8**

Connect to local dev DB and run each query. Expected: queries execute without error. At pilot pre-launch, results may be empty rows — that is acceptable (empty ≠ broken). Verify syntax is correct and no `column does not exist` errors.

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev
```
Then paste each query from `docs/decisions/0006-observability.md §8`.

**AC6 — Cross-reference table from ADR-0006 walked**

Open `docs/decisions/0006-observability.md §7` (alert rules) and tick: every alert rule has a detection source in `incident-response.md`, and every source in `incident-response.md §Detection sources` maps to a rule in ADR-0006 §7. No orphaned signals or rules.

---

### Task 4 — Update docs and mark phase Complete

- [ ] **Step 4.1 — Add P8 section to `docs/VERIFICATION.md`**

  Add above the P7 section:

  ```markdown
  ## P8 — Observability Live

  **Status**: [fill in after verification]

  | AC | Check | Result |
  |---|---|---|
  | AC1 | `request.start` + `request.end` log lines emitted with method/path/ip/ua/status/ms | |
  | AC2 | No snippet/original_text/hc_modified_text in log output (grep test) | |
  | AC3 | No email pattern in log output (grep test) | |
  | AC4 | Deliberate exception → appears in Sentry ≤30s, no PII in breadcrumbs, request_id tag present | |
  | AC5 | All 5 ADR-0006 §8 SQL queries execute without error against local dev DB | |
  | AC6 | ADR-0006 §7 alert rules cross-referenced against incident-response.md — no orphans | |

  Unit test delta: 63 → 66 (+3 request logging tests)
  ```

- [ ] **Step 4.2 — Update PHASE-08 status to Complete**
- [ ] **Step 4.3 — Update SESSION_LOG.md**
- [ ] **Step 4.4 — Commit**

  ```bash
  git add docs/VERIFICATION.md docs/specs/Unit_001_HcCoreCycle/PHASE-08-observability-live.md docs/SESSION_LOG.md
  git commit -m "docs(p8): mark P8 Complete, verification record"
  ```
