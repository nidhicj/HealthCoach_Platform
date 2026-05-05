# PHASE-03: Domain CRUD + Client-Facing Endpoints

**Unit**: Unit_001_HcCoreCycle
**Status**: Complete | Verified
**Verification date**: 2026-05-02 (see `docs/VERIFICATION.md` § P3 — Domain CRUD + Client OAuth)
**Implements**: `Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` — the full domain CRUD layer: HC manages clients, sessions, MOMs, action items, check-ins; clients access their own sent data and submit check-ins
**ADRs implemented**: ADR-0005 (auth dependencies; client OAuth added), ADR-0001 (stack: cursor pagination, idempotent endpoints)

---

## 1. Scope

Phase 3 built every domain endpoint the HC core cycle requires — minus LLM content generation, which belongs to P4. HC can create and manage clients, sessions, MOMs (manual text at this phase), action items, and check-ins. Clients can view their sent MOMs and submitted check-ins via the `/api/me/` namespace. Client onboarding via HC-issued invite tokens was also completed here. 107 tests pass at phase end.

Source spec: SESSION_LOG explicitly noted that `docs/specs/0002-domain-crud.md` was deleted as redundant; `SPEC-0001-hc-core-cycle.md` is the authoritative P3 spec.

## 2. Deliverables shipped

Drawn from SESSION_LOG 2026-05-02.

**Schema extension — migration `60775f9338d3`**:
- `users.role` column (`server_default 'hc'`) — role stamped at account creation
- `clients.user_id` FK to `users` (nullable) — for client OAuth linking
- `sessions.deleted_at` — soft-delete column (filter-not-exposed at P3; P5+ may surface)
- `client_invite_tokens` table — SHA256 hash, 30-day TTL, single-use, audit fields

**`backend/src/api/deps.py`**:
- `HcClaimsDep`, `ClientClaimsDep` — role-specific JWT extraction
- `TenantDep` — hc_id from JWT
- `DbDep` — typed async session dependency
- `LimitDep` — page-size bounding (max 50)
- `PaginatedList[T]` — generic paginated response schema
- `encode_cursor()` / `decode_cursor()` — base64 cursor encoding shared by all list endpoints

