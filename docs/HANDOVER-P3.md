# Handover: P0–P2 Complete → P3–P5 Context for Claude

> This document is a complete context transfer. Read it fully before writing any P3–P5 code.
> It replaces the need to read git history. Treat everything here as authoritative current state.

---

## What this product is

**Parivarthan** — a webapp for independent health coaches (HCs) in India. HCs use it to:
1. Onboard and manage clients
2. Run sessions with AI-assisted MOM (Minutes of Meeting) generation
3. Send action items to clients
4. Run between-session check-ins
5. Build a personalised AI style via snippet capture (HC edits to AI drafts)

**Current users**: coach only (prototype UI). Clients exist in the data model but have no UI yet.
**Geography**: India-first. DPDP Act 2023 applies (explicit consent, real deletion, India-region hosting).
**Stage**: production repo. Prototype learnings only — no code copied from prototype.

---

## Stack (locked, ADR-0001 Accepted)

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python 3.12), running on Cloudflare Python Workers |
| Database | PostgreSQL 16 via asyncpg + SQLAlchemy 2.0 async |
| Migrations | Alembic |
| Auth | Google OAuth 2.0 + PKCE → ES256 JWT (python-jose) + refresh token rotation |
| LLM | OpenRouter (Llama 3.3 primary, Gemma 3 / GPT-OSS / Nemotron fallbacks) |
| Frontend | Next.js 16, Tailwind, shadcn/ui (Node 22 required) |
| Package manager | uv (Python), npm (Node) |
| Tests | pytest-asyncio, session-scoped engine fixture |

**Important**: Cloudflare Python Workers run Pyodide (WebAssembly), NOT a normal Python process. `asyncpg` and `SQLAlchemy` are C-extension packages — they are NOT Pyodide-compatible. Per ADR-0002, DB-touching endpoints run on **DO Bangalore** (DigitalOcean), not on Workers. Workers handle routing only. This does NOT affect how you write FastAPI code — write normal async FastAPI, just know that `wrangler dev` cannot test DB endpoints locally (use `uvicorn` instead).

---

## Repo layout (current state)

```
parivarthan_platform/
├── .env.example                    # all env vars documented (no secrets)
├── .env                            # gitignored — copy from .env.example
├── docker-compose.yml              # local Postgres 16 on port 5432
├── CLAUDE.md                       # operating contract (read before coding)
├── CONTRIBUTING.md                 # dev commands
├── docs/
│   ├── SESSION_LOG.md              # session history (append-only)
│   ├── VERIFICATION.md             # manual verification checklists per phase
│   ├── build-plan.md               # P0–P9 acceptance criteria (source of truth)
│   ├── decisions/                  # ADRs 0001–0005 (all Accepted)
│   ├── diagrams/0002-data-model.md # ERD + walkthrough (primary data reference)
│   ├── domain/
│   │   ├── glossary.md             # HC, client, session, MOM, AST, snippet, etc.
│   │   ├── actors.md               # HC / client / (future) admin roles
│   │   └── compliance-india.md     # DPDP posture
│   └── specs/                      # feature specs (write spec BEFORE coding — CLAUDE.md rule 9)
│
└── backend/
    ├── pyproject.toml              # Python deps; dev group has pytest, ruff, mypy, uvicorn
    ├── alembic.ini
    ├── alembic/
    │   ├── env.py                  # async engine, reads DATABASE_URL from env
    │   └── versions/
    │       └── e8a1523b2f3a_initial_schema.py   # all 16 tables, single migration
    ├── src/
    │   ├── main.py                 # FastAPI app, CORS, request-id middleware, auth router registered
    │   ├── config.py               # pydantic-settings Settings; use get_settings() — NOT a module-level singleton
    │   ├── lib/
    │   │   └── http.py             # make_http_client() — ALL httpx usage must go through this
    │   ├── telemetry/
    │   │   ├── scrub.py            # scrub() — redact PII before logging
    │   │   ├── log.py              # get_logger() — structlog bound logger
    │   │   └── sentry.py          # Sentry init stub
    │   ├── db/
    │   │   ├── base.py             # DeclarativeBase
    │   │   ├── session.py          # get_db() async generator — use as FastAPI Depends
    │   │   └── models/             # 16 models in 6 files (see table below)
    │   └── auth/
    │       ├── jwt_utils.py        # create_access_token(), decode_access_token(), AuthError, TokenClaims
    │       ├── refresh.py          # issue_refresh_token(), rotate_refresh_token(), revoke_token()
    │       ├── oauth.py            # generate_pkce_pair(), build_authorization_url(), exchange_code_for_userinfo()
    │       ├── dependencies.py     # require_role(*roles), current_tenant() — FastAPI Depends
    │       └── router.py           # /api/auth/google/start, /google/callback, /refresh, /logout
    └── tests/
        ├── unit/
        │   ├── test_config.py
        │   ├── test_http.py
        │   ├── test_scrub.py
        │   └── test_jwt_utils.py
        └── integration/
            ├── conftest.py         # session-scoped engine (drop_all/create_all), function-scoped db session
            ├── test_health.py
            ├── test_models.py      # roundtrip + cascade-delete for all 16 tables
            └── test_auth.py        # refresh rotation, replay detection, logout, direct-revoke
```

