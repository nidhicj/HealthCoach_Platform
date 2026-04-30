# Actors

> **MERGE-REQUIRED**: existing `actors.md` in repo from prior session. This draft uses current terminology from ADR-0001/0003 and the HC-cycle spec. Reconcile when committing.

> Authoritative description of who the platform serves, what each actor can do, and how identity / authorization is structured.

---

## Primary actors

### Health Coach (HC)

The platform's paying user. Independent practitioner running their own coaching business.

**Authentication**: Google OAuth → backend-issued JWT (per ADR-0001).

**Permissions**:
- Full read/write on their own clients, sessions, MOMs, briefs, action items, content library
- Read on their own `llm_calls` telemetry (for their own debugging — UI optional at MVP)
- Read/write on their own snippet library (`hc_style_snippets` scoped to their `hc_user_id`)
- No access to any other HC's data

**Data scope**: every HC is a tenant boundary. All queries filtered by `hc_user_id`.

**Visible AI behavior**: HC sees AI drafts (MOM, brief, action items) and can edit before sending. HC may eventually see snippet library contents (open follow-up in ADR-0001 — DPDP transparency consideration).

### Client

The end user being coached.

**Authentication**: at MVP, **none directly** — clients do not log in. They receive HC-sent communications (MOM via email, check-ins via existing channels). The client experience is HC-mediated.

**This is a deliberate MVP simplification.** A client login surface (for in-app check-ins, content viewing, action-item tracking) is post-MVP. When introduced, it will be its own ADR.

**Permissions** (today): receive HC-sent content. Have no system-side identity beyond a record in `clients` table.

**Permissions** (future, post-client-login):
- Read their own MOMs, briefs, content assignments
- Write their own check-ins, action-item completion status
- Cannot see drafts, can only see HC-sent ('sent' state) content (the **coach-reviewed gate**)

**Data scope**: `clients.hc_user_id` is FK to `users.id`. Client data is owned by the HC who onboarded them. On HC account deletion, clients are not orphaned — they're either transferred or deleted per HC's choice (post-MVP).

### Operator (SoJo)

The platform builder. Has admin access for support / debugging.

**Authentication**: same Google OAuth flow, but with an `is_operator` flag on the `users` table. Set manually in DB; no UI.

**Permissions**:
- Read all data (for debugging, support tickets)
- Write nothing (production data is read-only from operator account; writes go through normal HC flow)
- Access to `llm_calls` across all HCs (cost monitoring, quality analysis)

**Audit**: every operator action that touches HC data writes to an `audit_log` table. This is a pre-launch requirement.

---

## Future actors (named, not implemented)

### Junior HC (system role, not human)

The AI persona that produces drafts. **Not an actor in the auth sense** — it has no identity, no login. It is the LLM behind the gateway, branded internally to clarify its role.

Why this matters: in the HC's mental model, the AI is a "junior" who drafts work for senior review. This framing keeps the HC accountable as the senior reviewer and prevents the "AI said it" diffusion of responsibility.

### Admin HC / Practice owner

If a single HC scales into a practice with assistants or junior coaches, a hierarchical role structure becomes relevant. **Not in MVP scope.** Captured here so the data model leaves room (`users.role` enum can extend; multi-tenancy via `hc_user_id` becomes `practice_id`).

---

## Authentication flow (MVP)

1. HC visits frontend → "Sign in with Google"
2. Frontend redirects to Google OAuth
3. Google returns ID token to frontend
4. Frontend sends ID token to backend `/auth/google` endpoint
5. Backend verifies token signature with Google, extracts email + sub
6. Backend looks up or creates `users` row
7. Backend issues short-lived access JWT + longer-lived refresh JWT
8. Frontend stores JWT in httpOnly cookie (refresh) + memory (access)
9. Subsequent requests include access JWT in `Authorization: Bearer` header

**No third-party auth provider** (per ADR-0001). Implementation owned. Standard libs: `python-jose` or `pyjwt` for JWT; `httpx` for Google verification.

**Workers-py #68 workaround**: every `httpx.AsyncClient` instantiation explicitly sets `User-Agent` header.

---

## Authorization model (MVP)

Simple role + tenant filtering at the FastAPI middleware layer:

1. **Authenticated** — does the request have a valid JWT?
2. **Tenant-scoped** — does the resource being accessed belong to this HC (`resource.hc_user_id == jwt.user_id`)?
3. **Operator override** — if `jwt.is_operator`, bypass tenant filter (with audit log entry).

No RBAC table at MVP. No row-level security in Postgres. App-layer filtering is sufficient at single-tenant or low-tenant-count scale.

**Re-evaluate when**: third HC onboarded, OR shared-tenant scenarios emerge (e.g., HC + assistant), OR compliance review demands DB-level enforcement.

---

## DPDP / privacy actor model

DPDP terms map to actors as:

- **Data Fiduciary**: the platform operator (SoJo) — decides purposes and means of processing
- **Data Processor**: cloud vendors (Cloudflare, AWS, OpenRouter) — process on our behalf
- **Data Principal**: clients (their data is the protected category) and HCs (their account data)

Consent management is captured in `consents` table; revocation triggers cascading deletion (per ADR-0003 §7).

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-28 | Fresh draft. MERGE-REQUIRED with existing repo file. |
