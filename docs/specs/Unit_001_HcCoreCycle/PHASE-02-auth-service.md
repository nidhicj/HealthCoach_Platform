# PHASE-02: Auth Service

**Unit**: Unit_001_HcCoreCycle
**Status**: Complete | Verified
**Verification date**: 2026-05-01 (see `docs/VERIFICATION.md` § P2 — Auth Service)
**Implements**: Pre-condition for all SPEC-0001 phases — every SPEC-0001 actor (HC and Client) must authenticate before any domain data can be accessed
**ADRs implemented**: ADR-0005 (auth strategy — primary; ES256 JWT, Google OAuth PKCE, refresh token rotation, tenant scoping)

---

## 1. Scope

Phase 2 built the complete auth substrate: Google OAuth sign-in for HCs, JWT issuance and verification (ES256), refresh token rotation with replay detection, and the FastAPI dependencies that enforce role and tenant constraints on every downstream endpoint. No domain endpoints were built — only the auth plumbing that P3+ depends on.

P2 ran in the same session as P0 and P1 on 2026-05-01 (`prompts/starter_prompt_01.md`).

## 2. Deliverables shipped

Drawn from SESSION_LOG 2026-05-01.

**Why DIY auth (not a managed provider)** — ADR-0005 evaluated Auth0/Clerk/Supabase Auth and rejected all: managed providers have per-MAU pricing that becomes a recurring cost at scale, US-region identity records that complicate DPDP, and limited control over JWT claim shape and refresh semantics. DPDP real-deletion requirement (data must be purged, not just flagged) makes owned-token revocation mandatory. DIY with `python-jose` (ES256) was chosen.

**`backend/src/auth/` module** — full auth package:
  - `jwt_utils.py` — ES256 JWT sign (`create_access_token`) and verify (`decode_access_token`) using `python-jose`; claims: `sub`, `role`, `hc_id`, `iat`, `exp`, `iss` per ADR-0005
  - `google.py` — Google OAuth PKCE flow: `start_oauth()` (build redirect URL + state), `exchange_code()` (code → access token → user info)
  - `refresh.py` — `rotate_refresh_token()`: verify hash, check `successor_id` then `revoked_at`, issue new token, mark old revoked
  - `router.py` — 4 endpoints:
    - `GET /api/auth/google/start` — redirect to Google
    - `GET /api/auth/google/callback` — exchange code, upsert user, issue JWT + set HTTP-only refresh cookie
    - `POST /api/auth/refresh` — rotate refresh token, return new access token
    - `POST /api/auth/logout` — revoke current refresh token
- **`backend/src/api/deps.py`** — FastAPI dependencies:
  - `require_role(role)` — validates JWT and enforces role claim
  - `current_tenant()` — extracts `hc_id` from JWT; every domain query filters by this
- **JWT shape** (per ADR-0005): `sub` (user UUID), `role` ('hc' | 'client'), `hc_id` (tenant boundary UUID), `iat`, `exp`, `iss`; signed ES256; access token in response body; refresh token in HTTP-only Secure SameSite=Lax cookie (first-party: same eTLD+1 as frontend on Cloudflare Pages)
- **Refresh token storage**: SHA256 hash only — plaintext never persisted; `auth_refresh_tokens` row includes `token_hash`, `user_id`, `successor_id` (populated when rotated), `revoked_at`, `expires_at`, `user_agent`, `last_used_at`
- **`POST /api/auth/logout`** — revokes current refresh token by setting `revoked_at`; subsequent refresh attempts → 401
- **`POST /api/auth/sessions` (list active)** — Not recorded as present in SESSION_LOG; `POST /api/auth/logout` is confirmed; build-plan lists a "sessions list" endpoint — check `auth/router.py` if needed
- **Auth integration test suite** — 37 tests passing covering sign-in, token decode, replay detection, revocation, tenant scoping

## 3. Decisions made during this phase

- **Replay detection check order** — in `rotate_refresh_token()`, `successor_id` is checked before `revoked_at`. This matters because a compromised token that was already rotated has a `successor_id` set; checking revocation first would give a different error path. The correct semantic is: "has this token already been used to generate a successor?" → if yes, it's been replayed.
- **Refresh token stored as SHA256 hash** — plaintext refresh token is never stored in `auth_refresh_tokens`; only the SHA256 hash. This is an ADR-0005 requirement, not a phase decision, but it was implemented and tested here.

