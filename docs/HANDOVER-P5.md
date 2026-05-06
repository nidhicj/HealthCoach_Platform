# Handover: P0–P5 Complete → P6 Context for Claude

> This document is a complete context transfer. Read it fully before writing any P6 code.
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
| Object storage | **Cloudflare R2** (free tier — 10 GB / 1 M writes / 10 M reads / zero egress). S3-compatible Sig V4. |
| Frontend | Next.js 15 App Router, Tailwind, shadcn/ui (Node 22 required — **P6 builds this**) |
| Package manager | uv (Python), npm (Node) |
| Tests | pytest-asyncio, savepoint-based isolation (`join_transaction_mode="create_savepoint"`) |

**Important — Cloudflare Workers constraint**: Workers run Pyodide (WebAssembly). `asyncpg` and `SQLAlchemy` are C-extension packages and are NOT Pyodide-compatible. Per ADR-0002, DB-touching endpoints run on **DO Bangalore** (DigitalOcean), not on Workers. Write normal async FastAPI. Use `uvicorn` for local dev.

**R2 note**: R2 free tier does not support India-region pinning. Accepted at MVP scale under DPDP negative-list regime. Revisit before pilot launch. See ADR-0001 changelog 2026-05-06.

---

## Repo layout (current state after P5)

```
parivarthan_platform/
├── .env.example                    # all env vars documented (no secrets)
├── .env                            # gitignored — copy from .env.example
├── docker-compose.yml              # local Postgres 16 on port 5432
├── CLAUDE.md                       # operating contract — read before coding
├── CONTRIBUTING.md                 # dev commands
├── docs/
│   ├── SESSION_LOG.md              # session history (append-only)
│   ├── VERIFICATION.md             # manual verification checklists per phase
│   ├── build-plan.md               # P0–P9 acceptance criteria (source of truth)
│   ├── decisions/                  # ADRs 0001–0006 (all Accepted)
│   ├── diagrams/0002-data-model.md # ERD + walkthrough (primary data reference)
│   ├── domain/
│   │   ├── glossary.md             # HC, client, session, MOM, AST, snippet, client_files, etc.
│   │   ├── actors.md               # HC / client / (future) admin roles
│   │   └── compliance-india.md     # DPDP posture
│   └── specs/
│       └── Unit_001_HcCoreCycle/
│           ├── SPEC-0001-hc-core-cycle.md
│           ├── PHASE-00 through PHASE-05 ← all written and complete
│
└── backend/
    ├── pyproject.toml
    ├── alembic.ini
    ├── alembic/versions/
    │   ├── e8a1523b2f3a_initial_schema.py
    │   ├── 60775f9338d3_p3_schema_extensions.py
    │   ├── 95df31e31f5f_p4_llm_service_schema.py
    │   ├── bb542bec1c52_p5_add_session_notes.py      ← P5 Part A
    │   └── df7c84b2de4f_p5b_add_client_files.py      ← P5 Part B
    ├── prompts/                    # versioned prompt files (YAML frontmatter + body)
    │   ├── mom_draft.md            # MOM generation — v1.0.0
    │   ├── brief_assemble.md       # pre-session brief — v1.0.0
    │   └── ai_assist.md            # generic assist — v1.0.0
    ├── scripts/
    │   ├── create_hc_user.py       # creates test HC user, prints JWT + HC_ID
    │   └── check_r2_creds.py       # R2 credential diagnostic (PUT/GET/DELETE smoke test)
    └── src/
        ├── main.py
        ├── config.py               # Settings — r2_account_id, r2_access_key_id, r2_secret_access_key, r2_bucket_name
        ├── lib/
        │   ├── http.py             # make_http_client() — ALL httpx usage goes through this
        │   ├── s3.py               # R2 client: s3_put, s3_get, s3_delete, s3_exists, build_session_file_key
        │   └── file_extraction.py  # extract_text(content, mime_type) → str; handles txt, md, pdf, docx
        ├── api/
        │   ├── deps.py
        │   ├── clients.py          # code field now exposed in ClientOut
        │   ├── sessions.py         # session_notes column + R2 mirror; Zoom snippet gate in patch_mom
        │   ├── files.py            # POST/GET/DELETE /api/sessions/{id}/files
        │   ├── action_items.py
        │   ├── check_ins.py
        │   └── me.py
        └── llm_service/
            ├── __init__.py         # generate_mom_draft(), generate_brief() — file content injected here
            ├── config.py           # LLMConfig — includes file_content_max_tokens_per_file, file_content_max_total_tokens
            ├── llm_config.yaml
            └── [rest unchanged from P4]
```

