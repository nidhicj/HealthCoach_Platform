# Session log

Append-only. Latest at top. Claude writes a new entry at the end of each substantial session.

---

## 2026-06-30 — Phase 10 fixes + Phase 11: Client Profile and Health Metrics

**Branch**: `feature/unit-001-phase-11-client-profile-and-health-metrics` (ready to merge to `main`)

**Phase 10 fixes landed in this session:**
- `bg-section-fill-01` applied to Sessions + Open Items cards (replaced incorrect white)
- Dashboard grid: `grid-cols-3` → `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3` (responsive)
- Journey stage: editable `<select>` on client detail page + backend `PATCH /api/clients/{id}` for `journey_stage`
- Session Notes (tab): Save/Edit freeze pattern writing to `notes_internal`
- Session Review tab (was "MOM editor"): single textarea, AI generation, Save/Edit freeze, "Send to client" button removed, `draftMom` now reads from `notes_internal` not `session_notes`
- Three-colour card system: introduced `section_fill_03` token (`#DFE3E6`) for Goal + Diet chart cards; `section_fill_01` for Sessions/Open Items, `section_fill_02` for Supplements/Details

**Phase 11 built:**
- **Gear icon → demographics Sheet**: 8 optional demographic fields (DOB, gender, city, occupation, medical conditions, allergies, medications, emergency contact) in a slide-over. Only non-empty fields render in Details card.
- **Health Metrics card**: HC defines custom metrics (name/value/unit), max 3 flagged for roster display. Save/Edit freeze pattern. Sits at 70% alongside Goal card (30%).
- **Roster card**: up to 3 `display_on_card` metrics shown below stage badge on each client tile.
- **Backend**: `demographics TEXT` (encrypted) + `health_metrics JSONB NOT NULL DEFAULT '[]'` columns on `clients`; Alembic migration; `PatchClientInput` + `ClientOut` + `ClientCreate` updated; max-3 validator.
- **ADR-0007**: app-layer Fernet encryption for `demographics` column (DPDP / CLAUDE.md §9.5).

**Security:** `demographics` PII (medical conditions, allergies, medications) encrypted at rest via SQLAlchemy `EncryptedJSON` TypeDecorator (Fernet AES-128-CBC + HMAC). Column is `TEXT` at DB layer; Python/Pydantic layer sees `dict[str, str] | None` transparently. Key: `DEMOGRAPHICS_ENCRYPTION_KEY` env var.

**Commits on branch (9 total):**
- `2bf190e` spec, `90197e7` backend, `0c0ce3f` frontend API, `2b701f7` client detail page, `04a39ce` roster metrics, `61bf782` review fixes, `808cbbb` ADR-0007, `cb68a65` encryption, `e01f318` decrypt logging + Cancel state

**Open items / follow-ups:**
- Reseed mock data for P11 (mock scripts at `backend/scripts/mock_p6/` still target local Postgres `parivarthan_dev` — data is intact)
- `health_metrics` encryption deferred (ADR-0007 §Consequences — client-side filter would break if encrypted)
- KMS migration when platform crosses regulatory audit or 10k data principals
- `h` column (Alembic revision ID `a1b2c3d4e5f6` is hand-typed not auto-generated — minor hygiene, non-breaking)

---

## 2026-06-24/25 — P9 Part B: Cross-browser auth fix + production verification + mock data migration

**Done**:

- **Root cause: sign-in loop in Firefox and Safari** — `run.app` is in the Public Suffix List. Frontend (`hc-platform-frontend-*.run.app`) and backend (`hc-platform-backend-*.run.app`) are cross-site, not same-site. Firefox Total Cookie Protection (dFPI) and Safari ITP block third-party cookies. ADR-0005 §5 assumed same-eTLD+1 — assumption was silently violated when deployment moved from Cloudflare Pages+Workers to GCP Cloud Run.

- **Fix: BFF proxy** — `frontend/src/app/api/[...path]/route.ts` — Next.js 16 catch-all Route Handler proxies all `/api/*` browser requests server-to-server to the FastAPI backend. For OAuth callback (`302 + Set-Cookie`): intercepts the redirect, re-emits `Set-Cookie` on the frontend domain. All browser requests are now same-origin. Cookie is first-party in all browsers.

- **Supporting config changes**:
  - `frontend/src/lib/config.ts`: `API_URL = ""` — all browser fetches are relative (no cross-origin calls)
  - Secret Manager `API_BASE_URL` → frontend URL — backend now sends Google's `redirect_uri` to the frontend BFF, not directly to itself
  - Google OAuth Console: frontend URL added as authorized redirect URI
  - Backend redeployed to pick up new `API_BASE_URL`

- **Second bug: `new URL()` silent failure** — When `API_URL = ""`, `new URL("/api/sessions")` throws `TypeError: Invalid URL` (requires absolute URL). All four list-with-filters functions were silently failing: `listSessions`, `listClients`, `listActionItems`, `listClientCheckIns`. Error was swallowed by error boundaries → empty data. Fixed in all four files by replacing `new URL()` with `URLSearchParams` + string concat. Bug only visible in browser Console tab, not Cloud Run logs.

- **Mock data migration** — Local dev Postgres (Docker) had 3 clients, 17 sessions, 17 MOMs, 17 briefs, 28 action items, 10 diet charts, 16 HC style snippets, 4 content assignments, 1 client file. Supabase was schema-only. Migrated via `pg_dump --data-only --inserts`, UUID substitution (local HC `26e57b28` → Supabase HC `38ff56d2`), `SET session_replication_role = replica` for FK bypass, `psql` restore. All 150 rows landed cleanly.

- **Documentation updated**: `docs/decisions/0005-auth-strategy.md` (Amendment 2026-06-24 section), `docs/diagrams/0001-system-architecture.md` (BFF proxy layer, new request flow examples), `PHASE-09` §4 bugs + §7 lessons (v1.5 and v1.6).

**Current production state**:
- Frontend: `hc-platform-frontend-00006-h65` — BFF proxy live, all list endpoints fixed
- Backend: `hc-platform-backend-00007-sdb` — using frontend URL for `redirect_uri`
- Auth: working in Chrome; Firefox and Safari unverified in browser (logs confirm sign-in and dashboard load)
- Data: mock HC data (3 clients, 17 sessions, diet charts, etc.) live in Supabase
- Pending push: `fix(frontend): replace new URL() with URLSearchParams` — committed locally, not yet pushed (HTTPS remote requires credentials)

**Open items**:
- Verify sign-in in Firefox and Safari explicitly (browser test, not just logs)
- Push the `new URL` fix commit to trigger Cloud Build frontend redeploy
- `PKCE state store` (`_state_store: dict` in `router.py`) is in-memory — multi-instance unsafe on Cloud Run scale-to-zero. Low risk at pilot scale.
- `SameSite=None` → `SameSite=Lax` cleanup in backend cookie (all requests are now same-site via proxy; `Lax` is more secure — safe to change once Firefox/Safari confirmed)
- CSRF double-submit cookie (ADR-0005 §6) — still not implemented

