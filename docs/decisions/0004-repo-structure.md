# ADR-0004: Repo Structure

**Status**: Accepted
**Date**: 2026-04-28
**Decision driver**: SoJo (solo founder)
**Supersedes**: n/a
**Relates to**: ADR-0001 (one-repo-dual-config principle)

> **Numbering note**: this ADR was originally queued as ADR-0002 (repo structure). The runtime-topology question (now ADR-0002) and the LLM-strategy ADR (ADR-0003, deferred from ADR-0001) took those slots. Repo structure becomes ADR-0004.

---

## Context

ADR-0001 settled stack and the **one-repo, two-configurations** principle. ADR-0002 settled runtime topology. ADR-0003 settled LLM strategy. None of those settled where files actually go.

This ADR settles:
- Top-level folder layout
- Where backend, frontend, prompts, docs, archive, tooling live
- Naming conventions (kebab-case files, snake_case Python, etc.)
- What goes in `.claude/` and `.claude-project/`
- What's gitignored

---

## Decision

```
product/
├── README.md                          # entry point — overview, run-locally, key links
├── CLAUDE.md                          # operating contract (root copy, mirrors Project knowledge)
├── PREFLIGHT.md                       # preflight reference
├── CONTRIBUTING.md                    # commit conventions, branching, PR template
├── pyproject.toml                     # backend Python deps (uv-managed)
├── package.json                       # frontend deps (one workspace; backend has none)
├── .env.example                       # secrets template (no values)
├── .gitignore
├── .wranglerignore                    # excludes .venv etc. from Worker bundle (workers-py #92)
│
├── backend/
│   ├── pyproject.toml                 # if Python deps live here instead of root, pick one
│   ├── pywrangler.toml OR wrangler.toml
│   ├── src/
│   │   ├── main.py                    # FastAPI app entry
│   │   ├── config.py                  # env-driven settings (pydantic-settings)
│   │   ├── auth/                      # JWT + Google OAuth
│   │   ├── api/                       # FastAPI routers
│   │   │   ├── coaches.py
│   │   │   ├── clients.py
│   │   │   ├── sessions.py
│   │   │   └── ...
│   │   ├── domain/                    # business logic; framework-agnostic
│   │   │   ├── hc_cycle.py
│   │   │   ├── snippets.py
│   │   │   └── ...
│   │   ├── llm/                       # OpenRouter client, prompt assembly, validation
│   │   │   ├── client.py
│   │   │   ├── chains.py              # the pinned model chain config
│   │   │   ├── validators.py          # Pydantic models for parsed outputs
│   │   │   └── snippets.py            # snippet selection
│   │   ├── db/
│   │   │   ├── models.py              # SQLAlchemy 2.0 models
│   │   │   ├── session.py             # async session factory
│   │   │   └── migrations/            # Alembic
│   │   ├── jobs/                      # external-scheduler-triggered endpoints + handlers
│   │   └── telemetry/                 # llm_calls writer, structured logging helpers
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── llm_evals/                 # LLM eval harness (separate from regular tests)
│
├── frontend/
│   ├── next.config.js
│   ├── src/
│   │   ├── app/                       # Next.js 15 App Router
│   │   ├── components/
│   │   │   └── ui/                    # shadcn/ui components
│   │   ├── lib/                       # API client, auth helpers, utils
│   │   └── styles/
│   └── public/
│
├── prompts/                           # versioned prompts (markdown files)
│   ├── mom-generation.md
│   ├── pre-session-brief.md
│   ├── action-items.md
│   └── ...
│
├── docs/
│   ├── PROJECT-INDEX.md               # what's authoritative for what
│   ├── SESSION_LOG.md                 # session handoff log
│   ├── decisions/                     # ADRs
│   │   ├── 0000-template.md
│   │   ├── 0001-stack-selection.md
│   │   ├── 0002-runtime-topology.md
│   │   ├── 0003-llm-strategy.md
│   │   └── 0004-repo-structure.md
│   ├── specs/                         # feature specs (Unit_NNN_PascalCaseName/ structure)
│   │   ├── 0000-template_SPEC.md
│   │   └── Unit_001_HcCoreCycle/
│   │       ├── SPEC-0001-hc-core-cycle.md
│   │       └── SPEC-0002-llm-service.md
│   ├── domain/
│   │   ├── glossary.md
│   │   ├── actors.md
│   │   └── compliance-india.md
│   ├── diagrams/
│   │   ├── 0001-system-architecture.md
│   │   └── 0002-data-model.md
│   ├── ops/
│   │   ├── cloudflare-cost-reference.md
│   │   ├── secrets-management.md
│   │   ├── deployment.md
│   │   ├── backup-restore.md
│   │   └── incident-response.md
│   ├── legal/
│   │   ├── privacy-policy.md          # NEEDS LAWYER REVIEW
│   │   └── terms-of-service.md        # NEEDS LAWYER REVIEW
│   └── testing-strategy.md
│
├── scripts/                           # ad-hoc admin scripts
│   ├── seed-pilot-hc.py
│   └── ...
│
├── archive/                           # superseded files; never deleted
│   ├── n8n-onboarding-brief.md        # killed pre-decision; kept for traceability
│   └── ...
│
├── .claude/                           # Claude Code workspace
│   ├── skills/                        # repo-scoped skills
│   ├── mcp_servers.json               # repo-scoped MCP config (Postgres, GitHub, Sentry)
│   └── settings.local.json            # local Claude Code settings (gitignored)
│
└── .claude-project/                   # claude.ai Project mirror (optional, for sync)
    └── ...
```

