We are continuing the build. Scope of this session: **Phase 4 (LLM Service)** only, per `docs/build-plan.md`. Stop at the end of P4 — do not start P5. P0–P3 are complete (107/107 tests passing) and P3 manual verification is done (see `docs/VERIFICATION.md`).

# Mandatory preparation (before writing any code)

1. Read `CLAUDE.md` (root) and `PREFLIGHT.md` in full. The anthem and the preflight block are non-negotiable for every substantive response in this session.
2. Read `HANDOVER-P3.md` (root) and the most recent `docs/SESSION_LOG.md` entry (2026-05-02 — P3). These together are your authoritative current state. P3 added: `users.role` column, `clients.user_id` (FK to users for client OAuth linking), `sessions.deleted_at` (soft-delete), `client_invite_tokens` table, `src/api/deps.py` shared dependency module, full `src/api/` router suite. Migration `60775f9338d3` is the latest.
3. Read `docs/build-plan.md` Phase 4 section in full, plus the "How to use this when working with Claude Code" and "Traceability matrix" sections.
4. Read every primary (●) and secondary (○) source doc the matrix marks for P4:
   - `docs/decisions/0003-llm-strategy.md` (full read — primary). Defines the model chain rationale, fallback semantics, prompt versioning, and the `llm_calls` schema. The schema landed in P1 with fields: `model_requested`, `model_served`, `prompt_version`, `request_id`. Verify ADR-0003's text matches this.
   - `docs/decisions/0001-stack-selection.md` (skim — secondary). For OpenRouter-as-LLM-provider rationale and the no-training/no-retention header requirement.
   - `docs/decisions/0006-observability.md` (full read — secondary). PII redaction rules apply directly to LLM prompts, completions, and the `llm_calls` table.
   - `docs/diagrams/0002-data-model.md` — for `llm_calls`, `hc_style_snippets` (note `retired_at` column added in P1), `moms`, `briefs` field shapes.
   - `docs/domain/glossary.md` — for terminology (snippet, AST, MOM, brief, prompt version, model chain).
5. Read `docs/specs/` to confirm prior specs and check for any existing P4 spec stub. If `0004-llm-service.md` already exists, extend it; if not, you'll write it as the first step (see "Spec first" below).

If any referenced document is missing, contradicts another, or contradicts the SESSION_LOG.md entry, **stop and produce a `## Context missing` block** per anthem rule 7. Do not guess. Do not pick a winner silently between conflicting docs.

# Source-doc consistency check (do this before writing any code)

After reading the source docs, produce a short report:
- "Source docs consistent: [yes / no]"
- If no: list each contradiction. SoJo will resolve before you proceed.
- Specifically confirm:
  - (a) `llm_calls` schema in the data model diagram matches ADR-0003: `model_requested`, `model_served`, `prompt_version`, `request_id`, success/failure capture
  - (b) `hc_style_snippets` table has `retired_at` column (added in P1)
  - (c) ADR-0003's stated model chain (Llama 3.3 70B → Gemma 3 → GPT-OSS → Nemotron) — note in your report that SoJo has explicitly marked these as **placeholders** subject to change. Do NOT fail consistency if these specific models are unavailable on OpenRouter; instead, see "OpenRouter model chain verification" below.

# OpenRouter model chain verification (before writing the LLM client)

The model chain in ADR-0003 is treated as a **placeholder**. SoJo's standing instruction: **the model chain must live in a config file, not in code, so it can be updated without code changes.**

Your task before writing the OpenRouter client:

1. With `OPENROUTER_API_KEY` set in `.env` (already populated by SoJo), make a real call to `GET https://openrouter.ai/api/v1/models` via `make_http_client()`. List the available models that match the ADR-0003 chain (or close substitutes if those slugs are deprecated/renamed).
2. Produce a short report: "ADR-0003 model chain availability on OpenRouter: [chain]." Flag any model in the chain that is not currently available with a recommended substitute.
3. **Do not amend ADR-0003** to swap models. Instead: design the `llm_config` file (see below) such that the chain is editable without touching ADR-0003 at all. ADR-0003 documents the *strategy* (chain-with-fallback, prompt versioning, no-training-headers); the `llm_config` documents the *current chain values*.