**Next**: Feature building — begin P10 or new unit. Product focus: trust and robustness.

---

## 2026-06-23 — P9 Part A: Cloud Run deployment, CI/CD, secrets, infra debugging

**Done**:

- **Cloud Run deployment** — Service `hc-platform` live at `https://hc-platform-296472807958.asia-south1.run.app`, region `asia-south1`, project `t-replica-361407`. Ingress: all users. App handles its own auth (no Cloud Run IAM gate).

- **CI/CD via Cloud Build** — Auto-created trigger (from GCP "Connect to repo") originally used buildpacks which cannot build Python/uv projects. Fixed by adding `cloudbuild.yaml` at repo root with three steps: `docker build ./backend`, push to Artifact Registry, `gcloud run services update hc-platform` with all 15 `--update-secrets` flags. Trigger updated to use this file. Push to `main` now auto-deploys. GitHub Actions is NOT in use — `.github/workflows/deploy.yml` deploys to deleted service `parivarthan-api` and is dead code.

- **`/healthz` → `/health` rename** — Discovered `/healthz` is intercepted by GFE (Google Frontend) layer at the infrastructure level (Kubernetes reserved path) and never reaches the container. Renamed route to `/health` in `backend/src/main.py`. Confirmed: `/` and `/health` reach FastAPI; `/healthz` returns Google HTML 404 from GFE.

- **All 15 secrets mounted** — Secrets created in Secret Manager earlier; were not mounted on the service. Fixed via `gcloud run services update --update-secrets=...`. Also added all `--update-secrets` flags to `cloudbuild.yaml` deploy step so future CI deploys keep them.

- **Sentry startup crash fixed** — With real secrets mounted, `SENTRY_DSN` placeholder value (`XXXXXXX`) passed the `if not dsn: return` guard but failed Sentry SDK's `Dsn` parser (`BadDsn: Invalid project in DSN`), crashing the container lifespan. Fixed by wrapping `sentry_sdk.init()` in `try/except Exception: pass` in `backend/src/telemetry/sentry.py`. App now starts regardless of DSN value. **Sentry is still not reporting errors** — DSN needs a real value (see open items).

- **Technical rundown created** — `docs/technical-rundown.html` — dark-themed reference doc covering full tech stack, all API routes, auth flows, 6 HC usage scenarios, known infra traps, open items.

- **PHASE-09 updated to v1.1** — Part A as-built record documented, GitHub Actions approach superseded, bugs-fixed table filled in, lessons learned written, Task 1 checklist updated with done/blocked status.

**Infra traps discovered** (logged in PHASE-09 §7 and `docs/technical-rundown.html`):
- `/healthz` is GFE-reserved; `/health` is the correct path
- Cloud Build trigger region is always "global" (not a problem — outputs still go to asia-south1)
- `gcloud run services logs read` crashes the CLI (bug); workaround: `gcloud logging read`
- Buildpacks cannot build Python/uv projects — always need `cloudbuild.yaml` with Docker

**Current live state**:
- Revision: `hc-platform-00007-78m` (healthy, 100% traffic)
- Secrets: all 15 mounted
- CI/CD: working

**Open items before Part B (smoke gate) can run**:
1. **DB** — `DATABASE_URL` secret must point to a real Supabase instance; `alembic upgrade head` must be run
2. **Sentry** — need a real project DSN; update `SENTRY_DSN` secret
3. **`FRONTEND_URL`** — update once frontend is hosted
4. **`SENTRY_DSN`** — currently silently swallowed; errors invisible in prod

**Next**: DB provisioning (Supabase ap-south-1), then frontend hosting, then return to P9 Part B smoke gate.

---

## 2026-06-16 — P7 + P8: External Scheduler + Observability Live

**Done**:

- **P7 — External Scheduler** (4 commits): `POST /internal/scheduled-tasks` endpoint authenticated by `X-Scheduler-Token`; snippet retirement sweep using `COALESCE(last_used_at, created_at) < now() - 180 days`; idempotent (`retired_at IS NULL` guard); structured log `event=scheduled_task_run`; GitHub Actions cron (01:00 UTC daily, `workflow_dispatch` for manual trigger); `scheduler_secret` setting added to `Settings` + `.env.example`. 9 unit tests (TDD). AC4/AC5 (DB-level retirement) deferred to P9.

- **P8 — Observability Live** (2 commits): `request_id_middleware` enhanced to emit `request.start` (method, path, ip, ua) and `request.end` (status, ms) JSON log lines on every HTTP request; `sentry_sdk.set_tag("request_id", ...)` wired so Sentry errors correlate with Cloudflare log lines via UUID; 3 unit tests added (capsys stdout capture). Sentry alert rules documented in `docs/ops/incident-response.md`. AC4 (Sentry smoke test) and AC5 (5 SQL queries vs populated DB) deferred to P9 where production DSN and pilot data will be available.

- **Housekeeping**: `pyproject.toml` gained `pythonpath = ["."]` so `pytest tests/unit/` works without `PYTHONPATH` prefix.

**Test count**: 52 (P6 baseline) → 66 (P8 end): +2 config, +9 scheduler, +3 request logging.

**Next**: P9 — Pre-Pilot Smoke Gate. Covers: production Worker against real RDS Mumbai + OpenRouter + S3, Cloudflare platform config (rate limiting, WAF), Sentry smoke test (AC4), SQL queries vs pilot data (AC5), DPDP deletion test, pilot HC onboarding.

---

## 2026-05-12 — P6C: Diet Chart Feature (full implementation)

**Done**:

- **P6C spec written** (commit `02ab7d0`): PHASE-06-frontend.md Part C filled in — design decisions, data model (JSONB `parameters`, `content_assignments` link), 6 backend endpoints, LLM generation + fallback spec, 3 frontend surfaces, MOM integration, acceptance criteria, implementation plan (C.10).
- **Task 1** (commit `3de979a`): `backend/src/api/diet_charts.py` — 6 endpoints (template upload/list/delete + client chart get/generate/patch); `_parse_csv_bytes` CSV parser; 7 unit tests — TDD (red→green verified). Router registered in `main.py`.
- **Task 2** (commit `4902f11`): `backend/prompts/diet_chart_generate_v1.md` prompt; `backend/src/llm_service/schemas/diet_chart.py` (`DietChartGridSchema`); `backend/src/llm_service/diet_chart_generate.py` — full LLM generation following `generate_mom_draft` pattern, with structured fallback (warn log + Sentry + `generation_status: "fallback"`); 6 unit tests. MOM integration: `__init__.py` now appends "A diet chart has been prepared for this client." to `user_message` when an active chart exists.
- **Task 3** (commit `968b55e`): `frontend/src/lib/api/dietCharts.ts` API client (6 functions, Zod v4 schemas); `/settings/diet-chart-templates` page (upload + library list); `/clients/[clientId]/diet-chart` full editor (7-day grid, inline cell editing, add meal slot column, generate/regenerate, fallback amber banner, save); client detail page updated with diet chart 2-day preview section + "Edit chart →" / "Generate →" link.