---

## Migrations (5 total, all applied)

| Revision | Label | Key changes |
|---|---|---|
| `e8a1523b2f3a` | initial_schema | All 16 base tables |
| `60775f9338d3` | p3_schema_extensions | P3 additions |
| `95df31e31f5f` | p4_llm_service_schema | pgcrypto, llm_calls columns, clients.code |
| `bb542bec1c52` | p5_add_session_notes | `sessions.session_notes TEXT` column |
| `df7c84b2de4f` | p5b_add_client_files | `client_files` table (17th table) |

---

## Database models (17 tables)

All from P4 remain unchanged. P5 adds:

**`sessions.session_notes`** — `TEXT NULL`. HC's typed notes for the session. Persisted to DB (canonical). Also mirrored to R2 as `session_notes.txt` on every PATCH save (R2 copy is read-only reference; DB column is truth).

**`ClientFile`** (`client_files` table):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `session_id` | UUID FK → sessions | CASCADE DELETE |
| `hc_user_id` | UUID FK → users | tenant scope |
| `client_id` | UUID FK → clients | CASCADE DELETE |
| `original_filename` | TEXT | as uploaded |
| `storage_path` | TEXT | bare R2 key — write-once |
| `mime_type` | TEXT | validated on upload |
| `size_bytes` | INTEGER | |
| `uploaded_at` | TIMESTAMP(tz) | server_default now() |
| `is_zoom_summary` | BOOLEAN | auto-set if filename starts with `zoom_ai_summary_` |

Indexes: `idx_client_files_session`, `idx_client_files_hc`, `idx_client_files_client`.

---

## R2 object storage (new in P5)

**Client**: `src/lib/s3.py` — Sig V4 signing, no boto3 (Pyodide-incompatible).

**Key structure**:
```
hc-{hc_user_id}/client_session_library/{CP####}_{sanitized_name}/{YYYY-MM-DD}_session-{NN:02d}/{filename}
```

**Public functions**:
- `s3_put(key, content, content_type)` — upload
- `s3_get(key) → bytes` — download
- `s3_delete(key)` — delete (best-effort; DB row deletion is canonical)
- `s3_exists(key) → bool` — HEAD check
- `build_session_file_key(hc_user_id, client_code, client_full_name, session_date, session_number, filename) → str`

**Critical bug fixed**: original code added `Content-Type` header twice (once via `extra_headers` in signing, once explicitly after). httpx merged them into `text/plain, text/plain` causing `SignatureDoesNotMatch` 403. Fixed by removing the explicit post-signing assignment in `s3_put`.

**R2 env vars** (all required):
```bash
R2_ACCOUNT_ID=<32-char hex from Cloudflare dashboard → R2 → Overview>
R2_ACCESS_KEY_ID=<32-char from R2 → Manage R2 API Tokens>
R2_SECRET_ACCESS_KEY=<64-char secret — only shown once at token creation>
R2_BUCKET_NAME=<bucket name>
```

Run `python scripts/check_r2_creds.py` from `backend/` to verify credentials before debugging upload errors.

---

## File upload endpoints (new in P5)

| Method | Path | Notes |
|---|---|---|
| POST | `/api/sessions/{id}/files` | multipart; validates MIME + size (25 MB cap); auto-detects Zoom filenames |
| GET | `/api/sessions/{id}/files` | lists all files for session |
| DELETE | `/api/sessions/{id}/files/{file_id}` | removes DB row + best-effort R2 delete; 204 always if DB succeeds |

**Supported MIME types**: `text/plain`, `text/markdown`, `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.

**Zoom auto-detection**: filename starting with `zoom_ai_summary_` → `is_zoom_summary=True` automatically.

**client.code required**: file upload returns 422 if `client.code IS NULL`. All clients created via `POST /api/clients` get code auto-assigned (CP0001, CP0002, …).

---

## File content in LLM prompts (new in P5)

`_assemble_file_content_section(db, session_id, config)` in `src/llm_service/__init__.py`:

- Fetches all `ClientFile` rows for the session (including Zoom summaries)
- Downloads each from R2 via `s3_get`, extracts text via `extract_text(content, mime_type)`
- Per-file token budget: `file_content_max_tokens_per_file: 5000` (≈ 20 000 chars)
- Aggregate budget: `file_content_max_total_tokens: 15000`
- Truncation markers: `[... truncated, file too long ...]` and `[... total file budget exceeded ...]`
- Skips files that fail to fetch or extract (silent `except Exception: continue`)
- Returns `(section_str, has_files: bool)`

**User message structure** sent to LLM (NOT stored in DB — `prompt_text` stores system prompt only):
```
## HC's typed notes:
{session_notes}

