# Handover: P0–P4 Complete → P5 Context for Claude

> This document is a complete context transfer. Read it fully before writing any P5 code.
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
| Migrations | Alembic (2 migrations: `e8a1523b2f3a` initial, `95df31e31f5f` pgcrypto + llm columns) |
| Auth | Google OAuth 2.0 + PKCE → ES256 JWT (python-jose) + refresh token rotation |
| LLM | OpenRouter — 3-model chain: Llama 3.3 70B (primary) → Gemma 3 27B → Nemotron 120B |
| Frontend | Next.js 16, Tailwind, shadcn/ui (Node 22 required — not yet built) |
| Package manager | uv (Python), npm (Node) |
| Tests | pytest-asyncio, savepoint-based isolation (join_transaction_mode="create_savepoint") |

**Important — Cloudflare Workers constraint**: Workers run Pyodide (WebAssembly). `asyncpg` and `SQLAlchemy` are C-extension packages and are NOT Pyodide-compatible. Per ADR-0002, DB-touching endpoints run on **DO Bangalore** (DigitalOcean), not on Workers. Write normal async FastAPI. Use `uvicorn` for local dev — `wrangler dev` cannot test DB endpoints.

---

## Repo layout (current state)

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
│   │   ├── glossary.md             # HC, client, session, MOM, AST, snippet, etc.
│   │   ├── actors.md               # HC / client / (future) admin roles
│   │   └── compliance-india.md     # DPDP posture
│   └── specs/
│       └── Unit_001_HcCoreCycle/   # all phase plans and specs for the core cycle
│           ├── SPEC-0001-hc-core-cycle.md     # durable feature spec (HC cycle)
│           ├── PHASE-00-repo-scaffolding.md   # P0 implementation record
│           ├── PHASE-01-data-layer.md         # P1 implementation record
│           ├── PHASE-02-auth-service.md       # P2 implementation record
│           ├── PHASE-03-domain-crud.md        # P3 implementation record
│           └── PHASE-04-llm-service.md        # P4 implementation record ← read this
│
└── backend/
    ├── pyproject.toml              # Python deps; dev group has pytest, ruff, mypy, uvicorn
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py                  # async engine, reads DATABASE_URL from env
    │   └── versions/
    │       ├── e8a1523b2f3a_initial_schema.py       # all 16 tables
    │       └── 95df31e31f5f_p4_llm_service_schema.py # pgcrypto, llm_calls columns, clients.code
    ├── prompts/                    # versioned prompt files (YAML frontmatter + body)
    │   ├── mom_draft.md            # MOM generation — v1.0.0
    │   ├── brief_assemble.md       # pre-session brief — v1.0.0
    │   └── ai_assist.md            # generic assist — v1.0.0 (endpoint wired in P5)
    ├── src/
    │   ├── main.py                 # FastAPI app, CORS, request-id middleware, all routers registered
    │   ├── config.py               # pydantic-settings Settings; use get_settings() — NOT a module-level singleton
    │   ├── lib/
    │   │   └── http.py             # make_http_client() — ALL httpx usage must go through this
    │   ├── telemetry/
    │   │   ├── scrub.py            # scrub() — redact PII before logging; includes prompt_text, completion_text
    │   │   ├── log.py              # get_logger() — structlog bound logger
    │   │   └── sentry.py           # Sentry init stub
    │   ├── db/
    │   │   ├── base.py             # DeclarativeBase
    │   │   ├── session.py          # get_db() async generator — use as FastAPI Depends
    │   │   └── models/             # 16 models in 6 files (see §Database models)
    │   ├── auth/
    │   │   ├── jwt_utils.py        # create_access_token(), decode_access_token(), AuthError, TokenClaims
    │   │   ├── refresh.py          # issue_refresh_token(), rotate_refresh_token(), revoke_token()
    │   │   ├── oauth.py            # generate_pkce_pair(), build_authorization_url(), exchange_code_for_userinfo()
    │   │   ├── dependencies.py     # require_role(*roles), current_tenant() — FastAPI Depends
    │   │   └── router.py           # /api/auth/google/start, /callback, /refresh, /logout; client OAuth
    │   ├── api/
    │   │   ├── deps.py             # HcClaimsDep, ClientClaimsDep, TenantDep, DbDep, LimitDep, PaginatedList[T]
    │   │   ├── clients.py          # /api/clients CRUD + invite
    │   │   ├── sessions.py         # /api/sessions CRUD + MOM + brief + mom/draft
    │   │   ├── action_items.py     # /api/action-items
    │   │   ├── check_ins.py        # /api/check-ins (HC reads, flags)
    │   │   └── me.py               # /api/me — client-facing endpoints
    │   └── llm_service/            # ← new in P4 — the LLM integration layer
    │       ├── __init__.py         # generate_mom_draft(), generate_brief() — call these from API handlers
    │       ├── config.py           # LLMConfig dataclass, get_llm_config() (lru_cache)
    │       ├── llm_config.yaml     # model chain, snippet settings, validation_retry_count
    │       ├── prompts.py          # load_prompt() — YAML frontmatter parser, returns PromptFile
    │       ├── client.py           # call_openrouter() — httpx wrapper, returns OpenRouterResult
    │       ├── chain.py            # build_models_array(), fallback_count_for()
    │       ├── retry.py            # parse_or_retry() — 1 retry with STRICT_FORMAT_HINT
    │       ├── tracking.py         # write_llm_call() — inserts llm_calls row with pgp_sym_encrypt
    │       ├── snippets.py         # capture(), select(), update_usage()
    │       └── schemas/
    │           ├── mom.py          # MomDraftSchema (to_draft_text())
    │           ├── brief.py        # BriefSchema (to_brief_text(), triage_flags)
    │           └── action_items.py # ActionItemSchema
    └── tests/
        ├── unit/
        │   ├── test_config.py
        │   ├── test_http.py
        │   ├── test_scrub.py
        │   ├── test_scrub_extended.py       # prompt_text/completion_text scrubbed from logs
        │   ├── test_jwt_utils.py
        │   ├── test_llm_service_config.py   # LLMConfig loading, get_llm_config singleton
        │   └── test_llm_service_prompts.py  # load_prompt() frontmatter parsing, version field
        └── integration/
            ├── conftest.py                  # savepoint-based isolation; test JWT keys injected before imports
            ├── test_health.py
            ├── test_models.py               # roundtrip + cascade-delete for all 16 tables
            ├── test_auth.py                 # refresh rotation, replay detection, logout
            ├── test_client_auth.py          # client OAuth flow
            ├── test_clients.py
            ├── test_sessions.py
            ├── test_action_items.py
            ├── test_check_ins.py
            ├── test_me.py
            ├── test_llm_tracking.py         # write_llm_call happy + error path
            ├── test_llm_snippets.py         # capture gate, select pool + budget, update_usage
            └── test_mom_draft.py            # POST /mom/draft, re-draft, PATCH snippet capture