---

## Naming conventions

| Thing | Convention | Example |
|---|---|---|
| Markdown files | `kebab-case.md` | `compliance-india.md`, `secrets-management.md` |
| ADR / spec files | `NNNN-kebab-case.md` (zero-padded) | `0002-runtime-topology.md` |
| Python modules | `snake_case.py` | `hc_cycle.py`, `llm_calls.py` |
| Python classes | `PascalCase` | `SnippetSelector`, `LlmCall` |
| TypeScript files | `kebab-case.ts` for utilities, `PascalCase.tsx` for components | `api-client.ts`, `SessionList.tsx` |
| Database tables | `snake_case`, plural | `users`, `hc_style_snippets`, `llm_calls` |
| Database columns | `snake_case` | `created_at`, `hc_user_id` |
| Env vars | `SCREAMING_SNAKE_CASE` | `OPENROUTER_API_KEY`, `DATABASE_URL` |
| Branches (git) | `kind/short-description` | `feat/snippet-selection`, `fix/httpx-ua-header` |

---

## What's gitignored

```
# Secrets
.env
.env.local
*.pem
*.key

# Python
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Node
node_modules/
.next/
dist/

# Cloudflare / Wrangler
.wrangler/
.dev.vars

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Claude
.claude/settings.local.json
```

`.env.example` is committed (with placeholder values, no real secrets). `.wranglerignore` is committed.

---

## Why this layout

1. **Top-level `backend/` and `frontend/` mirror the deploy targets.** Cloudflare Workers builds from `backend/`; Cloudflare Pages builds from `frontend/`. CI/CD knows which directory triggered which deploy.
2. **`prompts/` is top-level, not buried.** Prompts are first-class artifacts (per ADR-0003). Versioning them with the rest of the code matters; hiding them in `backend/src/llm/prompts/` makes them feel implementation-detail. They are not.
3. **`docs/` mirrors Project knowledge.** The same files exist in claude.ai Project knowledge for thinking and in `docs/` for the repo. Single source of truth via `PROJECT-INDEX.md`.
4. **`archive/` instead of deleting.** Killed work (n8n brief, superseded specs, etc.) goes here. Keeps traceability for "why didn't we do X?" without polluting active dirs.
5. **`.claude/` separate from `.claude-project/`.** Claude Code's workspace config lives in `.claude/`. claude.ai Project metadata (if synced) lives in `.claude-project/`. Distinct surfaces, distinct dirs, no collision.

---

## Consequences

### What this enables
- Claude Code knows where to put new files without asking each time.
- New ADR / spec / prompt has a deterministic location.
- Deploy pipelines have clean directory boundaries.

### What this costs
- Some file types could plausibly live in two places (e.g., a domain model file — `backend/src/domain/` or `backend/src/db/`). The convention: **`db/models.py` is the SQLAlchemy ORM layer; `domain/` is framework-agnostic logic that operates on those models.** If a file feels ambiguous, prefer `domain/`.
- Schema drift between Project knowledge `docs/` and repo `docs/` is possible. Mitigation: when claude.ai produces a new doc, it goes through Claude Code commit; Project knowledge is updated by re-uploading.

### Things to revisit
- **Monorepo vs. polyrepo**: this decision is monorepo. If/when frontend and backend deploy cycles diverge significantly, revisit.
- **`prompts/` location**: if prompts grow into a complex retrieval system with embeddings, may need its own service / package boundary.

---

## References

- `decisions/0001-stack-selection.md` — one-repo-dual-config principle
- `decisions/0003-llm-strategy.md` — why `prompts/` is top-level

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-28 | Initial draft, Accepted. |