## Uploaded files:
### filename.txt
{content}
```

**Zoom snippet gate**: `patch_mom` checks if any `is_zoom_summary=True` file exists for the session. If yes, snippet capture is suppressed (Zoom AI summaries are HC-external content, not HC voice).

---

## Patterns and rules (non-negotiable — unchanged from P4, additions marked ★)

1. **`get_settings()` not `settings`** — `lru_cache`. Never import a module-level singleton.
2. **Absolute imports** — `from src.auth.jwt_utils import ...` not `from ..jwt_utils import ...`.
3. **All httpx through factory** — `make_http_client()` from `src.lib.http`. Never `httpx.AsyncClient()` directly in `src/`.
4. **All LLM calls through `llm_service/`** — `generate_mom_draft()` and `generate_brief()` only entry points.
5. **`uv run` for everything** — `uv run pytest`, `uv run alembic`, `uv run uvicorn`.
6. **Activate the shared venv** — `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate`. `backend/.venv` symlinks here.
7. **`text()` for string server defaults** — `server_default=text("'draft'")`.
8. **Migrations for every schema change** — `alembic revision --autogenerate -m "..."`, review before applying.
9. **Tests for new logic** — savepoint isolation, `parivarthan_test` DB.
10. **Write PHASE file first** — `docs/specs/Unit_001_HcCoreCycle/PHASE-NN-kebab-title.md` confirmed before any code.
11. **Tenant scoping** — every domain query filters by `hc_id`. Cross-tenant = 404, never 403.
12. **CP\<NNNN\> in prompts, never PII** — `client.code` only. Never `client.full_name`, email, phone.
13. **Model slugs only in YAML** — not in `.py` files.
14. **`repr(exc)` not `str(exc)` in `detail=`**.
15. ★ **No duplicate headers in R2 requests** — `extra_headers` in `_build_auth_header` covers content-type for PUT; do not set `Content-Type` again after signing.
16. ★ **`_get_owned_session` is canonical** — import from `src.api.sessions`, do not copy. It includes `deleted_at.is_(None)`.
17. ★ **BoundLogger** — use `.warn()` not `.warning()`; flat kwargs not `extra={...}` dict.

---

## All API endpoints (current state after P5)

Everything from P4, plus:

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/api/clients/{id}` | HC | Now returns `code` field (was missing from ClientOut) |
| PATCH | `/api/sessions/{id}` | HC | Now persists `session_notes`; mirrors to R2 as `session_notes.txt` |
| POST | `/api/sessions/{id}/files` | HC | Upload files (multipart); validates MIME + size |
| GET | `/api/sessions/{id}/files` | HC | List uploaded files |
| DELETE | `/api/sessions/{id}/files/{file_id}` | HC | Delete file (DB row + best-effort R2) |

---

## Test suite (189 tests, all passing)

New in P5:

| File | Count | What it covers |
|---|---|---|
| `test_session_notes_mirror.py` | 3 | session_notes persists, R2 mirror fires, idempotent |
| `test_file_upload.py` | 8 | upload, list, delete, 25 MB cap, MIME validation, cross-tenant 404, S3 resilience, Zoom auto-detect |
| `test_file_prompt_injection.py` | 5 | typed notes in prompt, no-files path, per-file truncation, Zoom file included, aggregate budget |
| `test_zoom_snippet_exclusion.py` | 3 | Zoom file suppresses snippet capture |
| `test_s3_client.py` | 5 | key builder, `_sanitize`, `s3_put` signing, `s3_delete` signing |

Run:
```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
python -m pytest tests/ -q
# Expected: 189 passed
```

---

## Known issues / carry-overs

1. **`{{SESSION_NOTES}}` placeholder in system prompt not replaced** — `mom_draft.md` has a `{{SESSION_NOTES}}` placeholder in the system prompt body that is never substituted. Session notes travel via `user_message` instead. The LLM receives them correctly; the system prompt placeholder is dead template text. Clean up in P6 or a dedicated prompt cleanup pass.