```

---

## Database models (16 tables, 2 migrations)

| File | Models |
|---|---|
| `models/users.py` | `User` |
| `models/clients.py` | `Client` — now has `code VARCHAR NOT NULL` (CP\<NNNN\> pseudonym, unique per HC) |
| `models/sessions.py` | `Session` — has `deleted_at` for soft-delete |
| `models/llm.py` | `LlmCall` — now has `prompt_text BYTEA`, `completion_text BYTEA`, `client_id FK` |
| `models/coaching.py` | `Mom`, `Brief`, `ActionItem`, `CheckIn`, `HcStyleSnippet` |
| `models/compliance.py` | `Consent`, `AuditLog` |
| `models/auth.py` | `AuthRefreshToken` |
| `models/content.py` | `DietChart`, `PrepRecipe`, `DietChartRecipe`, `ContentAssignment` |

**Key model facts**:
- All PKs: `UUID` with `server_default=func.gen_random_uuid()`
- All timestamps: `TIMESTAMP(timezone=True)` — **never** `TIMESTAMPTZ`
- String column server defaults: `server_default=text("'draft'")` + `default="draft"` — plain string triple-quotes in `create_all()` DDL (SQLAlchemy bug, fixed this way)
- `llm_calls.prompt_text` and `completion_text` are `BYTEA` — pgcrypto-encrypted. Read via `pgp_sym_decrypt(col, '<key>')` in psql; not readable as plain text
- `clients.code` is `CP<NNNN>` — set by `create_client()` via `MAX(CAST(SUBSTRING(code FROM 3) AS INTEGER)) + 1`. Used as PII-safe client identifier in prompts
- Cascade deletes: `clients` → `sessions`, `moms`, `briefs`, `action_items`, `check_ins`, `hc_style_snippets`, `consent`, `llm_calls`; `users` → `auth_refresh_tokens`

---

## Auth system (P2 complete)

**JWT claims** (ES256, 15-min TTL):
```json
{"iss": "https://api.parivarthan.com", "aud": "parivarthan-api",
 "sub": "<user_id>", "role": "hc|client", "hc_id": "<hc_user_id>",
 "jti": "<uuid>", "iat": 0, "nbf": 0, "exp": 0}
