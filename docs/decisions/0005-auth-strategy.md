# ADR-0005: Auth Strategy

**Status**: Accepted
**Date**: 2026-04-29
**Decision driver**: SoJo (architect-authored draft for SoJo review)
**Supersedes**: n/a
**Relates to**: ADR-0001 (stack — locks Google OAuth + owned JWT at high level), ADR-0002 (Cloudflare Workers runtime constraints), ADR-0004 (places auth code under `backend/src/auth/`)

---

## Context

ADR-0001 settled the high-level posture: **backend-issued JWT, Google OAuth as identity provider, owned implementation**. It did not settle the strategy — the dozen decisions that constitute "owned auth done correctly." This ADR settles those.

The platform has three current/future actor types per `domain/actors.md`: **HC** (Health Coach, paying user), **Client** (end user receiving coaching), and **Operator/Admin** (SoJo, future ops staff). Auth must support all three from day one, even though only HC UI is built at MVP. Tenant boundary is `hc_user_id` — every Client and every domain object belongs to exactly one HC.

Constraints already locked:

- Cloudflare Python Workers runtime (`workers-py` open beta) → must work within Web Crypto API, no native crypto modules *(superseded by Cloud Run — see §Amendment 2026-06-24)*
- `workers-py` #68 (httpx missing User-Agent) → every outbound HTTP call sets UA explicitly *(no longer applicable on Cloud Run — see §Amendment 2026-06-24)*
- DPDP Act 2023 → real deletion (not soft delete), India-region for personal data, explicit revocable consent
- Google OAuth as the only IdP at MVP (no email/password, no other social providers)
- ~~Frontend is Next.js 15 on Cloudflare Pages; backend is FastAPI on Workers; same eTLD+1 → cookies are first-party~~ **VIOLATED** — deployment moved to GCP Cloud Run; `run.app` is in the Public Suffix List; frontend and backend are cross-site. See §Amendment 2026-06-24 for the resolution.

What's at stake if this is done wrong: account takeover (catastrophic for a health-data product), tenant boundary violation (one HC seeing another HC's data — DPDP breach), refresh-token replay (silent persistent compromise), inability to revoke (cannot honor DPDP deletion rights).

---

## Options considered

### Option A: DIY — Google OAuth handler + own JWT issuance + own refresh rotation in FastAPI

Build it. Use `authlib` or hand-rolled OAuth client for the Google flow, `python-jose` or `pyjwt` for JWT signing/verification, Postgres-backed refresh tokens.

- **Pros**: zero vendor lock-in; full control over claim shape, TTLs, revocation; no per-MAU pricing; works inside Cloudflare Workers without a third-party SDK; straightforward to reason about; no data-residency questions about a third party storing identity records.
- **Cons**: more code to write and maintain (~600–1000 LOC); SoJo owns every security bug; password-reset / MFA / passkey flows would all be DIY if needed later (not needed at MVP — Google handles authentication itself).
- **Cost**: 2–3 days of focused build, ongoing review burden. No license cost.

### Option B: Auth0 / Clerk / Stytch (managed identity)

Use a managed provider. Frontend SDK handles the Google flow; provider issues JWTs; backend verifies via JWKS.

- **Pros**: less code; battle-tested security; built-in MFA / passkeys / org features.
- **Cons**: vendor lock-in on identity (the worst kind to have); per-MAU pricing crosses ₹0/mo only at low scale (Clerk free is 10K MAU, Auth0 free is 7.5K MAU — fine for pilot, becomes a recurring cost at scale); identity records sit on the provider's infra (often US) which complicates the DPDP story; SDKs may not be Cloudflare-Workers-friendly out of the box; we lose precise control over claim shape and refresh semantics; data-residency story becomes "trust the provider's region claims."
- **Cost**: ₹0 at MVP, escalating. ~1 day of build (less code, but integration + provider config). Rework cost to migrate off later is high.

### Option C: Supabase Auth

