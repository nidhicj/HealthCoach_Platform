# Session log

Append-only. Latest at top. Claude writes a new entry at the end of each substantial session.

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

**P3 status**: implementation complete; awaiting SoJo manual verification.

**Pending / next session**:
- SoJo runs P3 VERIFICATION.md checks
- P4 begins only after manual verification passes

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