```

**Refresh tokens**: 64-char hex, stored as SHA256 hash. 30-day TTL. Rotation via `successor_id` chain. Replay detection: `successor_id` checked before `revoked_at` — both are set on rotation, so the order matters.

**Protecting a route**:
```python
from typing import Annotated
from src.api.deps import HcClaimsDep, TenantDep, DbDep

@router.get("/api/sessions/")
async def list_sessions(
    claims: HcClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
):
    # Filter ALL queries by hc_id — never return cross-tenant data
    ...
```

`deps.py` exports: `HcClaimsDep`, `ClientClaimsDep`, `TenantDep`, `DbDep`, `LimitDep`, `PaginatedList[T]`, `encode_cursor()`, `decode_cursor()`.

---

## LLM service (P4 complete)

The `llm_service/` module is the **only** place where LLM calls happen. No code outside it should call OpenRouter directly.

### Public API (call from API handlers)

```python
from src.llm_service import generate_mom_draft, generate_brief

# In POST /sessions/{id}/mom/draft handler:
draft_text, llm_call_id = await generate_mom_draft(
    db,
    session_id=session_id,
    hc_user_id=hc_user_id,
    client_id=client_id,
    session_notes=body.session_notes,
    request_id=request_id,
)

# In GET /sessions/{id}/brief handler:
brief_text, triage_flags, llm_call_id = await generate_brief(
    db,
    session_id=session_id,
    hc_user_id=hc_user_id,
    client_id=client_id,
    request_id=request_id,
)
```

Both functions raise `HTTPException(503)` on LLM failure and `HTTPException(422)` on persistent validation failure. They always write a `llm_calls` row before raising.

### Snippet system

**Capture** — called from `PATCH /sessions/{id}/mom` when all three are true:
1. `body.final_text` is provided
2. `mom.llm_call_id IS NOT NULL` (draft was AI-generated)
3. `final_text != mom.draft_text` (HC actually changed something)

```python
from src.llm_service.snippets import capture
await capture(db, mom=mom, final_text=body.final_text, hc_user_id=hc_user_id, client_id=client_id)
```

**Selection** — Option C hybrid: pool of 25 most-recent by `created_at DESC` → re-sort pool by `last_used_at ASC NULLS FIRST` (unused snippets surface first) → stop at 2K-token budget (`snippet_token_budget` in `llm_config.yaml`). Done automatically inside `generate_mom_draft()` and `generate_brief()`.

### Config (editable without code changes)

`backend/src/llm_service/llm_config.yaml` — restart app after editing:
```yaml
model_chain:
  - meta-llama/llama-3.3-70b-instruct:free   # primary
  - google/gemma-3-27b-it:free               # fallback 1
  - nvidia/nemotron-3-super-120b-a12b:free   # fallback 2
