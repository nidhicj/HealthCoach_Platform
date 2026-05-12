# Handover: P0–P6 Complete → P7 Context for Claude

> This document is a complete context transfer. Read it fully before writing any P7 code.
> It replaces the need to read git history. Treat everything here as authoritative current state.

---

## What this product is

**Parivarthan** — a webapp for independent health coaches (HCs) in India. HCs use it to:
1. Onboard and manage clients
2. Run sessions with AI-assisted MOM (Minutes of Meeting) generation
3. Send action items to clients
4. Run between-session check-ins
5. Build a personalised AI writing style via snippet capture (HC edits to AI drafts)

**Current users**: coach only. Clients exist in the data model and have auth + ME endpoints, but no frontend yet.  
**Geography**: India-first. DPDP Act 2023 applies (explicit consent, real deletion, India-region hosting).  
**Stage**: production repo. Prototype learnings only — no code copied from prototype.

---

## Stack (locked, ADR-0001 Accepted)

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.12), targeting Cloudflare Python Workers |
| Database | PostgreSQL 16 via asyncpg + SQLAlchemy 2.0 async |
| Migrations | Alembic (5 migrations — see §Migrations) |
| Auth | Google OAuth 2.0 + PKCE → ES256 JWT (python-jose) + refresh token rotation |
| LLM | OpenRouter — 3-model chain: Llama 3.3 70B (primary) → Gemma 3 27B → Nemotron 120B |
| Object storage | Cloudflare R2 (free tier — 10 GB / 1 M writes / 10 M reads / zero egress). S3-compatible Sig V4. |
| Frontend | **Next.js 16.2.4** App Router, Tailwind v4, shadcn/ui + Base UI (`@base-ui/react ^1.4.1`) |
| Frontend testing | Playwright ^1.59.1 (e2e), Vitest ^4.1.5 (unit) |
| Package manager | uv (Python), npm (Node 22) |
| Backend tests | pytest-asyncio, savepoint-based isolation |

> **Note on Next.js version**: HANDOVER-P5 anticipated Next.js 15. P6 was built on **16.2.4** (released between
> phases). The ADR-0001 intent (App Router, Tailwind, shadcn) is unchanged. Update ADR-0001 if needed.

**Cloudflare Workers constraint**: Workers run Pyodide (WebAssembly). `asyncpg` and `SQLAlchemy` are
C-extension packages — NOT Pyodide-compatible. DB-touching endpoints run on **DO Bangalore** per ADR-0002.
Use `uvicorn` for local dev.

---

## Repo layout (current state after P6)