**Test count**: backend 45 unit tests + 43 frontend Vitest tests, all green.

**Bug fixed in plan**: BOM test used `"\xef\xbb\xbf".encode()` (Python string escape → multi-byte UTF-8), not actual BOM bytes. Fixed to `b'\xef\xbb\xbf' + content.encode("utf-8")`.

**Zod v4 note**: `z.record(z.unknown())` no longer valid — must be `z.record(z.string(), z.unknown())`.

**Next**: integration-test the full flow end-to-end (upload template → generate chart → edit → save → verify MOM draft picks up the note). C.9 acceptance criteria checklist.

---

## 2026-05-12 — P6B: Dashboard restructure + Action Items Kanban

**Done**:

- **CLAUDE.md §6**: Added binding override table — superpowers skill output paths now redirect into `PHASE-NN-*.md` files instead of `docs/superpowers/`. Prevents silent folder creation in all future sessions.
- **`docs/superpowers/` deleted**: Historical `plans/2026-04-30-scaffold-data-auth.md` confirmed fully executed (P0+P1+P2); content absorbed into PHASE-00/01/02 docs. Brainstorm spec deleted. `.superpowers/` and `graphify-out/` added to `.gitignore`.
- **PHASE-06-frontend.md restructured**: Existing P6A content wrapped as Part A; Part B design spec + implementation plan added; Part C diet chart stub added with 6 open questions for future brainstorm.
- **P6B Task 1** (commit `0f454c2`): Dashboard — removed "Recent Clients" section, enriched pending action item rows to two-line format (`{client} · {date}` / `{description}`).
- **P6B Task 2** (commit `e118319`): Extracted `frontend/src/lib/actionItemsKanban.ts` (`groupByClient`, `MOVE_FORWARD`, `MOVE_BACK`); 11 unit tests in `frontend/tests/unit/actionItemsKanban.test.ts` — TDD (red→green verified).
- **P6B Task 3** (commit `57e5484`): Replaced action items page with client×status kanban table (Open / In Progress / Done). Missed items in Open column with red treatment. Bidirectional click-to-move with optimistic update + revert on error.

**Test count**: 43 tests, all green.

**Decided**:
- Part B scope: frontend-only, no new npm deps, no backend changes
- Missed items stay in Open column (red card) — not a separate 4th column
- P6B marked Complete. P6C (diet chart) deferred to a future brainstorm session.

**Side quest — observability gap identified**:
ADR-0006 covers unhandled exceptions (Sentry), LLM validation failures (`llm_calls` + Sentry alert), and request errors (structured logs) well. Gap: no explicit convention for **application-level graceful degradations** — cases where the API returns 200 but a feature silently fell back to lesser behaviour (e.g. diet chart LLM returns malformed JSON → template returned unchanged). These pass through Sentry and logs invisibly under current rules. The diet chart fallback pattern (`warn` log with namespaced event, `sentry_sdk.capture_message()` with tag, response-level `generation_status` flag) is the right model and should be formalised as a platform-wide convention. **Action needed**: add a "graceful degradation" paragraph to ADR-0006 or a `docs/standards/graceful-degradation.md` — deferred, not blocking P6C.

---

## 2026-05-07 — Repo sync sweep + HANDOVER-P6 update + P6 UI review fixes

**Done**:

- **Full repo sweep** (`docs/SYNC-2026-05-07.md` created): read all ADRs (0001–0006), all phase plans (PHASE-00 through PHASE-06), SPEC-0001, all domain docs, HANDOVER-P6, SESSION_LOG, build-plan, REPO-INDEX, diagrams, and `frontend_feedback.md` in a single pass. Nine discrepancies between docs and implementation found and documented. All are doc-only fixes; none block P7.

- **HANDOVER-P6.md updated**: added `§Post-P6 developments` section covering: two post-HANDOVER-P6 commits, `frontend_feedback.md` review findings, 8 uncommitted P6-fix files, and SYNC sweep results with all 9 discrepancies. Git state block updated from `45852c5` to `af62526`.

- **P6 UI review** (`frontend_feedback.md` — committed `af62526`): 5 items triaged. Items 1, 3, 4 coded and uncommitted. Items 2 and 5 deferred as `P6B-spec`.
  - Item 1 (`P6-fix`): Dashboard section background cards for visual separation
  - Item 3 (`P6-fix`): Client name + Session # in Today's sessions list
  - Item 4 (`P6-fix`): Open action items section above sessions on client detail page; checkbox accountability
  - Item 2 (`P6B-spec`): "Recent Clients" widget — keep or replace? Needs brainstorm
  - Item 5 (`P6B-spec`): Diet chart feature — full spec needed before any code

- **Mock script fix** (commit `617b18d`): corrected table name `session_briefs` → `briefs` in `backend/scripts/mock_p6/05_verify_flywheel.sh`.

**Decided**:
- `frontend_feedback.md` items 2 and 5 require product brainstorm in Claude AI before implementation — not P6-fix, not P7 without a spec
- Diet chart may warrant its own unit (`Unit_002_DietCharts`) — defer naming until spec is written; DB tables already exist from P1
- SYNC document is the artifact for Claude AI sync context; HANDOVER-P6 + SYNC-2026-05-07 are the two docs to share for any P7 design conversation

**Bugs found / fixed**:
- Mock flywheel script was querying non-existent `session_briefs` table; fixed to `briefs`

**Known issues / carry-overs into P7**:
- 8 frontend files uncommitted — commit before P7 starts; run `cd frontend && npx vitest run` first
- `docs/SYNC-2026-05-07.md` uncommitted — commit with frontend files
- PHASE-06-frontend.md §4/§6/§7/§8 still unfilled (D8 from SYNC doc) — complete before PHASE-07 is written
- 9 doc discrepancies documented in SYNC doc — doc fixes, do not block P7
- All P7 carry-overs from HANDOVER-P6 §Known issues still apply (M000 UX gap, LLM timeout, Sentry stub, etc.)
- `PROJECT-CUSTOM-INSTRUCTIONS.md` at repo root was missing — recreated by SoJo

**Test count**: 189 backend / 40 e2e / ~12 unit (unchanged)

---

## 2026-05-06 — P6: Frontend E2E Fixes + P6 Verification Guide + AI Mock Test Scripts

**Done**:

- **P6 frontend e2e test suite: 40/40 passing** (was 34/40 at session start). Six failures fixed:
  - Test 6 (auth error text): assertion regex changed from `/authentication failed/i` to `/sign-in failed/i` to match actual page text "Sign-in failed. Redirecting to sign-in…"
  - Test 14 (brand rules font check): `assertHeadingFont` narrowed from `h1, h2, h3` to `h1` only — eyebrow-style `h2` elements on session page intentionally use `font-sans` (Manrope) per brand guide; Fraunces requirement only applies to `h1`
  - Test 26 (MOM draft strict mode): `getByText(/session summary/i).first()` — same text appeared in both AI draft `<p>` and editable `<textarea>` populated from the same draft; `.first()` disambiguates
  - Tests 36, 38, 39 (horizontal overflow at 375px): `TabsList` with `inline-flex w-fit whitespace-nowrap` and three long labels exceeded 327px available width; fixed by wrapping in `<div className="overflow-x-auto">` which scopes overflow without affecting larger viewports

