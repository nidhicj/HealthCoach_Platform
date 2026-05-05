# PHASE-00: Repo Scaffolding

**Unit**: Unit_001_HcCoreCycle
**Status**: Complete | Partially verified
**Verification date**: 2026-05-01 (automated suite green; Cloudflare Worker and Next.js manual steps pending — see `docs/VERIFICATION.md` § P0)
**Implements**: Pre-condition for all SPEC-0001 phases — scaffolding establishes the repo, dev environment, and conventions every subsequent phase depends on
**ADRs implemented**: ADR-0001 (stack selection), ADR-0004 (repo structure), ADR-0006 (observability scaffolding posture)

---

## 1. Scope

Phase 0 created the empty-but-correct repo structure: the FastAPI Worker boots, the Next.js frontend skeleton boots, local Postgres is up, and all dev-environment conventions are locked in. No domain code was written. The goal was a correctly-shaped foundation that subsequent phases could build on without revisiting tooling decisions.

P0, P1, and P2 were all delivered in a single session on 2026-05-01 (`prompts/starter_prompt_01.md`). The phase boundary in this document reflects the logical split, not a separate calendar session.

## 2. Deliverables shipped

Drawn from SESSION_LOG 2026-05-01.

- `git init` — repository initialised
- `backend/pyproject.toml` — PEP 735 `[dependency-groups]` structure; FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, httpx, asyncpg, python-jose listed
- `docker-compose.yml` — local Postgres service
- `.env.example` — all env vars documented with placeholders; no secrets
- `backend/src/main.py` — FastAPI app with CORS middleware, request-ID middleware, `/healthz` endpoint returning `{"status":"ok","version":"0.1.0"}`
- `backend/src/telemetry/scrub.py` — `scrub()` PII redaction function and `get_logger()` factory; Sentry stub (per ADR-0006 scaffolding posture: wire the hook, fill it in P8)
- `backend/src/lib/http.py` — `make_http_client()` factory enforcing `User-Agent` header (workers-py #68 workaround; per ADR-0001 constraint)
- `frontend/` — Next.js 16 skeleton bootstrapped via `create-next-app` (App Router)
- `CONTRIBUTING.md` — dev commands: `uv sync`, `uv run`, `docker-compose`, `npm`
- `backend/.venv` — symlinked to `/mnt/hdd/yourProjects/venv/hc_pf` (single shared Python env; not a project-local venv)
- `.gitignore` — `.env`, `.dev.vars`, `node_modules`, `.venv`, `__pycache__`, `*.pyc`, `.pytest_cache`, `.wranglerignore` artifacts
- `backend/src/config.py` — Pydantic Settings class; all config consumed via `get_settings()` singleton (not raw `os.environ`)
- `CONTRIBUTING.md` — conventional commits, no `--no-verify`, branch naming, PR template

**Known gotchas addressed at scaffold time** (from `prompts/starter_prompt_01.md`):

- `workers-py` #68 — raw `httpx.AsyncClient(` without a `User-Agent` header breaks inside Cloudflare Workers. Addressed by `make_http_client()` factory from day one; all subsequent code (P2 OAuth, P4 LLM) routes through it.
- `workers-py` #92 — `.wranglerignore` must exclude `.venv` (and other dev dirs) so they don't ship in the Worker bundle. Per ADR-0004 decision, `.wranglerignore` lives at repo root.
- **Async-only DB** — per ADR-0001 Consequence #3, no sync `Session` or `psycopg2` anywhere; enforced by `AsyncSession`-only types in P1.
- **PII redaction from day one** — `scrub()` is in place so P1+ logging never accidentally leaks health content or tokens, even in dev.

## 3. Decisions made during this phase

- **`.venv` as symlink to shared env** — `backend/.venv` points to `/mnt/hdd/yourProjects/venv/hc_pf` rather than a project-local virtualenv. This avoids per-project env duplication on the dev machine. `.venv/` is gitignored; activation command is `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate`.
- **ADR-0003 flipped to Accepted before P1 coding started** — the LLM strategy ADR was advanced from Draft to Accepted at the P0/P1 boundary so that the P1 data model could incorporate the `llm_calls` schema that ADR-0003 defines. No P0 code depends on ADR-0003; it is recorded here because the flip happened in this session.

## 4. Bugs fixed mid-phase

None recorded for P0 specifically. Bugs encountered during the P0/P1/P2 session are attributed to P1 and P2 below.

## 5. Source docs consulted

Per `prompts/starter_prompt_01.md` mandatory preparation:

- `docs/decisions/0001-stack-selection.md` — full read; language, framework, hosting, AI gateway, model chain; the known-gotchas list (`workers-py` #68, #92) drove P0 implementation choices
- `docs/decisions/0002-runtime-topology.md` — Cloudflare Workers runtime constraints: no threads, no native crypto, Web Crypto API only; shaped how `make_http_client()` and JWT signing must work
- `docs/decisions/0004-repo-structure.md` — full read; top-level folder layout, what goes in `.claude/`, naming conventions (kebab-case files, snake_case Python)
- `docs/decisions/0006-observability.md` — skim; PII rules (what must never reach logs) and the Sentry stub posture
- `docs/domain/glossary.md` and `docs/domain/actors.md` — terminology and role model for the product being scaffolded
- `docs/testing-strategy.md` — test infra setup is part of P0 scaffolding; async pytest config established here (then fixed in P1 — see PHASE-01 §4)

## 6. Verification

- **Verification date**: 2026-05-01
- **Verification record**: `docs/VERIFICATION.md` § P0 — Repo Scaffolding
- **Status**: Partially verified — unit tests pass; Cloudflare Worker (`wrangler dev`) and Next.js (`npm run dev`) manual checks were marked "pending" in the verification table
- **Test count at end of phase**: Not separately tracked for P0; P1 inherited 0 domain tests and bootstrapped from here

## 7. Lessons learned

- **Factory pattern from day one paid off in P4.** The `make_http_client()` factory established in P0 meant that when P4's LLM service needed a 120-second timeout and specific headers, there was one place to update — not scattered `httpx.AsyncClient()` calls.
- **`scrub()` as an extension point.** Starting the telemetry scaffold in P0 with a `scrub()` function meant P4 could add `prompt_text` and `completion_text` to the PII key set without touching the logging infrastructure.
- **Sentry stub is the right posture.** Wiring the Sentry import and init call in P0 (even as a no-op stub) means P8 has a well-defined socket to plug into rather than a retrofit.
- **Partial verification on P0 is acceptable.** Worker deployment and Node frontend boots are environment-dependent steps; testing them in isolation would have gated P1/P2 unnecessarily. The automated suite + healthz endpoint was sufficient to proceed.
- **`config.py` via Pydantic Settings from day one.** Having `get_settings()` as the single source for env config meant every subsequent phase (P2 JWT keys, P4 encryption key, P4 OpenRouter key) had a predictable, typed place to declare new settings. No `os.environ.get()` scattered through the codebase.
- **Node 22 requirement should have been in CONTRIBUTING.md.** Node version was discovered as a blocker only when the frontend was first run. The workaround (`export PATH=~/.nvm/versions/node/v22.15.1/bin:$PATH`) was documented in SESSION_LOG but not yet in CONTRIBUTING.md. Worth adding before P6.

## 8. Carry-over to subsequent phases

- `make_http_client()` factory — used by auth module (P2) and LLM service (P4)
- `scrub()` / `get_logger()` — extended in P4 with additional PII keys (`prompt_text`, `completion_text`)
- Sentry stub — scheduled for live wiring in P8
- `CONTRIBUTING.md` dev commands — referenced by all subsequent phases and the VERIFICATION.md manual steps
- `backend/.venv` symlink convention — every subsequent session activates with `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate`, not `source backend/.venv/bin/activate`
- Node 22 requirement for frontend (`export PATH=~/.nvm/versions/node/v22.15.1/bin:$PATH`) — documented for P6 frontend work
