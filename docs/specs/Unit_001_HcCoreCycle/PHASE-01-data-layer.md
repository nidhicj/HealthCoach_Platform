# PHASE-01: Data Layer

**Unit**: Unit_001_HcCoreCycle
**Status**: Complete | Verified
**Verification date**: 2026-05-01 (see `docs/VERIFICATION.md` § P1 — Data Layer)
**Implements**: Pre-condition for all SPEC-0001 phases — every entity the HC core cycle reads and writes must exist before any API or auth work begins
**ADRs implemented**: ADR-0001 (stack: SQLAlchemy 2.0, asyncpg, Alembic), ADR-0003 (llm_calls schema), ADR-0005 (auth_refresh_tokens schema), ADR-0006 (observability: no sync DB calls)

---

## 1. Scope

Phase 1 created every database table the platform will ever use, using SQLAlchemy 2.0 async models and a single Alembic migration. The goal was: all 16 tables present, Alembic roundtrip clean (upgrade/downgrade), cascade-delete verified, async-only DB access enforced, integration tests passing. No API endpoints — just the data substrate.

P1 ran in the same session as P0 and P2 on 2026-05-01 (`prompts/starter_prompt_01.md`).

## 2. Deliverables shipped

Drawn from SESSION_LOG 2026-05-01.

- **16-table SQLAlchemy 2.0 model files** — organized into 6 domain files under `backend/src/db/models/`:
  - `users.py` — `users` table (id UUID, email, role, google_sub, created_at)
  - `clients.py` — `clients` table (hc_user_id FK, user_id nullable FK, full_name, code CP<NNNN>, journey_stage, created_at)
  - `sessions.py` — `sessions` table (client_id FK, session_number, scheduled_at, ended_at, deleted_at)
  - `moms.py` / `briefs.py` — `moms` and `briefs` tables (session_id FK, llm_call_id deferred FK, draft_text, final_text, status, sent_at)
  - `action_items.py` — `action_items` table (session_id FK, client_id FK, description, status, completed_at)
  - `check_ins.py` — `check_ins` table (client_id FK, hc_user_id FK, content, sentiment_flag, created_at)
  - `consents.py` — `consents` table (client_id FK, purpose, granted_at, revoked_at)
  - `diet_charts.py`, `prep_recipes.py`, `diet_chart_recipes.py`, `content_assignments.py` — future content features; tables created now, used post-MVP
  - `hc_style_snippets.py` — snippet_type, original_text, hc_modified_text, client_id FK, hc_user_id FK, last_used_at, retired_at
  - `llm_calls.py` — use_case, model_requested, model_served, prompt_version, input_tokens, output_tokens, latency_ms, validation_failed, fallback_count, session_id FK, client_id FK, request_id
  - `auth_refresh_tokens.py` (per ADR-0005 §10) — token_hash, user_id FK, successor_id nullable FK, revoked_at, expires_at, user_agent, last_used_at
  - `audit_log.py` — actor_id, actor_role, action, resource_type, resource_id, created_at
- **`backend/src/db/session.py`** — async session factory using `asyncpg`; `get_db()` FastAPI dependency
- **`backend/alembic/env.py`** — Alembic configured with async engine (`asyncpg`); `target_metadata` pointing at all models
- **Initial migration `e8a1523b2f3a`** — creates all 16 tables; circular FK between `moms`/`briefs` and `llm_calls` handled with deferred `op.create_foreign_key()` (see §3)
- **Integration test suite** — 29 tests passing: roundtrip writes per table, cascade-delete chains verified (client → sessions → moms → action_items → check_ins → hc_style_snippets)

## 3. Decisions made during this phase

- **`llm_calls` schema reconciled** — `model_requested`, `model_served`, `prompt_version`, `request_id` fields added per ADR-0003 amendment. These fields were not in the original data model diagram; they were resolved during this phase by reading ADR-0003 §4.
- **`auth_refresh_tokens` added to data model diagram** — the table was in ADR-0005 §10 but missing from `docs/diagrams/0002-data-model.md`. Added during P1 with a Mermaid update, walkthrough prose update, and Changelog entry.
- **`retired_at` added to `hc_style_snippets`** — needed for the P7 snippet retirement sweep (ADR-0003 §5); added to the model and migration now so P7 has no schema migration to write.
- **Circular FK between `moms`/`briefs` and `llm_calls` handled via deferred `op.create_foreign_key()`** — both tables reference `llm_calls.id`, and `llm_calls` references both. SQLAlchemy `create_all` would deadlock; Alembic migration splits table creation and FK creation into separate operations.