- **VERIFICATION.md — P6 Frontend walkthrough** (Steps 1–14): automated suite, TypeScript build, Playwright visual inspection, live walkthrough with backend, mobile check, brand spot-check. Google OAuth redirect_uri_mismatch diagnosed — backend sends `http://localhost:8000/api/auth/google/callback` as redirect URI; this URI must be added to Google Cloud Console Authorized Redirect URIs before step 7 can pass.

- **Mock test scripts for AI context tracking** (`backend/scripts/mock_p6/`):
  - `lib.sh` — shared HTTP/date/session-lifecycle utilities sourced by all scripts
  - `01_foundation.sh` — HC user + 3 clients (Maya/Ravi/Sunita), writes IDs + JWT to `/tmp/mock_p6_ids.env`
  - `02_maya.sh` — Maya Patel: M000 onboarding (template brief) + M001 first real session (2 LLM calls)
  - `03_ravi.sh` — Ravi Kumar: 5 sessions, weight loss narrative 88kg→85.2kg (10 LLM calls)
  - `04_sunita.sh` — Sunita Rao: 8 sessions, PCOD management, cycle 50d+→27d, insulin resistance found at S7 (16 LLM calls)
  - `05_verify_flywheel.sh` — pure DB inspection: style snippet count, snippet injection in latest MOM drafts, brief token progression across sessions
  - Total: 28 LLM calls, verifies context farm + style flywheel end-to-end

- **Session-by-session architecture principle** (critical design decision): Each brief is generated at the moment the session starts — after all previous sessions' items are in DB, but before the current session's notes or items are added. This is the only correct way to simulate real context accumulation and observe whether the AI's context awareness grows across sessions. Token progression in `llm_calls.input_tokens` for brief generation is the objective metric.

**Decided**:
- Font rule: Fraunces applies to `h1` only; `h2`/`h3` eyebrow labels use Manrope — test confirms this
- Mock test architecture: session-by-session flow is canonical; bulk-seeding all sessions then generating briefs is a known anti-pattern (brief sees all items simultaneously, defeating the context progression test)
- Style snippets require `mom.llm_call_id IS NOT NULL AND final_text != draft_text` — all sessions in mock scripts use LLM MOM generation to ensure flywheel engages from session 1

**Bugs found / fixed**:
- TabsList overflow: three long tab labels overflow `html` element width at 375px — contained with `overflow-x-auto` wrapper
- Brand rules test too strict: h2 eyebrow elements flagged as missing Fraunces — narrowed scope to h1
- MOM draft strict mode: draft text appears in both `<p>` and `<textarea>`, Playwright strict mode fails without `.first()`

**Known issues / carry-overs into next session**:
- Google OAuth not testable end-to-end until `http://localhost:8000/api/auth/google/callback` is added to Google Cloud Console Authorized Redirect URIs (user action required)
- Mock test scripts not yet run — AI context tracking hypothesis not yet validated
- HANDOVER-P6.md not yet written (user will request after completing P6 verification)

**Test count**: 40 Playwright e2e passing; backend test count unchanged from prior session (189)

---

## 2026-05-06 — P5 Part B: Manual Verification + R2 Migration + Bugfixes

**Done**:

- **AWS S3 → Cloudflare R2**: Swapped object storage to R2 free tier (10 GB / 1 M writes / 10 M reads / zero egress). Changed `config.py` fields from `aws_*` to `r2_account_id / r2_access_key_id / r2_secret_access_key / r2_bucket_name`; updated `src/lib/s3.py` host to `{bucket}.{account_id}.r2.cloudflarestorage.com`, region hardcoded to `"auto"`. Sig V4 signing unchanged. Updated `.env.example`, `VERIFICATION.md`, ADR-0001 changelog. Decision recorded in ADR-0001 (changelog 2026-05-06). Known limitation: R2 free tier has no India-region pinning — accepted at MVP scale under DPDP negative-list regime.
- **Duplicate `content-type` bug fixed in `s3_put`**: `_build_auth_header` adds `content-type` to result_headers via `extra_headers`; original code then also added `headers["Content-Type"] = content_type` explicitly. httpx merged both into `text/plain, text/plain`, causing `SignatureDoesNotMatch` 403 on every PUT. Fixed by removing the redundant post-signing assignment. Root cause found via full request trace script.
- **`ClientOut` missing `code` field**: `GET /api/clients/{id}` was not returning the `code` (CP\<NNNN\>) field. DB always had it; response schema `ClientOut` was missing it. Added `code: str | None` to `ClientOut`. All 189 tests pass.
- **`check_r2_creds.py` diagnostic script**: `backend/scripts/check_r2_creds.py` — runs PUT / GET / DELETE smoke test against real R2, prints full Authorization header and all headers httpx actually sends. Used to pinpoint the duplicate content-type and signature mismatch. Keep for future debugging.
- **Verification checklist fixes** (`docs/VERIFICATION.md`):
  - Step 4: removed incorrect PATCH client command (no such endpoint); replaced with GET to confirm auto-assigned code
  - Step 5: moved `echo > /tmp/test_note.txt` before the upload curl command
  - Step 7: updated S3 aws-cli verification commands to wrangler equivalents
  - Step 8: corrected to note that `prompt_text` stores only system prompt — "HC's typed notes" and "Uploaded files" are in `user_message` which is not persisted; prompt injection verified by integration tests only
  - All S3/AWS references updated to R2 throughout checklist and summary table
- **P5 Part B verification**: all 12 steps confirmed passing. `VERIFICATION.md` status updated to Verified 2026-05-06.
- **HANDOVER-P5.md**: written and committed — full context transfer document for P6.

**Decided**:
- R2 over S3: zero-cost MVP posture; S3-compatible Sig V4 means ~30 lines of code change
- DB row deletion is canonical for files; R2 delete is best-effort (204 returned regardless)
- `user_message` (HC notes + file content) is not persisted to DB — observability gap deferred to P8

