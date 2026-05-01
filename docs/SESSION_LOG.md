# Session log

Append-only. Latest at top. Claude writes a new entry at the end of each substantial session.

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