---

## Database models (16 tables, 1 migration)

| File | Models |
|---|---|
| `models/users.py` | `User` |
| `models/clients.py` | `Client` |
| `models/sessions.py` | `Session` |
| `models/llm.py` | `LlmCall` |
| `models/coaching.py` | `Mom`, `Brief`, `ActionItem`, `CheckIn`, `HcStyleSnippet` |
| `models/compliance.py` | `Consent`, `AuditLog` |
| `models/auth.py` | `AuthRefreshToken` |
| `models/content.py` | `DietChart`, `PrepRecipe`, `DietChartRecipe`, `ContentAssignment` |

**Key model facts**:
- All PKs: `UUID` with `server_default=func.gen_random_uuid()`
- All timestamps: `TIMESTAMP(timezone=True)` — **never** `TIMESTAMPTZ` (not importable from sqlalchemy.dialects.postgresql)
- String column server defaults: use `server_default=text("'onboarding'")` + `default="onboarding"` — plain string `server_default="'onboarding'"` triple-quotes in `create_all()` DDL (known SQLAlchemy bug)
- Cascade deletes: `clients` → `sessions`, `moms`, `briefs`, `action_items`, `check_ins`, `hc_style_snippets`, `consent`; `users` → `auth_refresh_tokens`
- Partial index on `auth_refresh_tokens`: `WHERE revoked_at IS NULL` only — **never** include `NOW()` (volatile function, illegal in partial index predicates)

---

## Auth system (P2 complete)

**JWT claims** (ES256, 15-min TTL):
```json
{"iss": "https://api.parivarthan.com", "aud": "parivarthan-api",
 "sub": "<user_id>", "role": "hc|client", "hc_id": "<hc_user_id>",
 "jti": "<uuid>", "iat": 0, "nbf": 0, "exp": 0}
```

**Refresh tokens**: 64-char hex, stored as SHA256 hash. 30-day TTL. Rotation via `successor_id` chain.

**Replay detection**: if a token with `successor_id` set is presented again → `_revoke_all_for_user()` fires → all active tokens for that user revoked. Check order in `rotate_refresh_token()`: not-found → expired → **successor_id** (replay) → revoked_at (direct revoke). `successor_id` MUST be checked before `revoked_at` because rotation sets both.

**Protecting a route**:
```python
from typing import Annotated
from fastapi import Depends
from src.auth.dependencies import require_role, current_tenant
from src.auth.jwt_utils import TokenClaims

@router.get("/api/clients/")
async def list_clients(
    claims: Annotated[TokenClaims, Depends(require_role("hc"))],
    hc_id: Annotated[str, Depends(current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Filter ALL queries by hc_id — never return cross-tenant data
    ...
```

---

## Patterns and rules (non-negotiable)