**`backend/src/api/clients.py`**:
- `POST /api/clients` — create client (computes `CP<NNNN>` pseudonym code via MAX+1)
- `GET /api/clients` — cursor-paginated list (scoped to HC's tenant)
- `GET /api/clients/{id}` — detail; cross-tenant access → 404
- `POST /api/clients/{id}/invite` — issues SHA256 invite token; invalidates prior unused tokens for same client

**`backend/src/api/sessions.py`**:
- `POST /api/sessions` — create; duplicate session_number → 409
- `GET /api/sessions`, `GET /api/sessions/{id}` — list/detail
- `POST /api/sessions/{id}/end` — idempotent end
- `POST /api/sessions/{id}/mom` — create MOM with `status='draft'`
- `GET /api/sessions/{id}/mom` — retrieve MOM
- `PATCH /api/sessions/{id}/mom` — update; status transitions: draft → reviewed → sent
- `POST /api/sessions/{id}/mom/send` — idempotent send (sets status='sent', unlocks client visibility)
- `GET /api/sessions/{id}/brief` — 404 stub at P3; replaced by LLM generation in P4

**`backend/src/api/action_items.py`**:
- `POST /api/sessions/{id}/action-items`, `GET` (list), `GET /{item_id}`, `PATCH /{item_id}` — full CRUD; `completed_at` set/cleared on status transitions

**`backend/src/api/check_ins.py`**:
- `GET /api/clients/{id}/check-ins` — HC reads client's check-ins
- `PATCH /api/check-ins/{id}/flag` — HC sets/clears `sentiment_flag`; `model_fields_set` used to distinguish explicit `null` from omitted

**`backend/src/api/me.py`** (client-facing):
- `POST /api/me/check-ins` — client submits check-in
- `GET /api/me/moms` — list sent MOMs only
- `GET /api/me/moms/{id}` — detail; 404 if not `status='sent'`
- `GET /api/me/action-items` — client's own open items
- `PATCH /api/me/action-items/{id}` — client marks own items complete/in_progress

**`backend/src/auth/router.py` additions** (client OAuth):
- `GET /api/auth/client/start?invite=<token>` — verify invite, initiate Google OAuth
- `GET /api/auth/client/callback` — exchange code, link Client record, mark invite used, issue `role=client` JWT
- Fixed `/api/auth/refresh` to use `user.role` (not hardcoded `"hc"`) and look up `hc_user_id` from client record for client-role tokens

**`backend/tests/integration/conftest.py`** rewrite:
- Savepoint-based test isolation (`join_transaction_mode="create_savepoint"`)
- Test JWT keys injected before `src` imports (avoids settings-cache contamination)
- `client_user` / `client_rec` / `client_headers` fixtures added for client-actor test coverage

**Test suite**: 107 tests passing (up from 37 after P2).

## 3. Decisions made during this phase

Drawn from SESSION_LOG 2026-05-02.

- **D-1: `users.role` column** — role stamped at account creation (`server_default 'hc'`); not derived at query time. This avoids joins and keeps role visible for audit.
- **D-2: `client_invite_tokens` as a separate table** — not an inline column on `clients`. Separate table supports TTL, single-use enforcement, and an audit trail (who was invited when, which token was consumed).
- **D-3: Invite TTL = 30 days** — a new HC invite link expires after 30 days. Not configurable at MVP.
- **Cross-tenant responses are always 404 (never 403)** — prevents existence leakage: an HC in another tenant cannot tell whether a resource exists at all.
- **Client ME endpoints use `claims.sub` as client's user_id** — `hc_id` from the JWT pins the tenant; `sub` resolves to the client's `users.id`, which is then joined to `clients.user_id`.
- **Deleted `docs/specs/0002-domain-crud.md`** — that spec was a stub; `SPEC-0001-hc-core-cycle.md` already covered the domain model. Redundant spec removed to avoid drift.

## 4. Bugs fixed mid-phase

All discovered during manual verification (2026-05-02). Drawn from SESSION_LOG 2026-05-02.

- **`env_file=".env"` didn't find root `.env` when running from `backend/`** — Pydantic Settings was looking for `.env` in the current working directory (`backend/`), not the repo root. Fixed: `env_file=(".env", "../.env")` tries both locations.
- **Verification step 3 generated a random JWT sub with no `users` row** — the original verification script issued a JWT without inserting a real `users` row first, causing FK violations on session creation. Fixed: `scripts/create_hc_user.py` inserts a real HC user into the DB, then generates a JWT from that user's real `id`.
- **Heredoc in verification instructions caused terminal issues** — shell heredocs in multi-step curl sequences caused parsing errors in some terminals. Fixed: moved multi-step script into `scripts/create_hc_user.py`.
- **15-minute JWT expiry too short for full manual verification** — the default JWT expiry (15 min) expired before the manual verification sequence finished. Fixed: `scripts/create_hc_user.py` now issues 8-hour tokens for verification sessions.
- **`!!!` in curl URL triggered bash history expansion** — a `!!!` substring in the session URL pattern expanded unexpectedly in bash. Fixed: switched to single-quoted URLs in verification instructions.

## 5. Source docs consulted

Per `prompts/starter_prompt_02.md` mandatory preparation for P3:

- `Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` — primary; the authoritative P3 spec (replaced the deleted `0002-domain-crud.md`)
- `docs/diagrams/0002-data-model.md` — entity relationships, FK chains
- `docs/domain/glossary.md` — HC cycle term definitions
- `docs/domain/actors.md` — HC vs. Client role distinctions; ME endpoint scoping

## 6. Verification

- **Verification date**: 2026-05-02
- **Verification record**: `docs/VERIFICATION.md` § P3 — Domain CRUD + Client OAuth
- **Test count at end of phase**: 107 passing
- **Key results**: All 12 P3 manual checks passed. Verification found 5 bugs (all fixed in same session — see §4). Status: ✅ complete — manual verification passed 2026-05-02.

## 7. Lessons learned

- **`model_fields_set` for distinguishing explicit null from omission is the right pattern.** In `PATCH /check-ins/{id}/flag`, the caller can explicitly set `sentiment_flag=null` (clear the flag) or omit the field (leave it unchanged). Standard Pydantic excludes None by default; `model_fields_set` lets you detect intent. This pattern should be used on every PATCH endpoint that supports field clearing.
- **Verification scripts should create real DB state.** Random UUID JWTs with no corresponding DB row cause FK failures that look like auth bugs. Every manual verification sequence should use `scripts/create_hc_user.py` or equivalent to ensure the test user actually exists.
- **30-day invite tokens are comfortable for pilot.** The TTL decision (D-3) was made quickly — no strong requirement for shorter. Could be revisited post-pilot if HCs report invite links expiring unexpectedly.
- **Test isolation via savepoints is significantly faster than per-test transactions.** The conftest.py rewrite to savepoint-based isolation (`create_savepoint`) cut test suite runtime materially. This is the pattern for all future integration tests.

## 8. Carry-over to subsequent phases

- `PaginatedList[T]`, `encode_cursor()` / `decode_cursor()` — reused by any new list endpoints in P5+
- `_get_owned_client()` helper in `clients.py` — cross-tenant 404 pattern; P4 extends `sessions.py` using the same pattern
- `scripts/create_hc_user.py` — reused as-is for P4 manual verification
- 107-test baseline — P4 adds 37 more tests (144 total)
- `GET /api/sessions/{id}/brief` — the 404 stub built here was replaced by LLM generation in P4; stub removal was explicit (test `test_get_brief_returns_404_when_none` deleted in P4)
