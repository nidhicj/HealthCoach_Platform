# Session log

Append-only. Latest at top. Claude writes a new entry at the end of each substantial session.

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