# Note: OpenRouter models array limit is 3 — do not add a 4th entry
reasoning_model: deepseek/deepseek-r1        # explicit-only, not in automatic chain
snippet_pool_size: 25
snippet_token_budget: 2000
validation_retry_count: 1
```

### Prompt files

`backend/prompts/<name>.md` — YAML frontmatter + Jinja-style placeholders:
```markdown
---
version: "1.0.0"
created: "2026-05-04"
notes: "Initial draft."
---
[prompt body with {{CLIENT_CODE}}, {{SNIPPET_SECTION}}, etc.]
```

Bump `version:` in the YAML to roll a new prompt version — change is visible in `llm_calls.prompt_version` on next call, no code change needed.

**Current prompt files**: `mom_draft.md`, `brief_assemble.md`, `ai_assist.md` (endpoint wired in P5).

### `llm_calls` row — what gets written

Every LLM call writes exactly one row (success or failure):

| Field | Notes |
|---|---|
| `use_case` | `'mom_generation'` or `'brief_generation'` |
| `model_requested` | `model_chain[0]` from config |
| `model_served` | actual model that responded; `null` on network error |
| `fallback_count` | chain index of `model_served`; `-1` if model not in chain |
| `prompt_version` | from prompt file YAML frontmatter |
| `input_tokens` / `output_tokens` | from OpenRouter response `usage` field |
| `latency_ms` | wall time from HTTP call start to row write |
| `validation_failed` | `true` if Pydantic validation failed even after retry |
| `snippet_count` / `snippet_tokens` | number and token count of injected snippets |
| `prompt_text` | BYTEA — `pgp_sym_encrypt(system_prompt, key)` — `null` on pre-call error |
| `completion_text` | BYTEA — `pgp_sym_encrypt(raw_llm_response, key)` — `null` on pre-call error |
| `client_id` | FK to `clients` (CASCADE DELETE) |
| `request_id` | from FastAPI request state |

To decrypt for debugging:
```sql
SELECT pgp_sym_decrypt(prompt_text, '<LLM_CALL_ENCRYPTION_KEY>') FROM llm_calls WHERE id = '...';
```

---

## All API endpoints (current state after P4)

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/healthz` | — | Health check |
| GET | `/api/auth/google/start` | — | Initiate HC Google OAuth |
| GET | `/api/auth/google/callback` | — | HC OAuth callback → JWT + refresh cookie |
| GET | `/api/auth/client/start` | — | Client Google OAuth via invite token |
| GET | `/api/auth/client/callback` | — | Client OAuth callback → JWT + refresh cookie |
| POST | `/api/auth/refresh` | — | Rotate refresh token |
| POST | `/api/auth/logout` | HC/client | Revoke current refresh token |
| GET | `/api/clients/` | HC | List clients (cursor paginated) |
| POST | `/api/clients/` | HC | Create client (assigns CP\<NNNN\> code) |
| GET | `/api/clients/{id}` | HC | Get client |
| POST | `/api/clients/{id}/invite` | HC | Issue invite token (invalidates prior unused) |
| GET | `/api/sessions/` | HC | List sessions |
| POST | `/api/sessions/` | HC | Create session |
| GET | `/api/sessions/{id}` | HC | Get session |
| POST | `/api/sessions/{id}/end` | HC | End session (idempotent) |
| POST | `/api/sessions/{id}/mom` | HC | Create MOM (manual draft_text) |
| GET | `/api/sessions/{id}/mom` | HC | Get MOM |
| PATCH | `/api/sessions/{id}/mom` | HC | Update MOM; snippet capture gate fires on AI-drafted MOMs |
| POST | `/api/sessions/{id}/mom/send` | HC | Send MOM (status → 'sent', client visibility unlocked) |
| POST | `/api/sessions/{id}/mom/draft` | HC | **P4** — Generate AI MOM draft via LLM service |
| GET | `/api/sessions/{id}/brief` | HC | **P4** — Generate (or return cached) pre-session brief |
| GET | `/api/action-items/` | HC | List action items (filterable by client/status) |
| POST | `/api/action-items/` | HC | Create action item |
| GET | `/api/action-items/{id}` | HC | Get action item |
| PATCH | `/api/action-items/{id}` | HC | Update status / description |
| GET | `/api/check-ins/` | HC | List check-ins (filterable by client) |
| PATCH | `/api/check-ins/{id}/flag` | HC | Set/clear sentiment_flag |
| POST | `/api/me/check-ins` | client | Submit a check-in |
| GET | `/api/me/moms` | client | List sent MOMs |
| GET | `/api/me/moms/{id}` | client | Get a sent MOM |
| GET | `/api/me/action-items` | client | List own action items |
| PATCH | `/api/me/action-items/{id}` | client | Mark own item complete/in_progress |