1. **`get_settings()` not `settings`** — config uses `lru_cache`. Import and call `get_settings()`. Never import a module-level `settings` singleton (it doesn't exist).

2. **Absolute imports** — the entire codebase uses `from src.auth.jwt_utils import ...` not `from ..jwt_utils import ...`. Stay consistent.

3. **All httpx through factory** — `make_http_client()` from `src.lib.http`. Never instantiate `httpx.AsyncClient` directly in `src/` (workers-py #68 — User-Agent must be set). Verify: `grep -r "httpx.AsyncClient(" backend/src | grep -v lib/http.py` should be empty.

4. **`uv run` for everything** — `uv run pytest`, `uv run alembic`, `uv run uvicorn`. The `.venv` is a symlink to a shared env.

5. **`text()` for string server defaults** — `from sqlalchemy import text; server_default=text("'draft'")`.

6. **Migrations for every schema change** — `uv run alembic revision --autogenerate -m "description"` then review before applying.

7. **Tests for new logic** — TDD pattern: write failing test → implement → green. Tests run against `parivarthan_test` DB (separate from dev DB).

8. **Spec before code** — for anything beyond a one-liner, write the spec in `docs/specs/` first (CLAUDE.md rule 9). Get confirmation before coding.

9. **Tenant scoping** — every domain query MUST filter by `hc_id` from the JWT. Failure = data leak between coaches. Test explicitly.

10. **`server_default=func.now()` for timestamps** — not Python-side `datetime.now()`.

---

## Running the test suite

```bash
cd backend

# All 37 tests (unit + integration)
uv run pytest -v

# Unit only (fast, no DB)
uv run pytest tests/unit/ -v

# Integration only (needs Docker postgres running)
uv run pytest tests/integration/ -v

# Integration conftest: drops + recreates all tables on each test run
# DB: postgresql://postgres:localdevpassword@localhost:5432/parivarthan_test
```

**Current state: 37/37 passing.**

---

## Env vars (required for backend)

```bash
DATABASE_URL=postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev
TEST_DATABASE_URL=postgresql://postgres:localdevpassword@localhost:5432/parivarthan_test
JWT_PRIVATE_KEY=<ES256 PEM>   # generate: openssl ecparam -name prime256v1 -genkey -noout -out priv.pem
JWT_PUBLIC_KEY=<ES256 PEM>    # generate: openssl ec -in priv.pem -pubout -out pub.pem
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
API_BASE_URL=http://localhost:8000
OPENROUTER_API_KEY=<from openrouter.ai>
SENTRY_DSN=<from sentry.io>
APP_ENV=dev
APP_VERSION=0.1.0
```

Alembic needs `DATABASE_URL` passed explicitly:
```bash
DATABASE_URL=postgresql://postgres:... uv run alembic upgrade head
```

---

## What P3 needs to build

**Goal**: HC can manage clients, sessions, MOMs (manual text for now — no LLM yet), action items, check-ins. All routes scoped by JWT `hc_id`.

### Deliverables (from build-plan.md)
- CRUD routes: `clients`, `sessions`, `moms`, `briefs`, `action_items`, `check_ins`
- All routes under `require_role("hc")` + `current_tenant()` tenant scoping
- **Coach-reviewed gate**: `mom.status` ∈ {`draft`, `reviewed`, `sent`}; client-facing API only returns `status='sent'`
- Pagination on all list endpoints (cursor-based or page/limit)
- Pydantic request/response schemas per route

### P3 acceptance criteria (from build-plan.md)
- HC creates client → client visible in list; HC2 cannot see HC1's client (403/404, not data leak)
- HC creates session → session in list; cross-HC session access blocked
- HC creates MOM (`status='draft'`) → updates → sends (`status='sent'`)
- Client-facing MOM endpoint: `draft` → 404; `sent` → 200
- Action item created in session → appears in client's open items list
- List with 25+ items → first page + cursor returned

### Recommended file structure for P3
```
backend/src/
└── api/
    ├── __init__.py
    ├── clients.py      # /api/clients
    ├── sessions.py     # /api/sessions
    ├── moms.py         # /api/moms
    ├── action_items.py # /api/action-items
    └── check_ins.py    # /api/check-ins
```
Register each as an `APIRouter` in `src/main.py`.

### Write the P3 spec first
Create `docs/specs/0003-domain-crud.md` before coding. Reference:
- `docs/diagrams/0002-data-model.md` — for field names and relationships
- `docs/domain/glossary.md` — for terminology (MOM, AST, HC cycle, etc.)
- `docs/domain/actors.md` — for who can see what
- `docs/build-plan.md` Phase 3 section — for acceptance criteria

---

## What P4 needs to build (after P3)

**Goal**: LLM drafts work end-to-end. Snippet capture on HC edits. Telemetry on every call.

- `backend/src/llm_service/` module
- OpenRouter via `make_http_client()` with no-training/no-retention headers
- Model chain: Llama 3.3 70B → Gemma 3 → GPT-OSS → Nemotron (per ADR-0001/ADR-0003)
- Pydantic schemas for MOM, brief, action_items output
- Validation retry loop (1 retry on stricter format hint)
- Every LLM call writes one `llm_calls` row (all fields, success or failure)
- Prompt files in `prompts/` with YAML frontmatter (`version`, `created`, `notes`)
- Snippet capture: HC edit diff → `hc_style_snippets` row
- Snippet injection: top-N recent snippets ≤ 2K tokens injected into system prompt

---

## What P5 needs to build (after P4)

**Goal**: The actual product loop — pre-session brief, MOM workflow, action item lifecycle, triage flags.

- Pre-session brief: prior MOM + AST (open action items, recent status, trends) + snippets + recent check-ins → LLM → brief
- MOM workflow: session ends → draft → HC reviews → HC edits (snippet capture) → HC sends (status='sent', client visibility unlocked)
- Action item lifecycle: `open` → `in_progress` → `completed` / `missed`
- Triage flags: missed items, sentiment flags surface in next brief
- AST (Action/Status/Trends) computed at request time per client

---

## Key source docs to read before P3

| Doc | Why |
|---|---|
| `docs/diagrams/0002-data-model.md` | Field names, FK relationships, indexes |
| `docs/domain/glossary.md` | Product terminology — use exact terms from here in API design |
| `docs/domain/actors.md` | Who can read/write what |
| `docs/decisions/0005-auth-strategy.md` | JWT claims, tenant scoping rules |
| `docs/build-plan.md` Phase 3 | Acceptance criteria for P3 |
| `CLAUDE.md` | Operating contract — 9 non-negotiables, preflight checklist |

---

## Current git state

```
branch: main
last commit: docs: mark P2 verification complete
test count: 37 passing
phases complete: P0 ✅  P1 ✅  P2 ✅
phases pending: P3, P4, P5, P6, P7, P8, P9
```