Supabase has a Mumbai region (per memory). Auth is bundled with the Postgres they host.

- **Pros**: India-region, free tier, integrated with Postgres.
- **Cons**: forces using Supabase's Postgres (we chose AWS RDS Mumbai per ADR-0001) — splitting auth DB from app DB is exactly the kind of distributed-state problem we don't want at this stage; or migrate everything to Supabase and walk back ADR-0001's RDS decision; either way it's a stack-level reopen.
- **Cost**: would invalidate ADR-0001 partially. Not worth it.

### Option D: Cloudflare Access

CF's own zero-trust offering. Sits in front of Workers.

- **Pros**: native CF integration; SSO over Google works.
- **Cons**: designed for internal app access (employees, contractors), not for end-user auth in a SaaS product. Can technically be used here, but the UX (CF login page, not yours) and pricing model don't fit a multi-tenant consumer SaaS where Clients sign in via invite.
- **Cost**: not appropriate; eliminate.

---

## Decision

**Option A (DIY).** Build a focused auth module under `backend/src/auth/` that handles Google OAuth, issues ES256-signed JWTs, manages refresh tokens with rotation and revocation, and exposes FastAPI dependencies for protected routes.

The strategy below specifies every choice that "owned implementation" leaves open. Claude Code implements per this ADR; deviations require ADR amendment.

### 1. OAuth flow: Authorization Code with PKCE

Standard Google OAuth 2.0 Authorization Code grant. PKCE (RFC 7636) added on the frontend even though the backend exchanges the code — PKCE costs nothing to add, prevents authorization-code interception attacks if anything leaks via referer/logs/etc., and is current best practice for any client where an attacker might observe the redirect URL. State parameter (anti-CSRF) is mandatory.

Redirect URI: `${API_BASE_URL}/api/auth/google/callback`. Whitelisted in Google Cloud Console. **After §Amendment 2026-06-24**: `API_BASE_URL` is the *frontend* Cloud Run URL — Google redirects the browser to the Next.js BFF, which proxies the callback to the backend.

Scopes requested: `openid email profile` only. No Drive, no Calendar — those are future integrations, ask separately when needed.

### 2. JWT signing: ES256 (ECDSA P-256)

ES256 over HS256 because:

- The frontend, future microservices, and any external verifier (e.g., a Sentry integration that wants to attach user context) can verify tokens using the public key without holding the signing secret. HS256 requires every verifier to hold the same secret — fine for one service, bad practice the moment a second service exists.
- Web Crypto API in Cloudflare Workers supports ES256 natively (`crypto.subtle.sign` with `ECDSA / P-256`).
- ECDSA P-256 is FIPS-approved, widely supported in libraries, and produces compact tokens (smaller than RS256 and not meaningfully slower on the verify path).
- Migration from HS256 to ES256 later means rotating every issued token. Doing it now costs nothing extra.

