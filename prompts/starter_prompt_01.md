We are starting the build. Scope of this session: Phase 0 (Repo Scaffolding) → Phase 1 (Data Layer) → Phase 2 (Auth Service), per `docs/build-plan.md`. Stop at the end of P2 — do not start P3. We will verify each phase before moving to the next.

# Mandatory preparation (before writing any code)

1. Read `CLAUDE.md` (root) and `PREFLIGHT.md` in full. The anthem and the preflight block are non-negotiable for every substantive response.
2. Read `docs/REPO-INDEX.md` to understand what lives where.
3. Read `docs/build-plan.md` sections "Overall build shape," "Phase 0," "Phase 1," "Phase 2," and the "Traceability matrix."
4. Read every source doc the matrix marks as primary (●) or secondary (○) for P0, P1, P2:
   - `docs/decisions/0001-stack-selection.md` (full read — primary for P0)
   - `docs/decisions/0002-runtime-topology.md` (Cloudflare platform constraints)
   - `docs/decisions/0003-llm-strategy.md` (skim — `llm_calls` schema is referenced by P1)
   - `docs/decisions/0004-repo-structure.md` (full read — primary for P0)
   - `docs/decisions/0005-auth-strategy.md` (full read — primary for P2; defines `auth_refresh_tokens` schema needed in P1)
   - `docs/decisions/0006-observability.md` (skim — touches P1 logging conventions and PII rules that must be honored from day 1)
   - `docs/diagrams/0002-data-model.md` (full read — primary for P1)
   - `docs/domain/glossary.md` and `docs/domain/actors.md` (terminology and role model)
   - `docs/testing-strategy.md` (apply from P0 — test infra is part of scaffolding)
   - `CONTRIBUTING.md` (commit conventions, branching)

If any referenced document is missing or contradicts another, stop and produce a `## Context missing` block per anthem rule 7. Do not guess.

# Operating rules for this session

- Run a preflight block (per `PREFLIGHT.md`) before every substantive response — including before each phase starts.
- Verify before claiming done. "It should work" is banned (anthem rule 14). Run the actual command, hit the actual endpoint, query the actual DB.
- One phase at a time. At the end of each phase, produce a verification summary (checkbox-by-checkbox against the build-plan's acceptance criteria for that phase) and STOP. Wait for SoJo to confirm before starting the next phase.
- Commit per `CONTRIBUTING.md` conventions. Conventional commits, one logical change per commit.
- No secrets in code. `.env.example` and `.dev.vars.example` carry placeholders only. `.env` and `.dev.vars` are gitignored.

# Known gotchas (must be honored from day 1)

- **`workers-py` #68 (httpx UA)**: every `httpx` client must set an explicit `User-Agent` header. Per ADR-0001, route all httpx instantiation through a single factory function (`backend/src/lib/http.py`'s `make_http_client()`). Add a grep-based pre-commit hook or a CI check that flags raw `httpx.AsyncClient(` usage outside the factory.
- **`workers-py` #92 (.wranglerignore)**: `.wranglerignore` must exclude `.venv` (and any other dev-only directories) so they don't ship in the Worker bundle.
- **Async-only DB access**: per ADR-0001 Consequence #3, every DB call uses `asyncpg` via SQLAlchemy 2.0 `AsyncSession`. No sync `Session`, no `psycopg2`. P1 acceptance includes `grep -r "Session(" backend/src` returning only async usage.
- **PII redaction in logs**: per ADR-0006 §3, snippet content, transcript content, MOM content, full email/phone/name, JWT tokens, refresh tokens must never appear in logs. Even at P0–P2 scaffolding, the structured logger must be set up with the `scrub()` function from day one.
- **Tenant scoping**: every domain query in P3+ filters by `hc_id` from the JWT. P2 builds the `current_tenant()` FastAPI dependency that makes this enforceable. Do not ship `current_tenant()` without an integration test that asserts cross-tenant access is denied.
- **`auth_refresh_tokens` table**: schema is defined in ADR-0005 §10, **not** currently in `docs/diagrams/0002-data-model.md`. As part of P1, (a) include this table in the SQLAlchemy models and the first migration, AND (b) update `docs/diagrams/0002-data-model.md` to reflect the new table — Mermaid block, walkthrough prose, and Changelog entry per `CLAUDE.md` §7 "Diagram maintenance rules."

# Local environment

- Python: python 3.12.3 version  managed via `uv` in the `backend/` directory.
- Activate the backend virtualenv before any Python command: `cd backend && source /mnt/hdd/yourProjects/venv/hc_pf/bin/python3` (or run via `uv run <cmd>`).
- Node: 20+ for `frontend/`.
- Local Postgres: via `docker compose up -d postgres` (compose file created in P0).

# MCP: Postgres (read-only) — install before any DB work

The **Postgres MCP Pro** server is installed into the Python environment via `pipx`, not into the backend virtualenv. This keeps the dev tool isolated from project deps.

Steps (run before P1 starts; P0 does not require it):

1. Confirm `pipx` is available: `pipx --version`. If missing, install via `python -m pip install --user pipx && python -m pipx ensurepath`, then restart shell.
2. Verify install: `pipx list` should show the package and its entry-point command.
3. Register the server in `.claude/mcp_servers.json` (or via `claude mcp add`, whichever this Claude Code version supports — check `claude mcp --help` first). Connection string points at the local Postgres from docker-compose; credentials come from `.dev.vars` (never hardcoded).
4. Mark it read-only in the MCP config. Schema introspection and SELECT only — no writes. All schema changes go through Alembic, not the MCP.
5. Confirm the MCP is reachable from inside the Claude Code session before using it for verification queries.

If `pipx` is unavailable, the Postgres MCP install fails, or the connection cannot be verified, produce a `## Context missing` block and stop — do not fall back to running raw `psql` for verification, and do not skip P1 cascade tests.

# Phase verification format

At the end of P0, P1, and P2, produce a section like:

## Phase N verification summary

For each acceptance criterion in `docs/build-plan.md` Phase N:

- [✓] `<criterion>`: <how I verified — command run, output observed>
- [✗] `<criterion>`: <what's blocking>
- [-] `<criterion>`: <why skipped, with rationale>

Then STOP. SoJo will run the criteria independently and confirm before P(N+1) starts.

# Start

Begin with a preflight block covering this whole session. Then read the prep documents listed above. Then propose your P0 plan (files to create, in what order, what tests, what commit boundaries) for confirmation before writing any code.