---

## Patterns and rules (non-negotiable)

1. **`get_settings()` not `settings`** — `lru_cache`. Never import a module-level `settings` singleton.

2. **Absolute imports** — `from src.auth.jwt_utils import ...` not `from ..jwt_utils import ...`. Consistent throughout.

3. **All httpx through factory** — `make_http_client()` from `src.lib.http`. Never `httpx.AsyncClient()` directly in `src/`. Verify: `grep -r "httpx.AsyncClient(" backend/src | grep -v lib/http.py` should be empty. **Also**: pass `timeout=120.0` when calling LLM endpoints — free models take 30–60 s.

4. **All LLM calls through `llm_service/`** — `generate_mom_draft()` and `generate_brief()` are the only entry points. New use cases get a new orchestration function in `llm_service/__init__.py`; they do not call `call_openrouter()` directly from the API layer.

5. **`uv run` for everything** — `uv run pytest`, `uv run alembic`, `uv run uvicorn`.

6. **Activate the shared venv** — `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate` (or use `uv run` which picks it up). The `backend/.venv` is a symlink to this path.

7. **`text()` for string server defaults** — `from sqlalchemy import text; server_default=text("'draft'")`.

8. **Migrations for every schema change** — `uv run alembic revision --autogenerate -m "description"`, review before applying.

9. **Tests for new logic** — session-scoped engine (drop_all/create_all per test session), savepoint-based function-level isolation (`join_transaction_mode="create_savepoint"`). DB: `parivarthan_test`.

10. **Write PHASE file first** — for any build phase, create `docs/specs/Unit_001_HcCoreCycle/PHASE-NN-kebab-title.md` using `docs/specs/template-phase-plan.md` and get SoJo's confirmation **before** writing code (CLAUDE.md §6 rule).

11. **Tenant scoping** — every domain query MUST filter by `hc_id` from JWT. Cross-tenant responses are always 404 (never 403 — prevents existence leakage).

12. **CP\<NNNN\> in prompts, never PII** — use `client.code` as the client identifier in any prompt. Never inject `client.full_name`, email, or phone.

13. **Model slugs only in YAML** — verify: `grep -rn "llama-3.3\|gemma-3\|nemotron" backend/src --include="*.py"` should be empty.

14. **`repr(exc)` not `str(exc)` in `detail=`** — `str()` returns empty strings for some exception types. `repr()` always includes the class name and args.

---

## Running the test suite

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate

# All 144 tests (unit + integration)
PYTHONPATH=. pytest -v

# Unit only (fast, no DB)
PYTHONPATH=. pytest tests/unit/ -v

# Integration only (needs Docker postgres running)
PYTHONPATH=. pytest tests/integration/ -v
```

**Current state: 144/144 passing.**

Integration conftest: drops + recreates all tables per test session. Uses savepoint-based isolation per test function — no explicit transaction rollback needed in tests. Test JWT keys injected via `monkeypatch` before `src` imports.

---

## Env vars (all required for backend)

```bash
# Postgres
DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev
TEST_DATABASE_URL=postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_test

# Auth
JWT_PRIVATE_KEY=<ES256 PEM>   # openssl ecparam -name prime256v1 -genkey -noout -out priv.pem
JWT_PUBLIC_KEY=<ES256 PEM>    # openssl ec -in priv.pem -pubout -out pub.pem
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
API_BASE_URL=http://localhost:8000

# LLM
OPENROUTER_API_KEY=<from openrouter.ai>
LLM_CALL_ENCRYPTION_KEY=<openssl rand -base64 32>   # encrypts prompt_text/completion_text in llm_calls

# Observability
SENTRY_DSN=<from sentry.io>
APP_ENV=dev
APP_VERSION=0.1.0
```

Alembic needs `DATABASE_URL` explicit:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:... uv run alembic upgrade head
```