**Bugs found during manual verification** (all fixed this session):
- Duplicate `content-type` header in `s3_put` → `SignatureDoesNotMatch` 403 on every file upload
- `ClientOut` missing `code` field → step 4 verification command appeared to fail
- Verification step 4 had wrong curl command (PATCH endpoint doesn't exist)
- Verification step 5 had file creation after upload command (curl silently failed on missing file)
- Verification step 8 checked `prompt_text` for user message content that's never stored there

**Known issues / carry-overs into P6**:
- `{{SESSION_NOTES}}` placeholder in `mom_draft.md` system prompt is never replaced — session notes travel via `user_message` instead. Dead template text; clean up in a future prompt pass.
- `user_message` not stored in DB — full LLM conversation not reconstructable from DB alone. Decide in P8 whether to add `user_message_text BYTEA` column to `llm_calls`.
- No `PATCH /api/clients/{id}` endpoint — client fields (name, email, journey_stage) cannot be updated post-creation. Needed before pilot gate.
- R2 free tier: no India-region pinning — document for pilot legal review.

**Test count**: 189 passing (was 157 after P5B code; +32 from fixes this session — test mocks updated for r2_* settings).

---

## 2026-05-05 — PHASE-05 Part B: Client File Library

**Done**:

- **B1**: Added 4 S3 env vars to `backend/src/config.py` (`aws_access_key_id`, `aws_secret_access_key`, `aws_s3_bucket_name`, `aws_region=ap-south-1`) and to `.env.example` with IAM/residency guidance comments
- **B2**: `backend/src/lib/s3.py` — full AWS Sig V4 client using Python stdlib only (`hmac`, `hashlib`, `datetime`, `urllib.parse`); no boto3; functions: `s3_put`, `s3_get`, `s3_delete`, `s3_exists`, `build_session_file_key`, `_get_session_date_ist`, `_sanitize`; all HTTP via `make_http_client()`
- **B3**: Alembic migration `df7c84b2de4f_p5b_add_client_files.py` — creates `client_files` table with 10 columns and 3 indexes; `down_revision = "bb542bec1c52"` (P5A head); separate from Part A migration per CLAUDE.md §9
- **B4**: `backend/src/db/models/files.py` — `ClientFile(Base)` ORM with write-once contract documented in docstring; `storage_path` is bare S3 key; registered in `backend/src/db/models/__init__.py`
- **B5**: `backend/src/api/files.py` — POST/GET/DELETE on `/api/sessions/{session_id}/files`; multipart upload with MIME allowlist (4 types) + 25 MB size limit; Zoom auto-detection via `zoom_ai_summary_` filename prefix; `client.code is None` → 422; S3 delete failure non-fatal (log + continue); registered in `backend/src/main.py`
- **B6**: Extended `PATCH /sessions/{session_id}` in `sessions.py` to mirror `session_notes.txt` to S3 after DB commit; S3 failure logs warning and does NOT fail the request; DB is canonical
- **B7**: `backend/src/lib/file_extraction.py` — `extract_text(content, mime_type)` handles text/plain, text/markdown, PDF (pypdf), DOCX (python-docx with Pyodide fallback); added `pypdf>=4.0` and `python-docx>=1.1` to `pyproject.toml`
- **B8+B9**: `llm_config.yaml` + `LLMConfig` extended with `file_content_max_tokens_per_file=5000` and `file_content_max_total_tokens=15000`; `get_llm_config()` uses `.get(..., default)` for safe backward compat; `_assemble_file_content_section()` helper in `llm_service/__init__.py` — fetches files from S3, extracts text, applies per-file and aggregate token budgets, returns formatted section + `zoom_present` flag; `generate_mom_draft()` and `generate_brief()` updated to assemble `## HC's typed notes:` + `## Uploaded files:` user message
- **Zoom snippet gate**: `patch_mom` in `sessions.py` now queries for `is_zoom_summary=True` files before calling `capture()`; if any Zoom file exists for the session, snippet capture is suppressed entirely
- **B10**: `docs/domain/glossary.md` updated with session_notes, session_notes.txt (S3 mirror), client_files, is_zoom_summary entries in a new "Session data terms" section
- **B12**: 24 integration tests across 5 files: `test_s3_client.py` (S3 Sig V4 signing for put + delete, key builder, sanitization), `test_file_upload.py` (single/multi upload, 25 MB limit, MIME validation, cross-tenant, DELETE idempotency, S3 delete failure resilience, Zoom filename auto-detect), `test_session_notes_mirror.py` (S3 put called with correct key/content, overwrite, S3 failure non-fatal), `test_file_prompt_injection.py` (notes+files in user_message, notes-only, per-file truncation, aggregate budget truncation, Zoom file in LLM), `test_zoom_snippet_exclusion.py` (Zoom suppresses snippet, non-Zoom allows snippet, no files allows snippet)
- **Docs**: `docs/VERIFICATION.md` — added P5 Part B manual verification checklist (12 steps, summary table)
- Total test count: 157 (133 pre-P5B baseline → 157)

**Decided** (all recorded in PHASE-05 §3):
- AWS Sig V4 via stdlib (no boto3 — Pyodide incompatible)
- Single bucket, per-HC prefix isolation (`hc-{uuid}/client_session_library/...`)
- File content fetched from S3 at prompt-assembly time (not stored in DB)
- Zoom snippet exclusion at session level (any Zoom file = all snippet capture suppressed for that session)
- S3 cascade delete is synchronous at MVP (async sweep deferred to P7)
- python-docx Pyodide failure returns empty string + warning (acceptable at MVP)

**Key implementation bugs caught and fixed during review**:
- `_get_owned_session` in first draft of `files.py` was missing `deleted_at.is_(None)` filter (data integrity) — fixed by importing from `sessions.py`
- `logger.warning()` → `logger.warn()` (BoundLogger has no `warning` method — would raise AttributeError)
- Logger structured kwargs used `extra={...}` dict instead of flat `**kwargs` — fixed to flat style
- `extract_text()` was outside the `try` block in `_assemble_file_content_section` — corrupt files would crash LLM call; fixed by moving into try
- Negative `remaining_budget` (cumulative overrun) → `text[:-n]` silently admitted too much content; fixed with `max(0, ...)` + `break`

**Pending**:
- SoJo manual verification of Part B (see `docs/VERIFICATION.md` § P5 Part B)
- P6: Frontend UI (coach-facing) — connects to all P5 endpoints

**Context the next session needs**:
- Part B is NOT verified until SoJo confirms manual steps in VERIFICATION.md § P5 Part B
- S3 must be configured in `.env` for manual verification (4 vars: aws_access_key_id, aws_secret_access_key, aws_s3_bucket_name, aws_region)
- `client.code` must be set on the client record before file upload (API returns 422 if None)
- `build_session_file_key()` in `src/lib/s3.py` is the single source of truth for all S3 paths — never construct paths elsewhere
- `session_notes.txt` is always a mirror (never read back by the system); DB column is canonical
- The `_get_session_date_ist()` function in `s3.py` is technically private but is imported by `files.py` and `sessions.py` — rename to public in a follow-up
- TODO (P7): async S3 orphan cleanup sweep; auto-flag missed action items on due_date; s3_presign_get() for frontend file display

---

## 2026-05-05 — PHASE-05 Part A: HC Cycle Workflows

**Done**:

- Wrote `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md` — full 8-section PHASE plan for both Part A and Part B; SoJo confirmed plan before implementation began
- **A1**: Alembic migration `bb542bec1c52_p5_add_session_notes.py` — adds `sessions.session_notes TEXT` nullable; migration chain: P4 (`95df31e31f5f`) → P5 A1 (`bb542bec1c52`)
- **A2**: ORM: `session_notes: Mapped[str | None] = mapped_column(Text)` added to `backend/src/db/models/sessions.py`
- **A3+A4**: `SessionPatch` schema + `PATCH /sessions/{session_id}` endpoint in `backend/src/api/sessions.py`; `SessionOut` extended with `session_notes: str | None`
- **A5**: `draft_mom` now persists `body.session_notes` to `sessions.session_notes` + `await db.flush()` before LLM call (timeout protection)
- **A6**: `GET /clients/{client_id}/ast` endpoint in `backend/src/api/clients.py` with `AstOut` + `ActionItemOut` schemas; computes at request time: open/missed items, status_summary (14-day check-ins), triage_flags (missed_action_item, no_recent_checkin, manual_sentiment_flag)
- **A7**: `generate_brief()` in `backend/src/llm_service/__init__.py` extended with M000 path (session_number==0 → static template, no LLM, llm_call_id=None) and M00N path (full AST + triage computation, server-computed flags not from LLM); added `CHECKIN_TRIAGE_DAYS = 14` and `SENTIMENT_LOOKBACK_DAYS = 30` constants
- **A8**: `backend/prompts/brief_assemble.md` bumped from v1.0.0 → v1.1.0; added `{{AST_SECTION}}` and `{{TRIAGE_SECTION}}` placeholders
- **A9**: `docs/diagrams/0002-data-model.md` updated with P4 deltas (clients.code, llm_calls.prompt_text/completion_text) and P5 addition (sessions.session_notes); "MERGE-REQUIRED" banner removed
- **A10**: 21 integration tests across 4 new files: `test_session_notes.py`, `test_ast_endpoint.py`, `test_brief_extended.py`, `test_mom_workflow.py`
- **Bug fix**: `client.metadata` → `client.metadata_` (SQLAlchemy column alias) in M000 brief path
- Total test count: 144 (P4 baseline) → 165 (P5 Part A)

**Decided**:
- M000 detection: `session.session_number == 0` (not a non-existent `is_first_session` column)
- M000 brief: `briefs` row still created for idempotency, but `llm_call_id=None`; no `llm_calls` row written
- Triage flags are server-computed (not from LLM parsed output) — more reliable
- `Client.metadata_` is the ORM attribute name (maps to `metadata` column) — critical to note for future sessions

**Pending**:
- SoJo manual verification of Part A (see `docs/VERIFICATION.md` § P5 Part A)
- Part B (Client File Library: S3, client_files table, file upload/list/delete endpoints, session_notes.txt mirroring, file content injection in LLM prompts, Zoom summary detection) — starts only after Part A is verified

**Context the next session needs**:
- Part A is NOT verified until SoJo confirms manual steps in VERIFICATION.md § P5 Part A
- Part B deliverables B1-B12 are specified in `PHASE-05-hc-cycle-workflows.md` §2
- Key Part B decisions: AWS Sig V4 via stdlib (no boto3, Pyodide incompatibility), synchronous S3 cascade delete at MVP, Zoom snippet exclusion at session level
- `backend/src/config.py` needs 4 new AWS vars for Part B; `.env.example` also needs updating

---

## 2026-05-04 — PHASE-04 retroactive write + convention lock-in

**Done**:
- Rewrote `docs/specs/Unit_001_HcCoreCycle/PHASE-04-llm-service.md` from its old SPEC-style content (Goal, Non-goals, Actors, Mermaid diagrams, etc.) to a proper 8-section PHASE document matching `docs/specs/template-phase-plan.md`
- Content sourced strictly from SESSION_LOG 2026-05-04 (P4 entry) and VERIFICATION.md § P4 — no fabrication
- Updated `docs/build-plan.md`: P4 phase plan note changed from "not yet written" to a proper link; "How to use this when working with Claude Code" loop now includes "write the PHASE file before implementation begins" as step 1

**Decided**:
- P4 was the last retroactive PHASE file. All future phases (P5 onward) must have their PHASE-NN file written **before** the build sprint begins, not after — per the SPEC-before-code rule in CLAUDE.md §6 and the build-plan loop
- PHASE file convention is now locked: `Unit_001_HcCoreCycle/PHASE-NN-kebab-title.md`, 8 sections per `template-phase-plan.md`, linked from the corresponding build-plan.md phase section

**Pending / next session**:
- P5: HC Cycle Workflows
- Before writing any P5 code: write `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md` using `template-phase-plan.md`

**Context the next session needs**:
- PHASE file must be written and confirmed by SoJo before P5 implementation starts — this is not optional
- The PHASE file for P5 should reference SPEC-0001 §HC Cycle (the acceptance criteria it implements) and ADR-0003 §LLM strategy

---

## 2026-05-04 — Naming cleanup: Unit-scoped specs + retroactive phase plans

**Done**:
- Committed all uncommitted P4 work (43 files, migration `95df31e31f5f`, full `llm_service/` module, 144/144 tests)
- Created `docs/specs/Unit_001_HcCoreCycle/`
- Moved `0001-hc-core-cycle.md` → `Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` (history preserved via `git mv`)
- Moved `0004-llm-service.md` → `Unit_001_HcCoreCycle/SPEC-0002-llm-service.md`; updated internal header from `Spec-0004` to `SPEC-0002`
- Wrote retroactive PHASE plans for P0–P3 (`PHASE-00-repo-scaffolding.md`, `PHASE-01-data-layer.md`, `PHASE-02-auth-service.md`, `PHASE-03-domain-crud.md`); all content sourced strictly from SESSION_LOG and ADRs — no fabrication
- Created `docs/specs/template-phase-plan.md` and `.claude/skills/skill-write-phase-plan.md`
- Created `.claude/skills/skill-write-spec.md`; updated `docs/specs/0000-template_SPEC.md` with SPEC-vs-PHASE distinction header and "Implemented by phases" field
- Updated `CLAUDE.md` — added new §6 "Working with product files" (naming convention, unit structure, cross-cutting docs stay flat); renumbered subsequent sections §7–§12
- Created `PROJECT-CUSTOM-INSTRUCTIONS.md` at repo root (SoJo to upload to claude.ai Project knowledge)
- Updated cross-references across all active docs to new paths: `docs/decisions/0001, 0003, 0004`, `docs/diagrams/0002-data-model.md`, `docs/ops/secrets-management.md`, `docs/ops/incident-response.md`, `docs/REPO-INDEX.md`, `PREFLIGHT.md`
- Updated `docs/build-plan.md` — each phase section now links to its `PHASE-NN-...md` file

**Decided**:
- Naming convention locked: `docs/specs/Unit_NNN_PascalCaseName/SPEC-NNNN-...md` and `PHASE-NN-...md`
- Phase numbering resets per unit; SPEC numbering resets per unit
- LLM Service is `SPEC-0002` inside `Unit_001_HcCoreCycle` — not a separate unit; it serves the HC core cycle
- ADRs and diagrams stay flat in existing folders; no per-unit subfolders
- Retroactive PHASE plans are thorough, not thin; accuracy sourced strictly from SESSION_LOG and ADRs
- `PROJECT-CUSTOM-INSTRUCTIONS.md` lives at repo root; SoJo uploads to Claude Project knowledge after updates

**Bugs fixed mid-session**:
- None (doc-only session; no code changes)

**Pending / next session**:
- P5: HC Cycle Workflows
- Write retroactive PHASE-04 (LLM service) before P5 starts, or at start of P5 session

**Context the next session needs**:
- All future phases follow the same convention: write SPEC first (if new unit/feature), then write PHASE plan, then implement
- The phase plan for P5 uses `docs/specs/template-phase-plan.md` and lives at `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md`
- `PROJECT-CUSTOM-INSTRUCTIONS.md` at repo root needs to be uploaded to claude.ai Project knowledge before the P5 session

**Open questions for SoJo**:
- Should LLM Service eventually become its own unit (`Unit_002_LlmService`) as the module grows? Currently it's `SPEC-0002` inside `Unit_001_HcCoreCycle`. Fine for MVP; revisit if the LLM service becomes product-facing rather than internal.
- `PHASE-04-llm-service.md` not written in this session (scope was P0–P3 only). Write retroactively before P5, or defer?

---

## 2026-05-04 — P4: LLM Service

**Done**:
- **Migration `95df31e31f5f`** (ran earlier session): `pgcrypto` extension, `llm_calls.prompt_text` + `completion_text` (BYTEA, pgcrypto-encrypted), `clients.code` (CP0001 pseudonym, unique per HC), `llm_calls.client_id` FK → `ondelete=CASCADE`.
- **`backend/prompts/`**: three prompt files with YAML frontmatter — `mom_draft.md` (v1.0.0), `brief_assemble.md` (v1.0.0), `ai_assist.md` (v1.0.0, endpoint wired P5).
- **`src/llm_service/`** — full module:
  - `llm_config.yaml`: 4-model chain (llama-3.3-70b primary, gemma-3-27b, gpt-oss-120b, nemotron-3-super-120b-a12b), snippet settings, validation_retry_count=1.
  - `config.py`: `LLMConfig` dataclass, `get_llm_config()` (lru_cache).
  - `prompts.py`: `PromptFile`, `load_prompt()` — YAML frontmatter parser.
  - `tracking.py`: `write_llm_call()` — raw SQL INSERT with `pgp_sym_encrypt()`.
  - `snippets.py`: `capture()` (diff gate: threshold + whitespace filter), `select()` (Option C hybrid: pool of 25 by created_at, re-sorted by last_used_at ASC NULLS FIRST, stopped at 2K token budget), `update_usage()`.
  - `client.py`: `call_openrouter()` — uses `make_http_client`, returns `OpenRouterResult`.
  - `chain.py`: `build_models_array()`, `fallback_count_for()`.
  - `retry.py`: `parse_or_retry()` — one retry with stricter format hint.
  - `schemas/`: `MomDraftSchema` (with `to_draft_text()`), `BriefSchema` (with `to_brief_text()`), `ActionItemSchema`.
  - `__init__.py`: `generate_mom_draft()`, `generate_brief()` — full orchestration (snippets, LLM, tracking, error handling).
- **`src/api/sessions.py`** updated:
  - `MomOut` + `BriefOut` now include `llm_call_id`.
  - New `POST /{session_id}/mom/draft` — generates AI draft, upserts MOM.
  - `GET /{session_id}/brief` — cache-first, then generates via LLM (replaced P3 404 stub).
  - `PATCH /{session_id}/mom` — snippet capture gate: fires only when `mom.llm_call_id IS NOT NULL` and final_text != draft_text.
- **`src/telemetry/scrub.py`**: `prompt_text` + `completion_text` added to `_PII_KEYS`.
- **Tests**: `test_llm_tracking.py` (4), `test_llm_snippets.py` (9), `test_mom_draft.py` (7), `test_scrub_extended.py` (4), `test_llm_service_config.py` (7), `test_llm_service_prompts.py` (7) — all new, all green.
- Removed stale P3 test `test_get_brief_returns_404_when_none` (that stub is now P4 generation).
- **144/144 tests passing**.

**Decided**:
- Decision A — Snippet selection Option C hybrid (pool of 25 most-recent, then last_used_at ASC NULLS FIRST within pool, stop at 2K token budget). `snippet_pool_size` in llm_config.yaml.
- Decision B — Amend ADR-0006 §5: store encrypted `prompt_text` + `completion_text` in `llm_calls` via pgcrypto BYTEA. Three protections: client pseudonymization (CP<NNNN>), column-level pgp_sym_encrypt, tenant-scoped reads.
- Fallback key (`"dev-only-placeholder-not-for-production"`) used when `LLM_CALL_ENCRYPTION_KEY` is empty — ensures pgp_sym_encrypt never receives empty passphrase; production must set a real key.

**Out of scope** (P5+):
- Action item extraction endpoint (ai_assist.md prompt created; wired P5)
- Snippet retirement sweep (P7)
- Full AST + triage flags in brief (P5)
- ADR-0003/0006 formal amendment docs

**Manual verification**: `docs/VERIFICATION.md` → P4 section — **verified 2026-05-04**.

**Post-verification bugs fixed**:
- `clients.code NOT NULL` violation on `POST /api/clients` — migration made code NOT NULL but `create_client` never assigned it. Fixed: `create_client` now computes `CP<NNNN>` via `MAX(CAST(SUBSTRING(code FROM 3) AS INTEGER)) + 1` before insert.
- `llm_config.yaml` had 4 models — OpenRouter `models` array limit is 3. Fixed: removed `openai/gpt-oss-120b:free` (not a valid slug). Chain is now llama-3.3-70b → gemma-3-27b → nemotron-3-super-120b-a12b.
- LLM call silently timed out with empty `detail` — httpx default timeout is 5 s; free models can take 30–60 s. Fixed: `timeout=120.0` on the `make_http_client()` call in `client.py`. Also changed `detail=str(exc)` → `detail=repr(exc)` so future errors are never silently empty.

**Known issues / follow-ups noted after verification**:
- **Unicode in draft_text**: LLMs sometimes emit ` ` (NARROW NO-BREAK SPACE) and similar typographic characters in their output (e.g. in place of apostrophes or as non-breaking spaces). The backend stores LLM output faithfully — normalization/replacement should happen in the **frontend** when rendering MOM text. Frontend team to handle before GA.
- **Prompt version test (#14) is one-time**: test #14 in VERIFICATION.md verifies the prompt-version-in-llm_calls traceability chain. Only needs re-running after changes to `src/llm_service/prompts.py`. Not a recurring verification item.
- **pgcrypto BYTEA is expected**: `prompt_text` and `completion_text` in `llm_calls` are pgcrypto-encrypted binary, not plain text. To read for debugging: `SELECT pgp_sym_decrypt(prompt_text, '<LLM_CALL_ENCRYPTION_KEY>') FROM llm_calls WHERE id = '...';`. Columns are nullable for error-path rows where no LLM call completed.

---

## 2026-05-02 — P3: Domain CRUD + Client-Facing Endpoints

**Done**:
- **Schema extensions** (migration `60775f9338d3`): `users.role`, `clients.user_id` (FK to users, nullable, for client OAuth linking), `sessions.deleted_at` (soft-delete), `client_invite_tokens` table (SHA256 hash, 30-day TTL, single-use). Schema decisions D-1/D-2/D-3 confirmed.
- **`src/api/deps.py`**: `HcClaimsDep`, `ClientClaimsDep`, `TenantDep`, `DbDep`, `LimitDep`, `PaginatedList[T]`, `encode_cursor()` / `decode_cursor()` shared by all routers.
- **`src/api/clients.py`**: POST /api/clients, GET /api/clients (cursor paginated), GET /api/clients/{id}, POST /api/clients/{id}/invite (SHA256 token, invalidates prior unused tokens). Cross-tenant 404 via `_get_owned_client()`.
- **`src/api/sessions.py`**: Sessions CRUD (create/list/get/end), MOM lifecycle (create/get/patch/send), GET brief (404 stub at P3). Duplicate session_number → 409. Idempotent `end` and `send`.
- **`src/api/action_items.py`**: POST/GET/GET/{id}/PATCH action items. `completed_at` set/cleared on status transitions. All HC transitions allowed.
- **`src/api/check_ins.py`**: GET /api/clients/{id}/check-ins (HC reads), PATCH /api/check-ins/{id}/flag (set/clear `sentiment_flag`). `model_fields_set` used to distinguish explicit `null` from omitted.
- **`src/api/me.py`**: POST /api/me/check-ins (client submits), GET /api/me/moms (sent only), GET /api/me/action-items. Client resolved from JWT `sub` + `hc_id` claims.
- **conftest.py rewrite**: savepoint-based test isolation (`join_transaction_mode="create_savepoint"`), test JWT keys injected before src imports, `client_user` / `client_rec` / `client_headers` fixtures added.
- **92 tests passing** (was 37 after P2).

**Decided**:
- D-1: `users.role` column (server_default `'hc'`) — role stamped at account creation, not derived at query time.
- D-2: `client_invite_tokens` table — separate table (not inline on clients) to support TTL, single-use, audit trail.
- D-3: Invite TTL = 30 days.
- Deleted redundant `docs/specs/0002-domain-crud.md`; `0001-hc-core-cycle.md` is the authoritative P3 spec.
- Cross-tenant responses are always 404 (never 403) to prevent existence leakage.
- Client ME endpoints use `claims.sub` as client's user_id; `hc_id` from JWT pins the tenant.

- **`src/auth/router.py` — client OAuth**: `GET /api/auth/client/start?invite=<token>` (verify invite, initiate Google OAuth), `GET /api/auth/client/callback` (exchange code, link Client record, mark invite used, issue role=client JWT). Fixed `/api/auth/refresh` to use `user.role` instead of hardcoded `"hc"` and look up `hc_user_id` from client record for client users.
- **`src/api/me.py` additions**: `GET /api/me/moms/{id}` (404 if not sent), `PATCH /api/me/action-items/{id}` (client marks own items complete/in_progress).
- **107 tests passing**.
- `VERIFICATION.md` updated with full P3 manual-check section (12 checks).

**P3 status**: ✅ complete — manual verification passed 2026-05-02.

**Issues found during manual verification** (fixed in same session):
- `env_file=".env"` in config.py didn't find root `.env` when running from `backend/` → fixed to `(".env", "../.env")`
- Verification step 3 generated a random JWT sub with no users row → replaced with `scripts/create_hc_user.py` that inserts a real user first
- Heredoc in verification instructions caused terminal issues → moved to script file
- 15-minute JWT expiry too short for full manual verification → script now issues 8-hour tokens
- `!!!` in curl URL triggered bash history expansion → switched to single-quoted URL

**Pending / next session**:
- P4: LLM integration (brief generation, MOM draft assist)

---

## 2026-05-01 — P0 / P1 / P2: Scaffold → Data Layer → Auth

**Done**:
- **P0**: git init, pyproject.toml (`[dependency-groups]` PEP 735), docker-compose, `.env.example`, FastAPI app with CORS + request-id middleware + `/healthz`, telemetry scaffolding (`scrub()`/`get_logger()`/Sentry stub), `make_http_client()` factory, Next.js 16 frontend skeleton, `CONTRIBUTING.md` with dev commands
- **P1**: 16-table SQLAlchemy 2.0 models (6 files by domain), async session factory (`get_db()`), Alembic `env.py` with async engine, initial migration (`e8a1523b2f3a`), roundtrip + cascade-delete integration tests (29 total passing)
- **P2**: ES256 JWT sign/verify (`python-jose`), Google OAuth PKCE flow, refresh token rotation with replay detection, `require_role()` + `current_tenant()` FastAPI dependencies, auth router (4 endpoints), auth integration tests (37 total passing)

**Decided** (link ADRs):
- ADR-0003 flipped to Accepted before P1 coding started
- `llm_calls` schema reconciled: `model_requested`/`model_served`/`prompt_version`/`request_id` (per ADR-0003 amendment)
- `auth_refresh_tokens` added to data model diagram (was missing)
- `retired_at` added to `hc_style_snippets`
- Circular FK (`moms`/`briefs` → `llm_calls`) handled via deferred `op.create_foreign_key()` in migration
- `backend/.venv` → symlink to `/mnt/hdd/yourProjects/venv/hc_pf` for single shared Python env
- Replay detection check order: `successor_id` checked before `revoked_at` in `rotate_refresh_token()`

**Bugs fixed mid-session**:
- `server_default="'onboarding'"` triple-quoted by SQLAlchemy `create_all()` → fixed to `server_default=text("'onboarding'")` + Python-side `default=`
- `auth_refresh_tokens` partial index used `NOW()` (volatile) in predicate → fixed to `WHERE revoked_at IS NULL`
- pytest-asyncio event loop scoping → added `asyncio_default_test_loop_scope = "session"` to `pyproject.toml`

**Pending / next session**:
- P2 manual verification (see `docs/VERIFICATION.md`)
- P3: Domain CRUD endpoints (clients, sessions, MOMs, action items, check-ins)
- Install Postgres MCP (read-only) per `starter_prompt_01.md`

**Context the next session needs**:
- Run `docs/VERIFICATION.md` P2 checklist before starting P3
- P3 source docs: `docs/diagrams/0002-data-model.md`, `docs/domain/glossary.md`, `docs/domain/actors.md`
- P3 spec: `docs/specs/` — write spec before coding, per CLAUDE.md rule 9
- Node 22 required for frontend: `export PATH=~/.nvm/versions/node/v22.15.1/bin:$PATH`

**Open questions for SoJo**:
- Google Cloud Console credentials needed before OAuth callback can be fully tested end-to-end
- P3 priority order: clients → sessions → MOMs, or a different slice?

---

## YYYY-MM-DD — [topic]

**Done**:
- ...

**Decided** (link ADRs):
- ...

**Pending / next session**:
- ...

**Context the next session needs**:
- ...

**Open questions for SoJo**:
- ...

---
