# Health Coach Platform

> SaaS for independent Indian health coaches. Onboarding clients, AI-assisted session workflows (MOM, briefs, action items), between-session check-ins. AI drafts; HC reviews and sends. India-first, DPDP-aware.

---

## Status

**Pre-launch.** Building MVP for pilot HC. See `docs/SESSION_LOG.md` for current state.

---

## Stack at a glance

- **Backend**: FastAPI on Cloudflare Python Workers (open beta). Fallback: DigitalOcean Bangalore.
- **Frontend**: Next.js 15 on Cloudflare Pages.
- **Database**: AWS RDS Postgres, Mumbai.
- **Storage**: AWS S3, Mumbai.
- **LLM**: OpenRouter gateway with pinned free-model chain (Llama 3.3 → Gemma 3 → GPT-OSS → Nemotron). Migration to paid Claude on triggers.
- **Auth**: Google OAuth → owned JWT.
- **Observability**: Sentry + Cloudflare Logs + custom `llm_calls` telemetry.

Full stack rationale: `docs/decisions/0001-stack-selection.md`.

---

## Run locally

### Prerequisites

- Python 3.12 (managed via `uv`)
- Node 20+
- Docker (for local Postgres)
- Cloudflare account (Free tier sufficient for dev)

### Backend

```bash
cd backend
uv sync                                  # install Python deps
cp .dev.vars.example .dev.vars           # populate with your dev secrets
docker compose up -d postgres            # start local Postgres
uv run alembic upgrade head              # apply migrations
uv run pywrangler dev                    # start Worker locally
```

Backend runs at `http://localhost:8787`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local               # populate
npm run dev
```

Frontend runs at `http://localhost:3000`.

### Smoke test

After both are running:

1. Visit `http://localhost:3000` — sign in with Google
2. Create a client → create a session → trigger MOM draft
3. Verify in `psql` that `llm_calls` row was written

If anything fails, the smoke-test gate in ADR-0001 (open follow-ups) defines the expected pass criteria.

---

## Project layout

```
product/
├── backend/        # FastAPI + Pyodide on Cloudflare Workers
├── frontend/       # Next.js 15 on Cloudflare Pages
├── prompts/        # Versioned LLM prompts
├── docs/           # ADRs, specs, domain notes, ops runbooks
├── scripts/        # Admin scripts (seed, etc.)
├── archive/        # Superseded content
├── .claude/        # Claude Code workspace config
└── .claude-project/ # claude.ai Project sync (optional)
```

Detailed layout and conventions: `docs/decisions/0004-repo-structure.md`.

---

## Key documents

| For | See |
|---|---|
| Why we picked this stack | `docs/decisions/0001-stack-selection.md` |
| When to split runtimes vs. migrate to DO | `docs/decisions/0002-runtime-topology.md` |
| LLM strategy (model selection, snippets, validation) | `docs/decisions/0003-llm-strategy.md` |
| Folder layout, naming | `docs/decisions/0004-repo-structure.md` |
| Auth (JWT, Google OAuth, sessions) | `docs/decisions/0005-auth-strategy.md` |
| Observability (Sentry, logs, llm_calls) | `docs/decisions/0006-observability.md` |
| Terms (HC, MOM, AST, snippet, etc.) | `docs/domain/glossary.md` |
| Who can do what | `docs/domain/actors.md` |
| DPDP and compliance posture | `docs/domain/compliance-india.md` |
| System architecture | `docs/diagrams/0001-system-architecture.md` |
| Database schema | `docs/diagrams/0002-data-model.md` |
| Branching, commits, conventions | `docs/standards/CONTRIBUTING.md` |
| Test layers and gating | `docs/standards/testing-strategy.md` |

---

## Contributing

Solo project at MVP. Process notes in `docs/standards/CONTRIBUTING.md`.

---

## License

Proprietary. All rights reserved. (Re-evaluate if open-sourcing components becomes useful.)

---

## Contact

Owner: SoJo. (Internal-only at MVP.)
