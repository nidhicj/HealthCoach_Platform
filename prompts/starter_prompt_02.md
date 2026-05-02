We are continuing the build. Scope of this session: **Phase 3 (Domain CRUD)** only, per `docs/build-plan.md`. Stop at the end of P3 — do not start P4. P0, P1, P2 are complete (37/37 tests passing) and P2 manual verification is done.

# Mandatory preparation (before writing any code)

1. Read `CLAUDE.md` (root) and `PREFLIGHT.md` in full. The anthem and the preflight block are non-negotiable for every substantive response in this session.
2. Read `HANDOVER-P3.md` (root, or wherever SoJo placed it). This is your authoritative current-state document. It replaces git archaeology — trust it, but verify against the actual files when something looks off.
3. Read `docs/build-plan.md` Phase 3 section in full, plus the "How to use this when working with Claude Code" and "Traceability matrix" sections.
4. Read every primary (●) and secondary (○) source doc the matrix marks for P3:
   - `docs/diagrams/0002-data-model.md` (full read — primary). Field names, FK relationships, indexes, cascade rules. The auth_refresh_tokens table and the `retired_at` column on `hc_style_snippets` were added during P1; confirm they're present.
   - `docs/domain/glossary.md` (full read — primary). Use exact terminology from here in API design (HC, client, session, MOM, AST, snippet, brief, action item, check-in).
   - `docs/domain/actors.md` (full read — primary). Defines who can read/write what. P3's tenant scoping and the coach-reviewed gate flow directly from this.
   - `docs/decisions/0005-auth-strategy.md` (full read — secondary, but you need it for `require_role()` and `current_tenant()` usage patterns).
5. Read `docs/specs/` for any existing spec. If `0003-domain-crud.md` already exists, extend it; if not, you'll write it as the first step (see below).
6. Read the most recent entry in `docs/SESSION_LOG.md` to confirm what was last completed.

If any referenced document is missing, contradicts another, or contradicts `HANDOVER-P3.md`, **stop and produce a `## Context missing` block** per anthem rule 7. Do not guess. Do not pick a winner silently between conflicting docs.

# Source-doc consistency check (do this before writing any code)

After reading the source docs, produce a short report:
- "Source docs consistent: [yes / no]"
- If no: list each contradiction. SoJo will resolve before you proceed.
- Specifically confirm: (a) `auth_refresh_tokens` table is in the data model diagram, (b) `retired_at` column is on `hc_style_snippets` in the diagram, (c) `llm_calls` schema in the diagram matches ADR-0003's amended schema (`model_requested`, `model_served`, `prompt_version`, `request_id`).

This is rule 4 (use most relevant docs) made operational. If the docs disagree, code written from them will be wrong somewhere.

# Operating rules for this session