## 4. Bugs fixed mid-phase

Drawn from SESSION_LOG 2026-05-01.

- **`auth_refresh_tokens` partial index used `NOW()` (volatile) in predicate** — the initial migration created a partial index with `WHERE expires_at > NOW()`. PostgreSQL rejects volatile functions in partial index predicates. Fixed to `WHERE revoked_at IS NULL` (the actual semantics needed: index only active/unrevoked tokens). This is the index that makes `rotate_refresh_token()` fast.

## 5. Source docs consulted

Per `prompts/starter_prompt_01.md` mandatory preparation for P2:

- `docs/decisions/0005-auth-strategy.md` — full read; primary; defines JWT claims, refresh token schema, PKCE flow, replay detection requirement, tenant boundary (`hc_user_id`)
- `docs/domain/actors.md` — HC and Client role definitions; P2 only implements HC sign-in (Client OAuth deferred to P3)

## 6. Verification

- **Verification date**: 2026-05-01
- **Verification record**: `docs/VERIFICATION.md` § P2 — Auth Service
- **Test count at end of phase**: 37 passing
- **Key checks** (from VERIFICATION.md):
  - Auth routes registered: `/api/auth/google/start`, `/api/auth/google/callback`, `/api/auth/refresh`, `/api/auth/logout` ✅
  - JWT decode returns correct claims (`sub`, `role`, `hc_id`) ✅
  - Refresh rotation: old token rejected on second use ✅
  - Revocation: `revoked_at` set; subsequent refresh → 401 ✅
  - Tenant scoping: HC1's JWT cannot access HC2's data ✅
  - Partial index predicate uses `WHERE revoked_at IS NULL` (not `NOW()`) ✅

## 7. Lessons learned

- **Partial index gotcha with volatile functions** — `NOW()` in a partial index predicate is the kind of bug that passes `alembic upgrade head` but fails silently or raises a cryptic Postgres error depending on version and config. The fix (`WHERE revoked_at IS NULL`) is both correct and simpler. Rule: prefer structural predicates over time-based ones in partial indexes.
- **Replay detection semantics vs. implementation** — the `successor_id` vs. `revoked_at` ordering might seem like an implementation detail, but it determines what error the caller receives when presenting a replayed token. Getting the semantics right here prevents confusing auth errors in P3/P4 when client flows also use refresh tokens.
- **P3 will extend `auth/router.py`** — the client OAuth flow (`GET /api/auth/client/start`, `GET /api/auth/client/callback`) was added in P3 on top of the HC-only skeleton built here. The router extension point was clean.
- **DIY auth is the right call at this product stage.** Managed providers (Clerk, Auth0) would have required trusting a US-region service with health-coach session identity data — a DPDP concern — and would have added per-MAU cost. The P2 implementation is ~400 LOC and covers everything the pilot needs. Migration path: if Google OAuth is ever replaced or supplemented, the JWT issuance and refresh rotation layers are independent of the identity provider.
- **`hc_id` claim design is the key architectural decision.** Every domain object is scoped to `hc_id`, not `user_id`. This means a single user can theoretically hold multiple HC identities (future org feature) without re-architecting auth. It also means the tenant boundary is explicit in every JWT and every DB query — not inferred from session context.
- **`scripts/create_hc_user.py` is more useful than expected.** The manual verification step that required a real user in the DB revealed that a reusable HC-creation script was necessary. This script became standard for P3 and P4 verification as well.

## 8. Carry-over to subsequent phases

- `require_role()` FastAPI dependency — used by every HC endpoint in P3+
- `current_tenant()` FastAPI dependency — the single enforcement point for tenant scoping; every domain query in P3+ uses this
- `decode_access_token()` — reused by P3 client auth flow; `hc_id` claim in client tokens pins the tenant boundary for client-facing endpoints
- Auth integration tests (37) — baseline for regression; P3 adds 70+ more on top
- `create_access_token()` — reused by `scripts/create_hc_user.py` for manual verification in P3 and P4