```
parivarthan_platform/
├── .env.example                    # all env vars documented
├── .gitignore                      # updated P6: test-results/, *.tar.gz, *.zip
├── CLAUDE.md                       # operating contract — read before coding
├── docs/
│   ├── SESSION_LOG.md              # append-only session history
│   ├── VERIFICATION.md             # manual checklists P1–P6 + AI mock test appendix
│   ├── build-plan.md               # P0–P9 acceptance criteria (source of truth)
│   ├── decisions/                  # ADRs 0001–0006 (all Accepted)
│   ├── HANDOVER-P5.md              # P5 context (superseded by this file)
│   └── specs/Unit_001_HcCoreCycle/
│       ├── SPEC-0001-hc-core-cycle.md
│       └── PHASE-00 through PHASE-06 ← all written and complete
│
├── backend/
│   ├── src/
│   │   ├── auth/router.py          # ★ P6: email-upsert in google_callback (see §Auth changes)
│   │   └── [rest unchanged from P5]
│   └── scripts/
│       ├── create_hc_user.py       # ★ P6: accepts --email arg; upserts by email
│       ├── check_r2_creds.py       # R2 smoke test
│       ├── check_r2_creds_boto.py  # boto3 variant of R2 smoke test
│       └── mock_p6/                # ★ NEW: AI context-tracking mock test suite
│           ├── lib.sh              # shared HTTP/date/session/display helpers
│           ├── 01_foundation.sh    # HC user + 3 clients
│           ├── 02_maya.sh          # Maya — 2 sessions, onboarding
│           ├── 03_ravi.sh          # Ravi — 5 sessions, weight loss
│           ├── 04_sunita.sh        # Sunita — 8 sessions, PCOD management
│           ├── 04_sunita_resume.sh # Resume script if 04 crashes mid-run
│           └── 05_verify_flywheel.sh # DB inspection: snippets + token progression
│
└── frontend/                       # ★ ENTIRELY NEW in P6
    ├── next.config.ts
    ├── playwright.config.ts
    ├── vitest.config.ts
    ├── src/
    │   ├── app/
    │   │   ├── (app)/              # authenticated route group
    │   │   │   ├── dashboard/
    │   │   │   ├── clients/
    │   │   │   │   ├── page.tsx    # client list
    │   │   │   │   ├── new/        # create client
    │   │   │   │   └── [clientId]/
    │   │   │   │       ├── page.tsx          # client detail + AST
    │   │   │   │       └── sessions/
    │   │   │   │           ├── new/          # create session
    │   │   │   │           └── [sessionId]/  # brief + notes + MOM editor
    │   │   │   ├── action-items/
    │   │   │   └── settings/
    │   │   ├── (public)/sign-in/
    │   │   └── auth/callback/      # handles Google OAuth redirect
    │   └── lib/
    │       ├── api/                # typed API client (clients, sessions, files,
    │       │                       #   action_items, check_ins, auth)
    │       ├── auth/               # token storage, OAuth client, redirect logic
    │       └── config.ts
    └── tests/
        ├── e2e/                    # 40 Playwright tests (all passing)
        │   ├── auth.spec.ts
        │   ├── brand-rules.spec.ts
        │   ├── core-cycle.spec.ts
        │   ├── mobile-375.spec.ts
        │   └── fixtures/
        └── unit/                   # Vitest unit tests
            ├── api-schemas.test.ts
            ├── auth-flow.test.ts
            └── theme-build.test.ts
```

---

## Auth changes (P6 addition)

### Email-upsert in `google_callback`

**Problem**: `create_hc_user.py --email` creates a user with a placeholder `google_sub`
(`pending-oauth-<hash>`). When the HC logs in via Google, the `google_sub` lookup would miss and
create a second orphan row — mock data would be invisible in the frontend.

**Fix** (`src/auth/router.py`, `google_callback` only):

```python
# 1. Try google_sub match (existing real users)
user = lookup_by_google_sub(user_info.sub)

# 2. Email fallback: finds dev-seeded users with placeholder google_sub
if user is None:
    user = lookup_by_email(user_info.email)

# 3. Create new user if neither matches
if user is None:
    user = User(email=..., google_sub=..., ...)
    db.add(user)
else:
    # Claim the row — update google_sub + profile fields to real values
    user.google_sub = user_info.sub
    user.display_name = user_info.name
    user.photo_url = user_info.picture
```

This means: run the mock scripts → log in via Google → the row is claimed → all mock data appears.

This is also the correct production behaviour for any account-linking scenario.

---

## P6 frontend: key implementation notes

| Area | Detail |
|---|---|
| **Tab overflow at 375px** | Session page `TabsList` wrapped in `<div className="overflow-x-auto">`. Three long tab labels ("Pre-session brief", "In-session notes", "MOM editor") overflow 327px available width otherwise. |
| **Font rule** | `h1` uses Fraunces (font-heading). `h2`/`h3` eyebrow labels use Manrope (font-sans) — intentional per brand. E2e brand test checks `h1` only. |
| **MOM strict mode** | Draft text appears in both `<p>` (display) and `<textarea>` (editable). Playwright selectors use `.first()` to disambiguate. |
| **Auth error text** | Auth callback page shows "Sign-in failed. Redirecting to sign-in…" — test regex `/sign-in failed/i`. |
| **M000 UX gap** | The M000 onboarding session exists in DB after client creation, but the frontend has no prompt directing the HC to fill in intake notes. Coach must navigate manually to the M000 session page. This is a known gap — see §Known issues. |