- Run a preflight block (per `PREFLIGHT.md`) before every substantive response. Compressed (3 lines) is fine for tight follow-ups; full preflight before each new sub-task (spec, schemas, routers, tests).
- **Spec first, code second.** Anthem rule 9. Before any router code, write `docs/specs/0003-domain-crud.md` per `template-spec.md` and `skill-write-spec.md`. Get SoJo's confirmation on the spec before writing endpoint code. The spec is not optional and is not a write-up-after-the-fact.
- Verify before claiming done. "It should work" is banned (rule 14). Run pytest, hit the actual endpoints with curl/httpie, query the DB. The Postgres MCP (read-only) is available — use it for verification queries; never as a fallback to skip writing tests.
- Commit per `CONTRIBUTING.md`. Conventional commits, one logical change per commit. Don't squash spec + schemas + routers + tests into one commit.
- No secrets in code. Confirm `.env.example` has any new vars P3 introduces (it shouldn't — P3 is pure domain CRUD with no new external integrations).
- Maintain `docs/SESSION_LOG.md` and `docs/VERIFICATION.md` as you go (see "Living docs" section below).

# Phase 3 scope — what to build

**Goal**: HC can manage clients, sessions, MOMs (manual text — no LLM yet), briefs (manual text), action items, and check-ins. All HC routes scoped by JWT `hc_id`. All `/api/me/*` routes scoped by JWT `sub`.

## HC-facing endpoints (require_role("hc") + current_tenant())

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/clients` | Create client |
| POST | `/api/clients/{id}/invite` | Generate one-time invite token for client signup |
| GET | `/api/clients` | List own clients (paginated) |
| GET | `/api/clients/{id}` | Client detail (AST stub at this phase — full AST is P5) |
| POST | `/api/sessions` | Create session for a client |
| POST | `/api/sessions/{id}/end` | End session (P3: just sets `ended_at`; MOM auto-draft is P4) |
| GET | `/api/sessions/{id}/brief` | Get brief (P3: returns existing brief or 404; generation is P5) |
| GET | `/api/sessions/{id}/mom` | Get MOM (any status, HC-scoped) |
| PATCH | `/api/sessions/{id}/mom` | Edit MOM body (HC) |
| POST | `/api/sessions/{id}/mom/send` | Transition `draft` → `sent` (snippet capture is P4 — P3 just flips status) |
| POST | `/api/action-items` | Create action item |
| PATCH | `/api/action-items/{id}` | Update action item state (`open` → `in_progress` → `completed` / `missed`) |
| GET | `/api/clients/{id}/check-ins` | List a client's check-ins |
| PATCH | `/api/check-ins/{id}/flag` | Manually flag check-in (sentiment placeholder) |

## Client-facing endpoints (require_role("client"))

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/me/moms` | List own MOMs where `status='sent'` only |
| GET | `/api/me/moms/{id}` | Read sent MOM (404 if `status` ≠ `sent` — even if owned) |
| GET | `/api/me/action-items` | List own action items |
| PATCH | `/api/me/action-items/{id}` | Mark complete/in-progress (own only) |
| POST | `/api/me/check-ins` | Submit check-in |

The client-facing OAuth completion endpoint (`POST /api/auth/google/callback` with invite token) was scaffolded in P2 — you may need to wire the invite-token verification path here in P3 if it wasn't completed. Confirm against `src/auth/router.py` before assuming.

## Recommended file structure

```
backend/src/
└── api/
    ├── __init__.py
    ├── clients.py
    ├── sessions.py
    ├── moms.py
    ├── briefs.py
    ├── action_items.py
    ├── check_ins.py
    └── me.py            # /api/me/* client-facing routes
```

Each as an `APIRouter`, registered in `src/main.py`. Pydantic request/response schemas alongside (e.g., `clients.py` defines `ClientCreate`, `ClientOut`, `ClientList`, etc., or split into `schemas/` if it gets long).

# Known gotchas for P3 (must be honored from day 1)

1. **Tenant scoping in EVERY HC query.** Failure = data leak between coaches. Anthem rule says this is non-negotiable. Pattern from HANDOVER-P3.md:
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
       # EVERY query MUST filter by hc_id
       result = await db.execute(select(Client).where(Client.hc_id == hc_id))
       ...
   ```
   Add an integration test for **every HC endpoint** that asserts cross-tenant access returns 404 (not 403 — return 404 to avoid leaking existence).

2. **Coach-reviewed gate.** Per `domain/glossary.md` and the build-plan: `mom.status` ∈ {`draft`, `reviewed`, `sent`}. The client-facing API returns `status='sent'` only. `status='draft'` or `'reviewed'` → 404 even when owned by the requesting client. Test this explicitly with a client-role JWT.

3. **`/api/me/*` filters by `sub` (the user_id), NOT `hc_id`.** A client doesn't have an `hc_id` claim in their JWT — they have their own user_id in `sub`, and the client record has its own `hc_id` field that points to their HC. Don't confuse the two. The dependency for `/api/me/*` is `require_role("client")`, and the filter is on `Client.user_id == claims.sub` (or whatever the FK to users is — verify against the data model).

4. **Pagination on all list endpoints.** Build-plan acceptance criterion: "List with 25+ items → first page + cursor returned." Cursor-based or page/limit, your call — pick one and apply it consistently across all GET-list routes. Document the choice in the spec.

5. **Soft-delete on sessions with sent MOMs.** Build-plan edge case: HC tries to delete a session that has a sent MOM → soft-delete only (`deleted_at` set), MOM preserved. Hard-delete is the DPDP path, not this one. P3 should at minimum return 409 or soft-delete; full DPDP deletion path is P9-adjacent.

6. **Action item due date — open question, default to manual entry.** Build-plan flagged this as an open question owned by SoJo "by end of P3." Default if undecided: manual entry, no auto-default. Honor that default. Note it in the spec under "Open questions" so it's revisitable.

7. **Invite token flow.** `POST /api/clients/{id}/invite` generates a one-time token. Store it hashed (SHA256) like refresh tokens. TTL 30 days per build-plan edge case. The client's OAuth callback in P2 was supposed to handle the invite-token completion — verify wiring; if it was stubbed, complete it here.

8. **All httpx through `make_http_client()`.** No new external integrations in P3, but if any sneak in (e.g., for invite email — though we're not sending email at MVP), use the factory. Run `grep -r "httpx.AsyncClient(" backend/src | grep -v lib/http.py` at the end of P3 — output must be empty.

9. **`get_settings()` not `settings`.** Same as P0–P2.

10. **Absolute imports** (`from src.api.clients import ...`, not relative).

# Open questions to honor (with defaults)

These came from `docs/build-plan.md` "Open questions" section. SoJo has confirmed: **use the defaults below**. Note each in the spec's "Open questions" section so they're revisitable.

- **Action item due date**: manual entry, no auto-default to "next session."
- (Snippet edit threshold and M000 brief content are P4/P5 questions, ignore for P3.)

# MCP: confirm Postgres MCP is reachable before any DB-touching test

Per `starter_prompt_01.md`, the Postgres MCP Pro server should be installed via pipx and registered in `.claude/mcp_servers.json` (or wherever this Claude Code version expects it). Verify reachable before P3 verification queries:

1. Run a trivial schema-introspection query through the MCP (e.g., `\dt` equivalent — list tables).
2. Confirm read-only mode is enforced (a `INSERT` or `UPDATE` attempt should fail).
3. If unreachable or write-capable, **stop and produce a `## Context missing` block**. Do not fall back to raw `psql`. The MCP being read-only is a safety property.

# Living docs — maintain as you go

SoJo will not be reading every commit. They WILL read `SESSION_LOG.md` and `VERIFICATION.md` between sessions. Keep both current.

## `docs/SESSION_LOG.md` (append-only, latest at top)

At the end of P3 (and any sub-milestone you reach), append an entry per the existing format. Specifically:

```
## YYYY-MM-DD — P3: Domain CRUD

**Done**:
- [bullet per major sub-task]

**Decided** (link ADRs / specs):
- [any decision that emerged mid-session]

**Bugs fixed mid-session**:
- [any]

**Pending / next session**:
- P4: LLM Service
- [any P3 carry-overs]

**Context the next session needs**:
- [paths to source docs P4 needs]

**Open questions for SoJo**:
- [any]
```

## `docs/VERIFICATION.md` (manual checklist for SoJo)

This is what SoJo uses to verify your work outside the session. At the end of P3, append a section like:

```
## P3 — Domain CRUD verification

### Setup
- [ ] `cd backend && uv run pytest -v` → all tests pass (target: ~60+)
- [ ] `uvicorn` boots without errors: `DATABASE_URL=... uv run uvicorn src.main:app --reload`
- [ ] OpenAPI docs reachable: `http://localhost:8000/docs` lists all P3 endpoints

### HC endpoints
- [ ] Create client: `curl -X POST .../api/clients -H "Authorization: Bearer <hc1_jwt>" -d '{...}'` → 201
- [ ] List clients as HC1, then as HC2: HC2 sees zero of HC1's clients
- [ ] Cross-tenant: HC1 tries to GET HC2's client by ID → 404
- [ ] Create session for client → list sessions → confirm shape
- [ ] Create MOM (status='draft') → PATCH → POST /send → status='sent'
- [ ] List with 25+ clients → first page + cursor returned

### Client endpoints
- [ ] As client, GET /api/me/moms with one draft + one sent MOM → only sent is returned
- [ ] As client, GET /api/me/moms/{draft_id} → 404
- [ ] As client, GET /api/me/moms/{sent_id} → 200
- [ ] Action item: HC creates → client lists → client PATCHes to in_progress → HC sees update

### Tenant scoping (the blast-radius check)
- [ ] grep -r "Session(" backend/src returns only async usage
- [ ] grep -r "httpx.AsyncClient(" backend/src | grep -v lib/http.py returns nothing
- [ ] Spot-check 3 random HC endpoints: visible filter by hc_id in the query
- [ ] No /api/me/* endpoint references hc_id from the JWT (clients don't have one)

### Edge cases
- [ ] Soft-delete: HC tries to delete session with sent MOM → soft-delete or 409
- [ ] Invite token: generate → use → second use of same token rejected
- [ ] Pagination: cursor from page 1 returns page 2 correctly; invalid cursor → 400
```

SoJo will tick these manually before authorizing P4.

# Phase verification format (your closing summary)

When you believe P3 is complete, produce:

## P3 verification summary

For each acceptance criterion in `docs/build-plan.md` Phase 3:

- [✓] `<criterion>`: <how I verified — command run, output observed>
- [✗] `<criterion>`: <what's blocking>
- [-] `<criterion>`: <why skipped, with rationale>

Then **STOP**. Do not start P4. SoJo will run `VERIFICATION.md` independently and confirm.

# Definition of done for P3

- All HC and client endpoints listed above implemented and registered in `main.py`
- Pydantic schemas for every request and response (no raw dicts in route signatures)
- Tenant scoping verified by integration test on every HC endpoint
- Coach-reviewed gate verified by integration test on `/api/me/moms/{id}`
- Pagination working on all list endpoints with explicit test for >25 items
- Spec at `docs/specs/0003-domain-crud.md`, status: `Approved` (after SoJo confirms — start as `Draft`)
- All tests passing (`uv run pytest -v` from `backend/`)
- `SESSION_LOG.md` updated
- `VERIFICATION.md` updated with P3 manual-check section
- Conventional commits, one logical change per commit
- No `httpx.AsyncClient(` outside `src/lib/http.py`
- No raw `Session(` (sync) usage in `src/`
- No `localStorage` / `sessionStorage` / browser-storage references (N/A for backend, but flag if any frontend snippet sneaks in)

# Start

Begin with a preflight block covering this whole session. Then read the prep documents listed above (in order). Then produce the source-doc consistency report. Then write `docs/specs/0003-domain-crud.md` per `skill-write-spec.md` and present it for SoJo's review **before** writing any router code. Wait for confirmation on the spec before implementation.