Key storage: ES256 private key in Cloudflare Workers Secrets (`JWT_PRIVATE_KEY`), public key in `JWT_PUBLIC_KEY` (also a secret to keep config simple, though it doesn't strictly need to be). PEM format. Generated once via `openssl ecparam -name prime256v1 -genkey -noout -out priv.pem` then `openssl ec -in priv.pem -pubout -out pub.pem`.

Key rotation: documented procedure in `docs/ops/secrets-management.md`. Rotation is rare (yearly or on suspected compromise) and involves issuing both keys for a transition window — out of scope for this ADR.

### 3. JWT claims

Access token claim shape:

```json
{
  "iss": "https://api.parivarthan.com",
  "aud": "parivarthan-api",
  "sub": "<user_uuid>",
  "role": "hc | client | admin",
  "hc_id": "<hc_user_uuid>",
  "jti": "<random_uuid>",
  "iat": <unix_seconds>,
  "exp": <unix_seconds>,
  "nbf": <unix_seconds>
}
```

Notes:

- `hc_id` is the tenant scoping field. For role `hc`, `sub == hc_id`. For role `client`, `hc_id` is the HC who owns this client. For role `admin`, `hc_id` is null (admin queries are explicit and don't go through tenant-scoped middleware).
- `jti` enables per-token revocation on the access path if we ever need it (currently we rely on short access TTL + refresh revocation; `jti` is forward-compatible).
- `aud` and `iss` are verified on every request. Mismatch → 401.
- No PII in claims. Email and name go to the frontend separately on login response, not in the JWT.

Claim mapping note: the build-plan uses `hc_id` in JWT (matches above). The DB column is `hc_user_id`. The auth module owns this translation.

### 4. Token TTLs

- **Access token**: 15 minutes. Short enough that a leaked token has bounded blast radius. Long enough that normal usage doesn't refresh excessively.
- **Refresh token**: 30 days, sliding (rotation extends). After 30 days of no use, expires.
- **Google OAuth state token**: 10 minutes. Stored server-side in a short-lived cache (Workers KV or in-memory map; KV preferred for Worker isolate independence).
- **Client invite token**: 7 days. One-time use. SHA256-hashed in DB.

### 5. Refresh token strategy

**Rotation**: every successful `/api/auth/refresh` call issues a new refresh token and invalidates the old one. This is one-time-use rotation per OAuth 2.0 BCP (RFC 8725).

**Replay detection**: if a refresh token is presented after it's been used (i.e., `revoked_at` is not null OR a successor token exists), that's a replay attack signal. Response: revoke **all** refresh tokens for that user (the legitimate user has lost their session anyway by this point), log a high-severity Sentry event, force re-login. This is the standard "refresh token reuse" handling.

**Storage**: SHA256 hash of the token in `auth_refresh_tokens.token_hash`. Plaintext token returned to the client once at issuance and never stored. SHA256 (not bcrypt) because (a) refresh tokens are already 256 bits of randomness — there's nothing to brute-force, hashing is just defense-in-depth against DB read; (b) bcrypt would force a slow path on every refresh, unnecessary.

**Cookie**: `HttpOnly`, `Secure`, `SameSite=None`, `Path=/api/auth`, `Max-Age=2592000` (30 days). `Path=/api/auth` so the refresh cookie is not sent on every API request — only on auth endpoints.

**Amendment 2026-06-24 — cookie domain and SameSite**:

The original spec said `SameSite=Lax` and `Domain=<your domain>`, assuming same-eTLD+1 deployment. Both assumptions are now invalid:

- `run.app` is in the Public Suffix List. Frontend (`hc-platform-frontend-*.run.app`) and backend (`hc-platform-backend-*.run.app`) are **different registrable domains** — cross-site. `SameSite=Lax` blocks cross-site cookies; Firefox Total Cookie Protection (dFPI) and Safari ITP block them even with `SameSite=None; Secure`.
- Resolution: **BFF proxy pattern**. The Next.js frontend (`app/api/[...path]/route.ts`) proxies all `/api/*` requests server-to-server. The OAuth callback redirect + `Set-Cookie` is re-emitted by the Route Handler with the cookie attributed to the frontend domain. All browser requests are now same-origin. The cookie is first-party in all browsers.
- Current code sets `SameSite=None; Secure` when `APP_ENV != "dev"` (correct for a cross-origin flow that used to exist; harmless in the same-origin proxy setup). A follow-up can tighten this to `SameSite=Lax` once the proxy is confirmed stable. No `Domain` attribute is set — the browser infers the frontend hostname as the cookie domain.

See `diagrams/0001-system-architecture.md §Amendment 2026-06-24` for the updated request flow.

**Access token delivery**: returned in the JSON response body of `/api/auth/google/callback` and `/api/auth/refresh`. Frontend holds it in memory (React state / a small auth context). Not in `localStorage` (XSS-readable). Not in a cookie (would need to be readable, which means not HttpOnly, which means XSS-readable anyway).

### 6. CSRF protection

`SameSite=Lax` blocks the worst CSRF cases (cross-origin POST), but not all of them (top-level GET-then-POST flows). Because state-changing endpoints (`POST /api/sessions`, `PATCH /api/moms/:id`, etc.) carry the access token in the `Authorization: Bearer` header — not in a cookie — they are inherently CSRF-safe. An attacker's browser cannot forge an `Authorization` header from a cross-origin request.

The auth endpoints themselves (`/api/auth/refresh`, `/api/auth/logout`) **do** rely on the refresh cookie, so they need CSRF protection. Approach: double-submit cookie pattern — the frontend reads a non-HttpOnly `csrf_token` cookie value and echoes it in an `X-CSRF-Token` header. Backend verifies match. The `csrf_token` cookie is rotated on each refresh.

This is enough for MVP. If we ever add cookie-based access tokens, CSRF protection extends to all mutating endpoints.

### 7. Roles and authorization

Three roles: `hc`, `client`, `admin`. Stored on `users.role` (TEXT with CHECK constraint).

Authorization model: **role-based at the route level + tenant-scoped at the query level**. Two FastAPI dependencies:

- `require_role("hc")` / `require_role("client")` / `require_role("admin")`: rejects requests where JWT `role` doesn't match. 403 on mismatch.
- `current_tenant()`: returns the `hc_id` from the JWT. Every domain query must filter by this — enforced by code review and integration tests, not by DB-level RLS at this stage (RLS adds operational complexity and asyncpg/Workers integration with Postgres roles is fiddly; we'll add RLS as defense-in-depth in a later ADR if/when we have a second backend service hitting the same DB).

Specifically: an HC's JWT cannot access another HC's data even if the URL says so. The tenant filter is applied in the data-access layer; the URL `hc_id` (if present) is verified to match the JWT's `hc_id`, otherwise 404 (not 403 — don't leak existence).

### 8. Client onboarding via HC-issued invite

HC creates a Client record (placeholder) → system generates a one-time invite token → token + invite URL emailed to the Client → Client signs in via Google at the invite URL → backend verifies (a) invite token valid + unconsumed + matching email, (b) Google email matches invite email, (c) ties Google `sub` to the Client record, marks invite consumed.

Email-mismatch behavior: reject with a clear error message. Do not auto-link a different Google email to the Client record — that would let an attacker who knows the invite URL claim a Client record under their own Google identity.

Invite tokens stored as SHA256 hash, 7-day TTL, single-use.

### 9. HTTP client User-Agent ~~(workers-py #68 workaround)~~ [superseded]

**Amendment 2026-06-24**: This section was written for Cloudflare Python Workers, which had a known bug (`workers-py` #68) requiring explicit `User-Agent` on every `httpx` call. Deployment moved to GCP Cloud Run (standard CPython), where this bug does not apply. The factory `make_http_client()` in `backend/src/lib/http.py` is retained as good practice (consistent User-Agent across all outbound calls) but is no longer a correctness requirement.

### 10. Schema: `auth_refresh_tokens`

This table is **new** — not currently in `diagrams/0002-data-model.md`. ADR-0005 defines it; the data model diagram must be updated after this ADR is Accepted (flagged in Consequences).

```sql
CREATE TABLE auth_refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,            -- SHA256 hex
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    last_used_at    TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,                     -- non-null = explicitly revoked
    successor_id    UUID REFERENCES auth_refresh_tokens(id),  -- set when this token has been rotated
    user_agent      TEXT,                            -- captured at issuance; for sessions list UI
    ip_at_issue     INET,                            -- for sessions list UI; not used for security checks
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user_id ON auth_refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON auth_refresh_tokens (token_hash);
CREATE INDEX idx_refresh_tokens_active ON auth_refresh_tokens (user_id) 
    WHERE revoked_at IS NULL AND expires_at > NOW();
```

Cascade-on-delete from `users` is correct: DPDP deletion of a user wipes all their refresh tokens. Successor-id self-reference enables replay detection (presented token has a successor → reused → revoke all).

### 11. Endpoints

| Endpoint                      | Method | Auth                        | Purpose                                                                     |
| ----------------------------- | ------ | --------------------------- | --------------------------------------------------------------------------- |
| `/api/auth/google/start`    | GET    | none                        | Returns redirect URL with `state` and PKCE `code_challenge`             |
| `/api/auth/google/callback` | GET    | none                        | Google redirects here with `code` + `state` → exchange → issue tokens |
| `/api/auth/refresh`         | POST   | refresh cookie + CSRF token | Rotate refresh token, return new access token                               |
| `/api/auth/logout`          | POST   | refresh cookie + CSRF token | Revoke current refresh token                                                |
| `/api/auth/sessions`        | GET    | access token                | List active refresh tokens (user_agent, last_used_at, created_at)           |
| `/api/auth/sessions/:id`    | DELETE | access token                | Revoke a specific refresh token (by id)                                     |
| `/api/auth/sessions/all`    | DELETE | access token                | "Sign out everywhere" — revoke all the user's refresh tokens               |
| `/api/auth/invite`          | POST   | access token (role=hc)      | Create one-time invite for a Client                                         |
| `/api/auth/invite/:token`   | GET    | none                        | Validate invite (returns email + HC name, not the token itself)             |

### 12. What this ADR does NOT cover

- MFA / passkeys (deferred — Google handles authentication factor)
- Email/password auth (not in scope, may never be — Google-only at MVP)
- Email/SMS as second factor (not in scope at MVP)
- Federated identity beyond Google (not in scope at MVP)
- DB-level row-level security (deferred to a future ADR if a second service joins the DB)
- Service-to-service auth (not needed yet — single backend service)
- Rate limiting on auth endpoints (Cloudflare WAF rate-limit rules per ADR-0002 / phase P9)

---

## Consequences

### Positive

- Tenant boundary is enforced in two places (route-level role check + query-level `hc_id` filter), which is hard to get wrong if the dependency injection is consistent.
- ES256 future-proofs the system for verifier-without-secret use cases (frontend verification, microservice expansion, external integrations).
- Refresh rotation with replay detection catches the realistic attack: a leaked refresh token gets used by an attacker, then the legitimate user refreshes — replay alarm fires, all sessions revoked.
- DPDP deletion is straightforward: `DELETE FROM users WHERE id = ?` cascades to `auth_refresh_tokens` and everything else (clients, snippets, etc., per their FK rules).
- All code lives in one Python module under our control; no SDK upgrade treadmill.

### Negative / tradeoffs accepted

- ~600–1000 LOC of security-sensitive code to write and review. SoJo is the only reviewer; high responsibility.
- No MFA at MVP. Google itself enforces MFA for accounts that opt in, but we can't require it. Acceptable for pilot; revisit before broad launch.
- CSRF protection on auth endpoints uses double-submit cookie — slightly more frontend code than if we relied purely on `SameSite=Strict`. Worth it for the OAuth UX.
- No DB-level row-level security at this stage. Tenant boundary is enforced in app code only. This is a real risk if a future engineer adds a query that forgets the `hc_id` filter — mitigated by code review, integration tests that try cross-tenant access, and an eventual RLS layer.
- ES256 keys must be managed (generated, stored, rotated). One-time setup; documented procedure needed in `docs/ops/secrets-management.md`.

### Things to revisit

- **MFA / passkeys**: when first paying HC subscribes (post-pilot), or if any incident points to credential compromise.
- **DB-level RLS**: when a second service starts hitting the same DB, OR when a security audit recommends it, OR before any non-pilot HC onboards.
- **Switch to managed identity**: only if (a) DIY auth eats more than 10% of build time across two consecutive months, OR (b) a compliance regime adds requirements that are cheaper to outsource (HIPAA-equivalent, SOC2 customer, etc.). Migration cost is meaningful — plan for it as a 1-week effort.
- **Refresh token TTL**: 30 days is conventional but untested for HC usage patterns. Shorten if pilot data shows refresh happens daily anyway; lengthen if HCs complain about being logged out.

### Required follow-on actions (after Acceptance)

1. **Update `diagrams/0002-data-model.md`** to add the `auth_refresh_tokens` table. Include in P1's first migration. (claude.ai task — Claude Code or claude.ai can draft the diagram update.)
2. **Update `domain/actors.md`** if the role names here (`hc`, `client`, `admin`) deviate from current canonical terms. Quick check confirmed they match.
3. **Add `docs/ops/secrets-management.md` entry** for ES256 key generation + rotation procedure.

---

## References

- ADR-0001 — Stack selection (locks Google OAuth + owned JWT at high level)
- ADR-0002 — Runtime topology (Cloudflare Workers constraints)
- ADR-0004 — Repo structure (`backend/src/auth/` location)
- `domain/actors.md` — role definitions and tenant model
- `docs/build-plan.md` Phase 2 — acceptance criteria this ADR enables
- RFC 6749 (OAuth 2.0 Framework)
- RFC 7636 (PKCE)
- RFC 8725 (OAuth 2.0 Best Current Practice — refresh token rotation)
- RFC 7519 (JWT)
- OWASP JWT Cheat Sheet
- Google Identity OAuth 2.0 docs: https://developers.google.com/identity/protocols/oauth2
- Cloudflare Workers Web Crypto: https://developers.cloudflare.com/workers/runtime-apis/web-crypto/

---

---

## Amendment: 2026-06-24 — BFF proxy replaces cross-origin cookie strategy

**What changed**: Deployment moved to GCP Cloud Run. `run.app` is in the Public Suffix List — frontend (`hc-platform-frontend-*.run.app`) and backend (`hc-platform-backend-*.run.app`) are cross-site. The original cookie strategy (`SameSite=Lax`, same-eTLD+1) was incompatible with Firefox Total Cookie Protection and Safari ITP.

**Resolution**: Next.js Backend-for-Frontend (BFF) proxy.

- New file: `frontend/src/app/api/[...path]/route.ts` — catch-all Route Handler that proxies all `/api/*` requests server-to-server to the FastAPI backend. For the OAuth callback (which returns `302 + Set-Cookie`), the handler intercepts the redirect, copies the `Set-Cookie` header, and re-emits it so the browser attributes the cookie to the frontend domain.
- `frontend/src/lib/config.ts`: `API_URL = ""` — all browser fetch calls are same-origin.
- `API_BASE_URL` Secret Manager value: changed to the frontend Cloud Run URL so the OAuth `redirect_uri` sent to Google points to the frontend BFF, not the backend.
- Google Cloud Console: frontend URL added to authorized redirect URIs.

**Sections updated in this ADR**: §Context (crossed-out same-eTLD+1 assumption), §1 (redirect URI note), §5 (cookie SameSite and domain), §9 (workers-py workaround superseded).

**Known follow-ups** (not blocking):
- `SameSite=None` → `SameSite=Lax` cleanup in backend cookie: all requests are now same-site via the proxy; `Lax` is more secure. Deferred until proxy is confirmed stable across all browsers.
- PKCE state store (`_state_store: dict` in `router.py`): in-memory, multi-instance unsafe on Cloud Run. Fix: Cloud Memorystore (Redis) or a DB-backed state. Low risk at pilot scale.
- CSRF double-submit cookie (§6): spec'd but not yet implemented. Still needed on `/api/auth/refresh` and `/api/auth/logout`.

---

## Changelog

| Date       | Change         | Reason                                            |
| ---------- | -------------- | ------------------------------------------------- |
| 2026-06-24 | Amendment: BFF proxy pattern replaces cross-origin cookie strategy. Sections updated: §Context, §1, §5, §9. New §Amendment block added. | `run.app` in PSL → cross-site deployment → Firefox/Safari block third-party cookies. |
| 2026-04-29 | Initial draft. | Required by build-plan P2; defines auth strategy. |
