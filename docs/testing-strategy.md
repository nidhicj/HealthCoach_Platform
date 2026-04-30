# Testing Strategy

> What we test, how, and when. Covers code tests, LLM evals, and manual verification.

---

## Three layers

### 1. Unit tests (`backend/tests/unit/`)

**What**: pure functions, single-class behavior, no I/O.

**Examples**:
- Snippet selection logic given a fixed set of snippets
- JWT validation logic (with fixture keys)
- Pydantic model validation edge cases
- Diff logic for HC edits to AI drafts

**Run**: `uv run pytest backend/tests/unit/` — should complete in seconds.

**Coverage target**: > 80% on business logic files (`domain/`, `llm/validators.py`, etc.). Not enforced as a gate at MVP, but tracked.

### 2. Integration tests (`backend/tests/integration/`)

**What**: API endpoints with real DB (test instance), mocked external services (OpenRouter, Google OAuth).

**Examples**:
- POST `/api/sessions` creates a session, MOM draft generated (mocked LLM), all DB rows created
- Auth flow: valid Google token → JWT issued → JWT used on protected endpoint
- Tenant scoping: HC A cannot see HC B's clients
- Cascade delete: deleting a client purges all snippets, MOMs, briefs
- `coach-reviewed gate`: client-facing endpoint never returns `status='draft'` content

**Run**: `uv run pytest backend/tests/integration/` — slower; use `pytest-asyncio` with a dedicated test DB.

**Setup**: Docker-Compose with Postgres for local; test DB in a CI environment.

### 3. LLM evals (`backend/tests/llm_evals/`)

**What**: outputs of LLM calls against expected qualities. **Separate from unit/integration** because:
- Slow (real API calls)
- Non-deterministic
- Expensive (small but real)
- Different success criteria (quality, not strict equality)

**Examples**:
- MOM generation: given a sample transcript + snippets, does the MOM contain expected sections (action items, key decisions)?
- Pre-session brief: does it correctly identify triage flags from input data?
- Pydantic validation rate: across N test cases, what % validate on first attempt?

**Run**: not on every commit. Run on:
- Changes to prompts (`prompts/` directory)
- Changes to LLM chain (`llm/chains.py`)
- Changes to snippet selection logic
- Pre-release sanity check

**Tooling**: `promptfoo` or similar; results stored in `archive/llm-eval-runs/YYYY-MM-DD/`. **Action item**: pick eval framework before first LLM endpoint ships.

---

## What we do NOT unit-test

- Framework code (FastAPI middleware behavior — trust the framework)
- ORM-level CRUD (trust SQLAlchemy)
- Pure UI rendering (covered by manual verification at MVP scale)

---

## Manual verification (MVP)

Until E2E tests exist (post-MVP), every meaningful change ends with manual smoke:

1. Local dev runs cleanly (`pywrangler dev` + `npm run dev`)
2. The specific change works as intended (use the actual UI)
3. The smoke flow works:
   - Sign in
   - Create a client
   - Create a session
   - Generate a MOM (LLM call)
   - HC edit, send
   - Snippet captured

Document any deviations.

---

## Frontend testing

**MVP**: minimal. No Jest/Playwright at MVP — manual verification covers the small surface. Add when:
- A bug recurs in the same UI flow twice → write a test
- A flow becomes complex enough that manual verification takes > 5 minutes

---

## CI gating

**MVP minimum**:
- Unit tests must pass on every push to main
- Integration tests must pass on every PR
- LLM evals run on prompt-touching PRs

**Not in MVP**:
- Coverage threshold gate
- Performance benchmarks
- Mutation testing

---

## Test data

- Never use real client data in tests
- Fixtures: `backend/tests/fixtures/`
- Seed scripts: `scripts/seed-pilot-hc.py` for local dev (creates a fake HC + 2 fake clients + sample sessions)

---

## References

- `decisions/0003-llm-strategy.md` §2 — Pydantic validation as the gate
- `decisions/0004-repo-structure.md` — where tests live

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-28 | Initial draft. |