If `GET /v1/models` fails (auth error, network), stop and produce a `## Context missing` block. Do not proceed with hardcoded slugs.

# Operating rules for this session

- Run a preflight block (per `PREFLIGHT.md`) before every substantive response. Compressed (3 lines) is fine for tight follow-ups; full preflight before each new sub-task (spec, llm_config, OpenRouter client, prompt files, schemas, validation loop, snippet capture, snippet injection, integration tests).
- **Spec first, code second.** Anthem rule 9. Before any LLM service code, write `docs/specs/0004-llm-service.md` per `template-spec.md` and `skill-write-spec.md`. Get SoJo's confirmation on the spec before writing implementation code. The spec is not optional and is not a write-up-after-the-fact.
  - The spec MUST include a "Decisions to make" section that surfaces the open design questions listed below (snippet selection algorithm; PII redaction policy in `llm_calls`). Each must be resolved with SoJo before the code that depends on it is written.
- Verify before claiming done. "It should work" is banned (rule 14). Run pytest, hit OpenRouter for real (with the populated key), inspect the resulting `llm_calls` row in the DB via the Postgres MCP. The Postgres MCP (read-only) is available — use it for verification queries; never as a fallback to skip writing tests.
- Commit per `CONTRIBUTING.md`. Conventional commits, one logical change per commit. Don't squash spec + config + client + prompts + schemas + retry loop + snippet capture into one commit.
- No secrets in code. `OPENROUTER_API_KEY` already populated; confirm it loads cleanly via `get_settings()` from BOTH `backend/` working directory AND `backend/tests/` working directory. (P3 found `env_file=".env"` only worked from one location — fix was `(".env", "../.env")`. P4's tests will exercise this same lookup; if OpenRouter calls 401 in tests but work in dev, this is the cause.)
- Maintain `docs/SESSION_LOG.md` and `docs/VERIFICATION.md` as you go (see "Living docs" section below).

# Phase 4 scope — what to build

**Goal**: LLM drafts work end-to-end. MOM and brief drafting via OpenRouter chain-with-fallback. Snippet capture on HC edits. Snippet injection into prompts. Every LLM call writes one `llm_calls` row.

## Deliverables

### 1. `backend/src/llm_service/` module

```
backend/src/llm_service/
├── __init__.py
├── config.py              # llm_config — model chain, snippet thresholds, token budgets
├── client.py              # OpenRouter wrapper using make_http_client()
├── chain.py               # try-fallback iteration over model chain
├── retry.py               # validation retry loop (1 retry on stricter format hint)
├── snippets.py            # capture (HC edit → row) + select (top-N within token budget)
├── prompts.py             # prompt-file loader (YAML frontmatter parsing)
└── tracking.py            # write llm_calls row on every call (success or failure)
```

### 2. `backend/src/llm_service/config.py` (or `.yaml` — your call, document in spec)

A SoJo-editable file containing:

- **Model chain** (list of OpenRouter slugs, primary → fallbacks). Editable without code changes.
- **Snippet diff threshold**: 5 (characters minimum for an edit to be captured as a snippet)
- **Snippet whitespace filter**: True (whitespace-only diffs filtered out)
- **Snippet token budget**: 2000 (max tokens of snippet content injected into a prompt)
- **Snippet selection N**: configurable upper bound on count regardless of token budget
- **Per-prompt-type model overrides** if needed (e.g., MOM vs brief might use different chains — your call, propose in spec)
- **Validation retry count**: 1
- **No-training/no-retention OpenRouter headers** to inject on every call

The file is read at module init. Changes require app restart but no code changes. Document this clearly in the spec — SoJo will need to know how to update the chain when models change.

### 3. Prompt files in `backend/prompts/`

```
backend/prompts/
├── mom_draft.md           # MOM draft generation
├── brief_assemble.md      # Pre-session brief generation
└── ai_assist.md           # Generic in-session assist (per build-plan)
```

Each with **YAML frontmatter**:
```yaml
---
version: "1.0.0"
created: "2026-05-02"
notes: "Initial draft. Conservative tone, structured output."
---
[prompt body]
```

The `version` field is the value that lands in `llm_calls.prompt_version`. Bumping the prompt = bumping the version = a new row of historical calls easily separable.

### 4. Pydantic output schemas in `backend/src/llm_service/schemas/`

```
backend/src/llm_service/schemas/
├── __init__.py
├── mom.py                 # structured MOM output (sections, action items, follow-ups)
├── brief.py               # structured brief output (AST view, suggested topics)
└── action_items.py        # structured action item extraction
```

Each schema is what the LLM is required to return. Validation is enforced; on validation failure, the retry loop (config.validation_retry_count = 1) re-prompts with a stricter format hint before giving up.

### 5. Snippet capture (on HC edit)

When HC PATCHes a MOM (or brief — applies to both):
- Compute diff between LLM's draft and HC's saved version
- Apply config thresholds (length, whitespace)
- Each surviving diff segment becomes one `hc_style_snippets` row
- `retired_at` column from P1 stays NULL on creation; retirement logic is OUT OF SCOPE for P4 — note in spec, defer to P5 or later

### 6. Snippet injection (on next prompt)

When generating any prompt for an HC:
- Query `hc_style_snippets` for that HC where `retired_at IS NULL`, ordered by recency
- Select top-N within 2K-token budget (algorithm: SoJo wants Claude Code to propose in spec; default to "most recent first, count tokens, stop when budget exceeded")
- Inject as system prompt examples per ADR-0003

### 7. `llm_calls` row on every call (success or failure)

Per ADR-0003:
- `model_requested`: the slug we tried (chain head)
- `model_served`: the slug that actually returned (could be a fallback)
- `prompt_version`: from the prompt file's YAML frontmatter
- `request_id`: from FastAPI request middleware
- Plus: prompt content, completion content, latency, status, token counts, cost
- Failures (4xx, 5xx, validation rejection after retry) ALSO get rows. The table is the audit log.

PII redaction in this table: see "Open question — PII in llm_calls" below.

# Open questions to resolve in the spec (before implementation)

These two questions came from the P4 prep conversation. Resolve them in `docs/specs/0004-llm-service.md` "Decisions to make" section. SoJo will review the spec and decide before any code that depends on these is written.

## A. Snippet selection algorithm (within 2K-token budget)

**Default proposal**: most recent first by `created_at`, count tokens, stop when adding the next snippet would exceed 2K. Snippets where `retired_at IS NOT NULL` are excluded.

Surface in the spec:
- This default
- Alternative: weighted by recency × frequency-of-edit-pattern
- Tradeoffs: simplicity vs. quality of style learning at scale

SoJo will pick. Default is fine for P4; alternatives may surface as P6+ optimization.

## B. PII redaction policy in `llm_calls` table (and prompt logs)

ADR-0006 mandates redaction in **logs**. The question is whether the same redaction applies to the `llm_calls` table itself, which stores prompts and completions.

Surface in the spec, with explicit tradeoffs:
- **Option A: store as-is in `llm_calls`** — same DB, same tenant, same DPDP boundary as MOMs themselves. PII redaction ONLY in stdout/structured logs. Pros: trivially debuggable, exact LLM input/output preserved for audit. Cons: backup/replica exfil increases blast radius.
- **Option B: redact in `llm_calls`** — apply `scrub()` (or equivalent) to prompt and completion before write. Pros: defense in depth, smaller blast radius. Cons: harder to debug LLM behavior; can't replay an exact prompt; complicates correctness verification.
- **Option C: hybrid** — store full content in `llm_calls`, but with column-level encryption at rest (PostgreSQL `pgcrypto`) for the prompt/completion fields. Pros: middle ground. Cons: implementation cost; key management; debugging requires decryption step.

Recommend Option A for P4 with an explicit migration path to B or C if/when audit findings demand it. Note in `docs/decisions/` if the choice is material — this may warrant ADR-0007.

# Known gotchas for P4 (must be honored from day 1)

1. **All httpx through `make_http_client()`.** P3 didn't exercise this much; P4 does for every OpenRouter call. Verify at end: `grep -r "httpx.AsyncClient(" backend/src | grep -v lib/http.py` returns empty.

2. **No-training / no-retention OpenRouter headers** on every request. Per ADR-0001 (and `make_http_client` should already enforce baseline headers — but explicitly add OpenRouter's privacy headers per their docs). Confirm against current OpenRouter API documentation; flag in source-doc consistency report if ADR-0001 conflicts.

3. **`model_requested` vs `model_served` distinction matters.** When the chain falls back from primary to secondary, `model_requested` is the primary (what we asked for), `model_served` is the secondary (what actually returned). Don't conflate. Don't only write the success model.

4. **Every call writes a row, INCLUDING failures.** Network error → row. Validation rejection after retry → row. 401 from OpenRouter → row. The table is the audit log of LLM activity, not just successful generations. Test this explicitly: an integration test that intentionally fails a call and asserts the row exists.

5. **`prompt_version` is sourced from the prompt file's YAML frontmatter, not hardcoded.** Bumping a prompt = updating the file's `version` field. The loader reads it; the call propagates it; the row records it. Test that an explicit prompt-version bump shows up in a new row.

6. **Snippet diff capture must run on the actual edit, not on send.** The diff is computed when HC PATCHes the MOM (between current saved draft and incoming text), not when HC POSTs to /send. P3's MOM PATCH endpoint is the trigger point.

7. **PII redaction in logs.** Per ADR-0006: snippet content, transcript content, MOM content, full email/phone/name, JWT/refresh tokens never appear in stdout/structured logs. The `scrub()` function from P0/telemetry must be invoked on any log line that touches these. P4 generates a LOT of LLM-prompt-shaped log lines; this is where ADR-0006 violations are most likely. Add a unit test that runs a prompt through the logger and asserts no PII in the output.

8. **`llm_config` file is hot-swappable but requires restart.** SoJo can edit the file and restart the app to swap models. No code change. Document this in the spec and the file itself (a header comment).

9. **`env_file` lookup gotcha from P3.** `OPENROUTER_API_KEY` must be reachable from `backend/` (uvicorn) AND `backend/tests/` (pytest). The fix from P3 (`env_file=(".env", "../.env")` in pydantic-settings) should already be in place — verify by running an integration test that calls OpenRouter, not just unit tests with mocked keys.

10. **Tenant scoping still applies.** Snippets, llm_calls, MOMs are all per-HC. When selecting snippets for prompt injection, the query must filter by `hc_id` from the JWT — same pattern as P3. Cross-tenant snippet contamination would be a serious data leak. Test explicitly.

11. **`get_settings()` not `settings`.** Same as P0–P3.

12. **Absolute imports** (`from src.llm_service.client import ...`).

13. **`uv run` for everything.** Same as P0–P3.

14. **Test isolation: savepoints.** P3 upgraded `conftest.py` to use savepoint-based isolation (`join_transaction_mode="create_savepoint"`). P4 tests inherit this; don't fight it. Each test runs in a savepoint that rolls back at end-of-test. LLM tests that need to assert `llm_calls` rows wrote correctly should query INSIDE the savepoint, not after.

# MCP: confirm Postgres MCP is reachable before any DB-touching test

Already verified for P3. Verify still reachable at start of P4 (read-only schema introspection). If it has drifted (e.g., new tables not visible after P3 migration), refresh the MCP's schema cache.

# Living docs — maintain as you go

SoJo will not be reading every commit. They WILL read `SESSION_LOG.md` and `VERIFICATION.md` between sessions. Keep both current.

## `docs/SESSION_LOG.md` (append-only, latest at top)

At the end of P4 (and any sub-milestone you reach), append a new entry per the existing format. Specifically:

```
## YYYY-MM-DD — P4: LLM Service

**Done**:
- [bullet per major sub-task]

**Decided** (link ADRs / specs):
- Snippet selection algorithm: [chosen]
- PII redaction policy in llm_calls: [chosen, with rationale]
- llm_config file location and shape
- Prompt versioning convention
- [any decision that emerged mid-session]

**Bugs fixed mid-session**:
- [any]

**P4 status**: ✅ complete — manual verification passed YYYY-MM-DD (or ⏳ awaiting verification)

**Pending / next session**:
- P5: HC Cycle Workflows
- [any P4 carry-overs]

**Context the next session needs**:
- Source docs P5 will need
- Any new patterns established in P4 (e.g., how prompts are loaded, how llm_config is read)

**Open questions for SoJo**:
- [any]
```

## `docs/VERIFICATION.md` (manual checklist for SoJo)

This is what SoJo uses to verify your work outside the session. At the end of P4, append a section like:

```
## P4 — LLM Service verification

### Setup
- [ ] `cd backend && uv run pytest -v` → all tests pass (target: ~130+)
- [ ] `OPENROUTER_API_KEY` populated in `.env` and reachable from `backend/`
- [ ] Postgres MCP read-only mode confirmed
- [ ] `llm_config` file exists at documented path; comment header explains how to update

### OpenRouter chain
- [ ] `GET /v1/models` returns 200 with current key
- [ ] Chain head model is callable (manual test: trivial completion request)
- [ ] Chain fallback fires when primary model returns error (test by temporarily breaking primary slug in config)
- [ ] No-training/no-retention headers present in actual OpenRouter requests (capture via httpx hook or proxy)

### MOM draft generation (end-to-end)
- [ ] Trigger MOM auto-draft on session end
- [ ] Resulting MOM has status='draft', body populated by LLM
- [ ] One `llm_calls` row written with `model_requested`, `model_served`, `prompt_version`, `request_id`, prompt, completion, latency, success
- [ ] PII not present in stdout logs from this call (per ADR-0006)

### Snippet capture
- [ ] HC PATCHes MOM with substantive edit (>5 chars, not whitespace) → at least one `hc_style_snippets` row
- [ ] HC PATCHes with whitespace-only edit → no snippet row
- [ ] HC PATCHes with <5 char edit → no snippet row
- [ ] Cross-tenant: HC2 cannot see HC1's snippets via any endpoint

### Snippet injection
- [ ] HC with N snippets → next MOM draft prompt contains snippets in system prompt
- [ ] Snippet token budget honored: HC with very long snippets → budget enforced (check via captured prompt)
- [ ] HC with zero snippets → prompt still works (fallback to base prompt)

### Validation retry
- [ ] LLM returns invalid JSON → retry fires once with stricter format hint
- [ ] Retry succeeds → MOM created with valid output
- [ ] Retry fails → failure row in `llm_calls`, error surfaced cleanly

### Prompt versioning
- [ ] Bump version in a prompt file → next call records the new version in `llm_calls`
- [ ] Prompt file with malformed YAML → error at load time, not at first request

### Failure path coverage
- [ ] OpenRouter 401 → `llm_calls` row with status=failure, error captured
- [ ] OpenRouter timeout → row written, error captured
- [ ] All chain models fail → row(s) written, user-facing error surfaced

### Grep hygiene
- [ ] grep -r "httpx.AsyncClient(" backend/src | grep -v lib/http.py → empty
- [ ] grep for hardcoded model slugs in src/ → only in `llm_config`, not in client.py / chain.py
- [ ] grep for raw API key in src/ → only via `get_settings()`
```

SoJo will tick these manually before authorizing P5.

# Two-stage completion: Claude Code's "done" vs SoJo's "done"

P4 is NOT complete when you finish coding and your tests pass. P4 is complete only when SoJo has run the manual verification in `VERIFICATION.md` and confirmed every checkbox. There are two stages and they are explicit:

## Stage 1 — Claude Code declares "ready for manual verification"

This is when:
- All P4 deliverables implemented (module structure, llm_config, prompts, schemas, retry, snippets, tracking)
- All automated tests pass (`uv run pytest -v`)
- Spec at `docs/specs/0004-llm-service.md` reviewed and approved by SoJo
- Decisions A and B above resolved by SoJo and reflected in code/config
- `SESSION_LOG.md` updated with what was done in this session
- `VERIFICATION.md` updated with the full P4 manual-check section

When all of the above are true, produce the `## P4 verification summary` (the in-session check format). At the end of that summary, write — verbatim — this line:

> **P4 is ready for SoJo's manual verification. Not complete until manual verification passes. Awaiting confirmation before any P5 work begins.**

Then STOP. Do not commit anything new. Do not draft P5 anything. Wait.

## Stage 2 — SoJo runs manual verification

SoJo opens `docs/VERIFICATION.md`, runs each check, and reports back. Three possible outcomes:

**Outcome A — All checks pass.** SoJo says "P4 verified, proceed to P5." That's the only sentence that ends P4. Until you hear that or its equivalent, P4 is not done.

**Outcome B — Some checks fail.** SoJo lists the failures. You fix them in this same session: write a failing test that reproduces each issue, fix the code, confirm green, update `VERIFICATION.md` with what was found and resolved, then re-issue the "ready for manual verification" message. Repeat until Outcome A.

**Outcome C — Manual verification surfaces a spec-level gap.** Update `docs/specs/0004-llm-service.md` with the gap, decide with SoJo whether to fix in P4 or defer to a later phase, and proceed accordingly. Do not silently absorb scope.

Failures from manual verification are NOT "a P5 problem." They are P4 not being done yet.

# Phase verification format (your closing summary)

When you believe P4 is ready for manual verification, produce:

## P4 verification summary

For each acceptance criterion in `docs/build-plan.md` Phase 4:

- [✓] `<criterion>`: <how I verified — command run, output observed>
- [✗] `<criterion>`: <what's blocking>
- [-] `<criterion>`: <why skipped, with rationale>

Then the verbatim handoff line above. Then STOP.

# Definition of done for P4 (Stage 1)

- `backend/src/llm_service/` module shipped with all submodules listed
- `llm_config` file exists at documented path, model chain editable without code changes
- `backend/prompts/` directory with at least `mom_draft.md`, `brief_assemble.md`, `ai_assist.md` — each with valid YAML frontmatter
- Pydantic output schemas for MOM, brief, action items
- Validation retry loop implemented (1 retry on stricter format hint)
- `llm_calls` row written on every call, including failures
- Snippet capture working on HC PATCH of MOM (and brief if applicable)
- Snippet injection working on next prompt for that HC, with token budget enforced
- PII redaction in logs verified by unit test
- All tests passing (`uv run pytest -v` from `backend/`)
- Spec at `docs/specs/0004-llm-service.md`, status: `Approved` (after SoJo confirms — start as `Draft`)
- Open questions A (snippet selection) and B (PII in llm_calls) resolved by SoJo and reflected in implementation
- `SESSION_LOG.md` updated
- `VERIFICATION.md` updated with P4 manual-check section
- Conventional commits, one logical change per commit
- No `httpx.AsyncClient(` outside `src/lib/http.py`
- No hardcoded model slugs outside `llm_config`
- No raw `OPENROUTER_API_KEY` references outside `get_settings()`

# Start

Begin with a preflight block covering this whole session. Then:

1. Read the prep documents listed above (in order)
2. Produce the source-doc consistency report
3. Produce the OpenRouter model chain availability report (real `GET /v1/models` call)
4. Write `docs/specs/0004-llm-service.md` per `skill-write-spec.md` — including the "Decisions to make" section with Open questions A and B
5. Present the spec for SoJo's review **before** writing any implementation code
6. Wait for SoJo's confirmation on the spec AND resolution of A and B before implementation