2. **`user_message` not stored in DB** — `llm_calls.prompt_text` holds only the system prompt (pgcrypto-encrypted). The user message (HC notes + file content) is passed to the LLM but not persisted. Observability gap: you cannot reconstruct the full conversation from the DB. Decide in P8 whether to add a `user_message_text BYTEA` column.

3. **R2 free tier: no India-region pinning** — documented in ADR-0001. Acceptable at MVP scale. Revisit before pilot launch.

4. **No PATCH `/api/clients/{id}`** — client code is auto-assigned on creation. There is no endpoint to update client fields (name, email, phone, journey_stage). Needed before P9 pilot gate if HCs need to correct client data.

---

## Env vars (all required)

```bash
# Postgres
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev
TEST_DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_test

# Auth
JWT_PRIVATE_KEY=<ES256 PEM>
JWT_PUBLIC_KEY=<ES256 PEM>
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
API_BASE_URL=http://localhost:8000

# LLM
OPENROUTER_API_KEY=<from openrouter.ai>
LLM_CALL_ENCRYPTION_KEY=<openssl rand -base64 32>

# Cloudflare R2
R2_ACCOUNT_ID=<32-char hex — Cloudflare dashboard → R2 → Overview>
R2_ACCESS_KEY_ID=<from R2 → Manage R2 API Tokens>
R2_SECRET_ACCESS_KEY=<64-char — only shown once at token creation>
R2_BUCKET_NAME=<bucket name>

# Observability
SENTRY_DSN=<from sentry.io>
APP_ENV=dev
APP_VERSION=0.1.0
```

HC user for manual testing:
```bash
cd backend
python scripts/create_hc_user.py
# prints: export HC_JWT=... export HC_ID=...
```

R2 credential check:
```bash
cd backend
python scripts/check_r2_creds.py
# Runs PUT / GET / DELETE smoke test — all steps must pass before app will work
```

---

## What P6 needs to build

**Goal**: HC can do the entire core cycle through the browser.

**Before writing any code**: write `docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md` using `docs/specs/template-phase-plan.md`. Get SoJo's confirmation. Only then start implementation.

**Deliverables** (from `docs/build-plan.md` Phase 6):

- Next.js 15 App Router structure (repo layout per ADR-0004)
- Sign-in screen (Google OAuth redirect)
- HC dashboard: today's sessions, recent clients, pending action items
- Client list + client detail (history, current AST)
- Session view: pre-session brief, in-session notes area (textarea → `session_notes`), post-session MOM editor
- MOM editor: shows AI draft, allows edit, "Send" button → `status='sent'`
- File upload UI: per session, supports txt/md/pdf/docx, 25 MB cap, shows uploaded files list
- Action items view (per client + cross-client)
- Sign out, session list
- Tailwind + shadcn/ui per ADR-0001

**Acceptance criteria** (from build-plan.md):
- [ ] HC signs in → lands on dashboard
- [ ] Click into a session → see brief → run a mock session → MOM draft appears
- [ ] Edit MOM → click Send → MOM status updates to `sent`
- [ ] After send, query DB: new row in `hc_style_snippets` reflects the edit
- [ ] Click into a client → see their AST, history
- [ ] Sign out → redirected to sign-in; refresh cookie cleared
- [ ] Mobile viewport (Chrome devtools at 375px wide) is usable, not broken

**Key source docs to read before P6**:

| Doc | Why |
|---|---|
| `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md` | What P5 built, patterns established |
| `docs/decisions/0001-stack-selection.md` | Frontend stack (Next.js 15, Tailwind, shadcn/ui) |
| `docs/decisions/0004-repo-structure.md` | Frontend folder layout |
| `docs/domain/glossary.md` | UI terminology |
| `docs/diagrams/0002-data-model.md` | Data model for all entities the UI touches |
| `CLAUDE.md` | Operating contract — 9 non-negotiables, preflight checklist |

---

## Current git state

```
branch: main
last commit: f2ea921  fix: remove duplicate content-type in s3_put; correct verification step 8
test count: 189 passing
migrations: 5 applied (df7c84b2de4f is head)
phases complete: P0 ✅  P1 ✅  P2 ✅  P3 ✅  P4 ✅  P5 ✅
phases pending: P6, P7, P8, P9
```