HC user for manual testing:
```bash
cd backend
PYTHONPATH=. python3 scripts/create_hc_user.py
# prints: export HC_JWT=... export HC_ID=...
```

---

## What P5 needs to build

**Goal**: the actual product loop — pre-session brief workflow, full MOM lifecycle, action item lifecycle, triage flags surfacing in the next brief, AST (Action/Status/Trends) view.

**Before writing any code**: write `docs/specs/Unit_001_HcCoreCycle/PHASE-05-hc-cycle-workflows.md` using `docs/specs/template-phase-plan.md`. Get SoJo's confirmation. Then implement.

### Deliverables (from `docs/build-plan.md` Phase 5)

- **Pre-session brief workflow**: the LLM service already generates the brief; P5 wires it into the HC cycle so the brief automatically pulls prior MOM + AST + recent check-ins + snippets. `generate_brief()` in `llm_service/__init__.py` already assembles this — verify the inputs are correct.
- **`ai_assist.md` endpoint**: `POST /api/sessions/{id}/ai-assist` — generic in-session assist. Prompt file already exists at `backend/prompts/ai_assist.md`.
- **MOM workflow**: session ends → MOM draft auto-generated (or HC triggers manually) → HC reviews → HC edits (snippet capture already wired) → HC sends (`status='sent'`, client visibility unlocks)
- **Action item lifecycle**: states `open` → `in_progress` → `completed` / `missed`; transitions recorded
- **Triage flag aggregation**: missed items, sentiment flags, recency-based concerns surface in next brief's `triage_flags` (the `BriefSchema.triage_flags` field is already populated by `generate_brief()`)
- **AST view** (Action/Status/Trends): computed per client at request time — open items count, last MOM summary, trend tags
- **Sentiment flag stub**: manual tagging only at MVP (per ADR-0003 deferral — auto-detection deferred)
- **M000 flow**: first session with empty AST + empty snippets — no error, graceful "first session" state

### P5 acceptance criteria (from build-plan.md)

- End-to-end M00N session: HC starts session → brief generated → session conducted → MOM drafted → HC edits → HC sends
- Brief includes: 1+ snippet (if available), open action items count, last MOM summary, recent check-in summary
- Action items from sent MOM appear in next brief's AST as `open`
- Action item not completed by next session → flagged in `triage_flags` of next brief
- Coach-reviewed gate holds: client cannot view brief content (briefs are HC-internal)
- AST endpoint returns structured response: open items list, status summary, trend tags
- M000 flow: first session has empty AST and empty snippets — no errors

---

## Key source docs to read before P5

| Doc | Why |
|---|---|
| `docs/specs/Unit_001_HcCoreCycle/PHASE-04-llm-service.md` | What P4 built, decisions, carry-over patterns |
| `docs/specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` | Durable feature spec — acceptance criteria P5 implements |
| `docs/diagrams/0002-data-model.md` | `moms`, `briefs`, `action_items`, `check_ins` schemas |
| `docs/domain/glossary.md` | HC cycle, AST, triage flag, snippet terminology |
| `docs/domain/actors.md` | Who can read/write what |
| `docs/decisions/0003-llm-strategy.md` | LLM strategy, snippet design, what's deferred |
| `docs/build-plan.md` Phase 5 | Acceptance criteria for P5 |
| `CLAUDE.md` | Operating contract — 9 non-negotiables, preflight checklist |

---

## Current git state

```
branch: main
last commit: 5bc810b  docs: write PHASE-04 retroactively and lock in PHASE-file convention
test count: 144 passing
phases complete: P0 ✅  P1 ✅  P2 ✅  P3 ✅  P4 ✅
phases pending: P5, P6, P7, P8, P9
```

**Naming convention (locked)**:
- Specs: `docs/specs/Unit_NNN_PascalCaseName/SPEC-NNNN-kebab-title.md`
- Phase plans: `docs/specs/Unit_NNN_PascalCaseName/PHASE-NN-kebab-title.md`
- ADRs, diagrams, domain docs: flat in their existing folders — no per-unit subfolders
- Every future phase starts with a PHASE file written and confirmed before any code is touched
