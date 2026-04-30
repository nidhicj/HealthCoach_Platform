# Contributing

> Solo project at MVP. These are notes-to-future-self about how the work happens. Will get more formal when a second contributor joins.

---

## Branching

- `main` — always deployable. Production deploys from here.
- Feature branches: `feat/short-description`
- Fix branches: `fix/short-description`
- Refactor: `refactor/short-description`
- Docs only: `docs/short-description`

Branch off `main`. Merge back to `main` via PR even when solo (forces `git diff` review of your own work).

---

## Commits

Conventional Commits format:

```
<type>(<scope>): <subject>

<optional body>

<optional footer>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `ci`, `style`.

Scopes commonly used: `backend`, `frontend`, `db`, `llm`, `auth`, `prompts`, `docs`.

Examples:

```
feat(llm): add Pydantic validation retry on first failure
fix(auth): set User-Agent header on httpx (workers-py #68)
docs(adr): accept ADR-0002 runtime topology
```

---

## PR review (self-review checklist)

Before merging your own PR:

- [ ] CI green (tests + lint)
- [ ] Manual smoke pass per `docs/testing-strategy.md`
- [ ] No secrets in diff (grep for known patterns)
- [ ] If adding a feature: spec exists in `docs/specs/`
- [ ] If making a tradeoff: ADR exists or amended
- [ ] If touching DB: migration is reversible
- [ ] Commit messages follow convention
- [ ] No `# PROTOTYPE-ONLY:` comments left in code paths that aren't documented as prototype-only

---

## When to write what

| Trigger | Write |
|---|---|
| Decision with consequences | ADR in `docs/decisions/` |
| New feature being designed | Spec in `docs/specs/` |
| Pattern emerges | Skill in `.claude/skills/` |
| Domain term used inconsistently | Update `docs/domain/glossary.md` |
| Operational lesson learned | Runbook entry in `docs/ops/` |

---

## Code style

- **Python**: ruff for lint and format; type hints required on public functions; Pydantic models for boundaries.
- **TypeScript**: ESLint + Prettier; strict mode on; no `any` without comment.
- **SQL**: lowercase keywords (`select`), snake_case identifiers, explicit joins (no implicit `,`).
- **Comments**: explain *why*, not *what*. Code shows what.

---

## Surface awareness

Per Project rules:
- Planning, ADRs, specs, decisions: in claude.ai Project (this repo's `docs/` mirrors Project knowledge)
- Code, migrations, deploys: in Claude Code (this repo)

Don't write production code in claude.ai. Don't write strategic docs solo in Claude Code without claude.ai discussion.

---

## Local dev commands

### Backend

```bash
cd backend

# Install / sync deps into hc_pf venv (backend/.venv is a symlink)
uv sync

# Run tests
uv run pytest

# Lint / type-check
uv run ruff check src tests
uv run mypy src

# Run Cloudflare Worker locally (requires Node 22 — use nvm)
PATH="$HOME/.nvm/versions/node/v22.15.1/bin:$PATH" wrangler dev
# → boots on http://localhost:8787
```

### Frontend

```bash
cd frontend

# Install deps (requires Node 22)
PATH="$HOME/.nvm/versions/node/v22.15.1/bin:$PATH" npm install

# Dev server
PATH="$HOME/.nvm/versions/node/v22.15.1/bin:$PATH" npm run dev
# → http://localhost:3000

# Production build (static export)
PATH="$HOME/.nvm/versions/node/v22.15.1/bin:$PATH" npm run build
```

> **Node version**: system Node is 18; Node 22 is under `~/.nvm/versions/node/v22.15.1/`. Frontend and wrangler both require Node ≥ 20. Prepend the PATH line above or add an `.nvmrc` file to auto-switch.

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-28 | Initial. |
| 2026-04-30 | Added local dev commands; documented venv symlink and Node 22 requirement. |