## 4. Bugs fixed mid-phase

Both drawn from SESSION_LOG 2026-05-01.

- **`server_default="'onboarding'"` triple-quoted by SQLAlchemy** — `create_all()` was producing `server_default = "'onboarding'"` (extra quotes) for the `journey_stage` column. Fixed to `server_default=text("'onboarding'")` for the DB-level default, plus a Python-side `default=` for in-process inserts. Same pattern applied to `moms.status` defaulting to `'draft'`.
- **pytest-asyncio event loop scoping** — async integration tests were failing with event loop scope conflicts. Fixed by adding `asyncio_default_test_loop_scope = "session"` to `pyproject.toml` `[tool.pytest.ini_options]`.

## 5. Source docs consulted

Per `prompts/starter_prompt_01.md` mandatory preparation for P1:

- `docs/diagrams/0002-data-model.md` — primary; the ERD that drove all table definitions
- `docs/decisions/0003-llm-strategy.md` — `llm_calls` schema (§4 telemetry) and `hc_style_snippets` schema (§5 snippet library)
- `docs/decisions/0005-auth-strategy.md` — `auth_refresh_tokens` schema (§10)
- `docs/decisions/0006-observability.md` — logging conventions; no sync DB calls posture

## 6. Verification

- **Verification date**: 2026-05-01
- **Verification record**: `docs/VERIFICATION.md` § P1 — Data Layer
- **Test count at end of phase**: 29 passing
- **Checks verified** (from VERIFICATION.md):
  - `uv run pytest -v` → 29 passed ✅
  - `alembic upgrade head` — 16 tables created ✅
  - `alembic downgrade base` then `upgrade head` — clean roundtrip ✅
  - `\d clients` → `journey_stage DEFAULT 'onboarding'` (no extra quotes) ✅
  - `\d moms` → `status DEFAULT 'draft'` ✅
  - Partial index `idx_refresh_tokens_active` uses `WHERE revoked_at IS NULL` ✅ (initially failed — see §4 bug fix)
  - All 16 tables present in `pg_tables` ✅
- **Cascade tests** (integration): insert `client` + 3 `hc_style_snippets` → delete client → snippets gone (verified in same transaction); same pattern for `moms`, `action_items`, `check_ins`. Re-verified in P4 after `clients.code NOT NULL` migration added additional constraints.

## 7. Lessons learned

- **Circular FKs need explicit Alembic handling.** The `moms`/`briefs`/`llm_calls` triangle is a recurring pattern in the codebase. Future schema additions to this cluster should use the same deferred-FK pattern established here.
- **`server_default` requires `text()`** — raw string `server_default` values get triple-quoted. Always use `server_default=text("'value'")` for string defaults in SQLAlchemy columns. Add a Python-side `default=` as well for ORM-created objects that don't hit the DB default path.
- **Adding fields from ADRs that aren't in the diagram.** `auth_refresh_tokens` and `llm_calls` fields existed in ADRs but not in the data model diagram. The right fix is update the diagram in the same commit as the model, not leave the diagram stale. Done here; should be the pattern going forward.
- **Pre-building `retired_at` and future-feature tables costs nothing.** Having `diet_charts`, `content_assignments`, and `retired_at` in the first migration means P7 and post-MVP features add rows, not migrations. The data layer is designed once; the API layer grows incrementally.
- **pytest-asyncio scope must be set explicitly.** Default event loop scope in `pytest-asyncio` causes session-scoped fixtures to fail with "attached to a different loop." Adding `asyncio_default_test_loop_scope = "session"` to `pyproject.toml` is mandatory before writing the first async test. Do this in the scaffold, not as a P1 surprise.

## 8. Carry-over to subsequent phases

- `get_db()` async session factory — used by every API endpoint in P3+
- `e8a1523b2f3a` migration — base for all subsequent Alembic migrations (P3 adds migration `60775f9338d3`; P4 adds `95df31e31f5f`)
- Cascade-delete chains — verified in P1 integration tests; re-verified in P4 (cascade from `clients` to `hc_style_snippets`)
- `retired_at` on `hc_style_snippets` — pre-built for P7 snippet retirement sweep; P4 and P5 do not use it
- `asyncio_default_test_loop_scope = "session"` in pyproject.toml — required by all async integration tests in P2, P3, P4