---

## Mock test suite (`backend/scripts/mock_p6/`)

Purpose: validates the AI context-tracking hypothesis (do briefs get richer as sessions accumulate?)
and the style flywheel (do MOM drafts learn the HC's voice?).

**Session-by-session architecture** (critical): each brief is generated AFTER previous sessions'
items are in the DB and BEFORE the current session's notes/items are added. This is the only correct
way to simulate real context accumulation. Bulk-seeding and then generating briefs in one pass defeats
the test.

**Run order**:
```bash
cd backend
bash scripts/mock_p6/01_foundation.sh   # HC user (joshichi.nidhi@gmail.com) + 3 clients
bash scripts/mock_p6/02_maya.sh          # 2 LLM calls
bash scripts/mock_p6/03_ravi.sh          # 10 LLM calls
bash scripts/mock_p6/04_sunita.sh        # 16 LLM calls (or 04_sunita_resume.sh if crash)
bash scripts/mock_p6/05_verify_flywheel.sh  # DB inspection only
```

**Reset before each run**:
```sql
TRUNCATE TABLE audit_log, hc_style_snippets, auth_refresh_tokens, client_invite_tokens,
  client_files, content_assignments, diet_chart_recipes, diet_charts, prep_recipes,
  action_items, moms, briefs, check_ins, llm_calls, sessions, consents, clients, users
RESTART IDENTITY CASCADE;
```

**Green flags**: `input_tokens` grows S1→S5 (Ravi) and S1→S8 (Sunita); `snippet_count ≥ 1` in
latest MOM drafts; ≥ 5 total `hc_style_snippets`.

**Known failure mode**: slow LLM response can cause curl to drop the connection before receiving the
full body, leaving the bash variable empty even though the backend stored the result. `lib.sh`
`print_brief`/`print_mom_draft` now degrade gracefully instead of crashing. If a session crashes,
check the DB (brief likely exists), then use the resume script or re-run that script from scratch.

---

## Test suite

| Suite | Count | Runner |
|---|---|---|
| Backend integration | 189 | pytest-asyncio |
| Frontend e2e | 40 | Playwright (Chromium) |
| Frontend unit | ~12 | Vitest |

```bash
# Backend
cd backend && source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
python3 -m pytest tests/ -q          # 189 passed

# Frontend e2e (requires backend + frontend both running)
cd frontend && npx playwright test

# Frontend unit
cd frontend && npx vitest run
```

---

## Production Error Handling & Observability — Design Gap Report

> **Why this section exists**: During the P6 mock test, a slow LLM response caused curl to drop the
> connection before receiving the full response body. The backend stored the result correctly, but the
> shell script captured an empty variable and crashed with a cryptic `JSONDecodeError`. This is a
> contained dev-tooling issue, but it surfaced a broader question: *what happens when something like
> this occurs in production, where the HC has no shell to debug and no idea what went wrong?*
>
> This section documents the current state, what production needs, and what should be built in P7/P8.
> It is intentionally thorough — use it as the brief for a spec or ADR in a future session.

### Current state (after P6)

| Concern | Status |
|---|---|
| Backend exception logging | `structlog` wired; `scrub()` redacts PII before logging |
| Sentry DSN | In `.env.example`, referenced in `config.py` — **stubbed, never initialised** |
| LLM call logging | `llm_calls` table records tokens, latency, model, prompt version |
| LLM call failures | Not recorded in DB. A failed LLM call leaves no trace. |
| LLM request timeout | **None set.** `httpx` default is no timeout. |
| LLM retry logic | **None.** One attempt, then exception propagates to HTTP 500. |
| Frontend error handling | No error boundaries. Unhandled API errors show blank UI or browser console only. |
| User-facing error messages | Generic. HC has no error code to report to maintainer. |
| Alerting | Nothing. No page, no email, no Slack message on errors. |
| Health check | `/healthz` endpoint exists (P0) — not monitored externally. |

### What production needs (ordered by priority)

#### 1. LLM call resilience (P7 — implement before pilot)

The LLM is the most failure-prone external dependency. Three things are needed:

**Timeout**: All LLM HTTP calls must have an explicit timeout. OpenRouter's p99 latency for
70B-class models is ~15s. A reasonable production timeout is 45s for brief generation (longer context)
and 30s for MOM draft. Without a timeout, a hung LLM request holds a Uvicorn worker indefinitely.

```python
# In src/lib/http.py or src/llm_service/__init__.py
async with make_http_client(timeout=httpx.Timeout(45.0)) as client:
    ...
```

**Retry with exponential backoff**: LLM providers return 429 (rate limit) and occasional 5xx. A
retry policy of 2 retries with jitter (e.g., `tenacity`) is standard. Do not retry on 4xx (client
error). Do not retry if the HC is waiting in-browser — show the error instead.

**Failure logging**: When an LLM call fails (timeout, 4xx, 5xx, parse error), write a row to
`llm_calls` with `status='failed'` and the error detail. This gives observability without PII
leakage. Currently the `llm_calls` table has no `status` or `error` column — this needs a migration.

Proposed column additions to `llm_calls`:
```sql
status        TEXT    DEFAULT 'success'  -- 'success' | 'failed' | 'timeout'
error_detail  TEXT    NULL               -- short error string, no PII
```

#### 2. Sentry integration (P7 — implement before pilot)

Sentry is already in `.env.example` but never initialised. Three things to wire up:

**Backend**: Call `sentry_sdk.init(dsn=settings.sentry_dsn, ...)` in `src/main.py` at startup.
The `scrub()` function already exists for PII redaction — configure Sentry's `before_send` hook
to run it. Set `traces_sample_rate=0.1` (10% of requests traced; adjust post-pilot).

**Frontend**: `@sentry/nextjs` package — wrap App Router with Sentry's Next.js instrumentation.
Captures unhandled React errors, failed fetch calls, and client-side route errors. Configure
`ignoreErrors` for expected auth redirects.

**Alert rules** (configure in Sentry dashboard):
- Any new exception type → email to maintainer immediately
- LLM call failure rate > 5% in 1 hour → email alert
- `500` response rate > 1% → email alert

#### 3. Frontend error boundaries (P7)

React error boundaries catch exceptions during render and replace crashed subtrees with a fallback.

**Minimum viable implementation**:
- One root-level error boundary wrapping `(app)/layout.tsx`
- Fallback UI: "Something went wrong. Please refresh the page. If this keeps happening, contact support."
- Display an **error reference code** (short UUID or timestamp-based) that the HC can copy and send to the maintainer
- The same error reference code should appear in the Sentry event — so the maintainer can look it up

**Error reference code pattern**:
```
Error ref: ERR-20260507-A3X9
```
HC pastes this into a WhatsApp message to the maintainer. Maintainer searches Sentry. Full trace found.

#### 4. HC-facing error messaging (P7)

When an API call fails, the HC currently sees either a blank UI or a spinner that never resolves.
What they should see instead:

| Scenario | HC sees | What the maintainer receives |
|---|---|---|
| LLM timeout during brief generation | "Brief generation is taking longer than usual. Try again in a moment." + retry button | Sentry event tagged `llm_timeout` + session_id |
| LLM timeout during MOM draft | "Draft generation failed. Your notes are saved. Try again." | Sentry event tagged `llm_timeout` |
| API 500 on any write action | "Something went wrong saving your work. Ref: ERR-XXXXX. Contact support." | Sentry event with ref code |
| API 401 (session expired) | "Your session has expired. Please sign in again." → redirect to sign-in | No alert needed |
| R2 file upload failure | "File upload failed. Check your internet connection and try again." | Sentry event tagged `r2_upload_fail` |

The key principle: **the HC is a practitioner, not a developer**. Error messages must be in plain
language, must not expose technical details, and must give them exactly one action to take
(retry, or contact support with a reference code). They should never see a stack trace, a 500
status code, or a JSON error body.

#### 5. Maintainer alerting channel (P7 — decide before pilot)

At pilot scale (1–5 HCs), a simple alerting setup is sufficient:

**Option A — Sentry email alerts** (simplest):
Configure Sentry alert rules to email `shriramsomeshwar@gmail.com` for any unhandled exception.
No extra infra. Works immediately after Sentry init is wired.

**Option B — Sentry → Slack/WhatsApp**:
Sentry has a Slack integration. For WhatsApp, use a Sentry webhook → a small Cloud Run function →
WhatsApp Business API. More setup, more useful for production.

**Recommendation**: Start with Option A (email) for pilot. Add WhatsApp before public launch.

#### 6. Health monitoring (P8 — before public launch)

The `/healthz` endpoint exists but nothing watches it. Minimum needed before public launch:

- **UptimeRobot** (free tier): pings `/healthz` every 5 minutes, emails on downtime
- **Sentry performance**: set `traces_sample_rate=0.2` to catch slow endpoints (especially LLM calls)
- **DB connection pool monitoring**: log pool exhaustion events (FastAPI `startup` event, check
  `asyncpg` pool stats)
- **R2 write failure monitoring**: `s3_put` failures should increment a Sentry counter

### What this is NOT about

This section is about **operational reliability after launch** — not about security hardening,
DPDP compliance monitoring, or rate limiting (which have their own ADRs pending). Those are separate
concerns.

### Suggested next steps

1. **Write `docs/specs/Unit_001_HcCoreCycle/SPEC-XXXX-observability-error-handling.md`** before P7 starts.
   Scope it to items 1–4 above (LLM resilience, Sentry, error boundaries, HC messaging). Items 5–6
   can be separate specs or folded into the P8/P9 pilot-gate phase.

2. **Add migration** for `llm_calls.status` and `llm_calls.error_detail` columns as part of P7.

3. **Decide alerting channel** before running the first real HC session. Even a single Sentry email
   alert rule takes 10 minutes to configure and means you know within minutes if something breaks.

4. **Do not build custom error dashboards**. Sentry provides everything needed at pilot scale.
   Custom dashboards are P9+ scope.

---

## Known issues / carry-overs into P7

1. **M000 onboarding UX gap**: After a client is created, the HC is not directed to the M000 session
   to fill in intake notes. The session exists in DB and the notes textarea is there — but there's no
   prompt. Fix: redirect to M000 session page after client creation, or add a "complete onboarding"
   banner on the client detail page. Low effort, high impact on brief quality for first real sessions.

2. **`{{SESSION_NOTES}}` dead placeholder in system prompt**: `mom_draft.md` has a `{{SESSION_NOTES}}`
   placeholder that is never substituted. Session notes travel via `user_message`. The LLM receives
   them correctly; the placeholder is dead template text. Clean up in a prompt maintenance pass.

3. **`user_message` not stored in DB**: `llm_calls.prompt_text` holds only the system prompt.
   The full conversation (HC notes + file content sent to LLM) is not persisted. Decision needed in
   P8: add `user_message_text BYTEA` column to `llm_calls`?

4. **R2 free tier: no India-region pinning**: Documented in ADR-0001. Acceptable at MVP scale.
   Revisit before pilot launch.

5. **No `PATCH /api/clients/{id}`**: Cannot update client fields post-creation. Needed before P9
   pilot gate.

6. **LLM has no timeout**: As detailed in §Production Error Handling above. Risk is low in dev
   (you can restart), high in production (hung worker blocks other HC requests).

7. **Google OAuth redirect URI**: Must add `http://localhost:8000/api/auth/google/callback` to
   Google Cloud Console Authorized Redirect URIs for local dev to work end-to-end. Production URL
   will need its own entry.

---

## Migrations (5 total, unchanged from P5)

| Revision | Label |
|---|---|
| `e8a1523b2f3a` | initial_schema — all 16 base tables |
| `60775f9338d3` | p3_schema_extensions |
| `95df31e31f5f` | p4_llm_service_schema — pgcrypto, llm_calls, clients.code |
| `bb542bec1c52` | p5_add_session_notes — sessions.session_notes |
| `df7c84b2de4f` | p5b_add_client_files — client_files table (17th table) |

No new migrations in P6. P7 should add `llm_calls.status` and `llm_calls.error_detail` (see §Production Error Handling).

---

## All API endpoints (unchanged from P5)

No new backend endpoints in P6. The frontend calls the same P1–P5 API surface.

See HANDOVER-P5.md §All API endpoints for the complete list.

---

## Patterns and rules (unchanged from P5, one addition)

All 17 rules from HANDOVER-P5 remain in force. Addition:

18. ★ **Email-upsert in `google_callback` is intentional** — the fallback to email lookup after
    `google_sub` miss is not a bug. It supports dev-seeded users claiming their real Google identity
    on first login. Do not remove it.

---

## Env vars (unchanged from P5)

```bash
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev
TEST_DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_test
JWT_PRIVATE_KEY=<ES256 PEM>
JWT_PUBLIC_KEY=<ES256 PEM>
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
API_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
OPENROUTER_API_KEY=<from openrouter.ai>
LLM_CALL_ENCRYPTION_KEY=<openssl rand -base64 32>
R2_ACCOUNT_ID=<32-char hex>
R2_ACCESS_KEY_ID=<32-char>
R2_SECRET_ACCESS_KEY=<64-char>
R2_BUCKET_NAME=<bucket name>
SENTRY_DSN=<from sentry.io>       # stubbed — not yet initialised
APP_ENV=dev
APP_VERSION=0.1.0
```

Frontend (`.env.local` in `frontend/`):
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Post-P6 developments (2026-05-07)

> This section documents changes that occurred after HANDOVER-P6 was initially written (commit `c5be324`).
> It extends §Known issues and §Current git state. Read this before §What P7 needs to build.

### Commits landed after initial HANDOVER-P6

| Commit | What changed |
|---|---|
| `617b18d` | Mock script fix: wrong table name `session_briefs` → `briefs` in `05_verify_flywheel.sh` |
| `af62526` | Added `frontend_feedback.md` — P6 UI review triage (5 items) |

### P6 UI review — `frontend_feedback.md`

A post-build UI review produced 5 items triaged as follows:

| # | Item | Label | Status |
|---|---|---|---|
| 1 | Dashboard section visual separation (background cards) | `P6-fix` | Coded, uncommitted |
| 2 | "Recent Clients" widget — keep or replace? | `P6B-spec` | Needs product brainstorm first |
| 3 | Today's session: show Client name + Session # | `P6-fix` | Coded, uncommitted |
| 4 | Open action items: checkboxes + section on client detail page | `P6-fix` | Coded, uncommitted |
| 5 | Diet chart feature (preview, AI gen, editable table) | `P6B-spec` | Needs product brainstorm first |

Items 2 and 5 are new carry-overs. They require product decisions + a spec before any code.
Item 5 (diet chart) may warrant its own unit (`Unit_002_DietCharts`) — defer naming until spec is written.
The DB tables (`diet_charts`, `diet_chart_recipes`, `prep_recipes`, `content_assignments`) already exist from P1.

### Uncommitted code changes (P6-fix items 1, 3, 4)

8 files modified, not yet committed:

| File | Change |
|---|---|
| `frontend/src/app/(app)/dashboard/page.tsx` | Section background cards; client name + session # in Today |
| `frontend/src/app/(app)/clients/[clientId]/page.tsx` | Open action items section above sessions list (+157 lines) |
| `frontend/src/app/(app)/action-items/page.tsx` | Checkbox accountability |
| `frontend/src/app/globals.css` | CSS cascade update |
| `frontend/src/styles/tokens.generated.css` | Regenerated from theme.yaml |
| `frontend/tests/unit/__snapshots__/theme-build.test.ts.snap` | Snapshot updated |
| `frontend/theme.yaml` | Design token additions |
| `scripts/build-theme.mjs` | Build script update |

**These must be committed before P7 starts.** Run `cd frontend && npx vitest run` first to confirm unit tests pass.

### Repo sync sweep — `docs/SYNC-2026-05-07.md`

A full sweep of all docs was done on 2026-05-07. Nine discrepancies between documentation and implementation were found:

| # | Where | What |
|---|---|---|
| D1 | SPEC-0001 §Stage 2 | Says `is_first_session=true` — column doesn't exist; code uses `session_number == 0` |
| D2 | SPEC-0001 §API surface | Shows `/mom/send` endpoint — doesn't exist; `PATCH /sessions/{id}/mom` handles send |
| D3 | REPO-INDEX.md | ADR-0003 listed as "Proposed" — it is Accepted |
| D4 | REPO-INDEX.md | References SPEC-0002-llm-service.md — file does not exist |
| D5 | ADR-0001 | Says Next.js 15 — actual is 16.2.4 |
| D6 | ADR-0001, ADR-0003 | Document 4 LLM models in chain — live chain has 3 (`gpt-oss-120b` removed in P4) |
| D7 | ADR-0004 | Repo layout doesn't match reality (`prompts/` location, `llm_service/` vs `llm/`) |
| D8 | PHASE-06-frontend.md | Status still "Draft"; §4/§6/§7/§8 unfilled |
| D9 | glossary.md | "MERGE-REQUIRED" banner never removed |

All are doc fixes — none block P7 code. Full detail in `docs/SYNC-2026-05-07.md`.

---

## What P7 needs to build

> Read `docs/build-plan.md` §Phase 7 for the authoritative acceptance criteria.
> Write `PHASE-07-*.md` before any code.

**P7 scope** (from build-plan.md): check-in flows, client-facing features, or the observability/
error-handling spec detailed in this document. Confirm the priority with SoJo before starting.

**Highest-priority carry-overs from this document**:
1. LLM timeout + retry (unblocks pilot reliability)
2. Sentry initialisation (unblocks maintainer visibility)
3. Frontend error boundaries + error reference codes (unblocks HC-to-maintainer troubleshooting)
4. M000 UX redirect after client creation (unblocks brief quality)

**Key source docs to read before P7**:

| Doc | Why |
|---|---|
| `docs/build-plan.md` | P7 acceptance criteria |
| `docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md` | What P6 built, patterns established |
| `docs/decisions/0001-stack-selection.md` | Stack constraints |
| `CLAUDE.md` | Operating contract — 9 non-negotiables, preflight checklist |
| This document §Production Error Handling | Brief for observability spec |

---

## Current git state

```
branch: main
last commit: af62526  docs: add frontend_feedback.md with P6 review triage
uncommitted:  8 frontend files (P6-fix items 1, 3, 4 — see §Post-P6 developments)
backend tests: 189 passing
frontend e2e:  40 passing
migrations:    5 applied (df7c84b2de4f is head)
phases complete: P0 ✅  P1 ✅  P2 ✅  P3 ✅  P4 ✅  P5 ✅  P6 ✅
phases pending:  P7, P8, P9
```
