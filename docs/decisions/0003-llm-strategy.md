# ADR-0003: LLM Strategy Principles — Model Selection, Validation, Snippets, Telemetry

**Status**: Accepted
**Date**: 2026-04-28
**Decision driver**: SoJo (solo founder)
**Supersedes**: n/a
**Relates to**: ADR-0001 §LLM model chain, §Snippet library — this ADR makes those operational

---

## Context

ADR-0001 settled the LLM gateway (OpenRouter), the pinned free-model fallback chain, the snippet library architecture, and the migration triggers to paid Claude. What ADR-0001 *deferred* to this ADR:

- Model-selection criteria — when do we use the primary vs. the reasoning escape hatch?
- Output validation patterns — what gets validated, how, what happens on failure
- Fallback orchestration — how OpenRouter's `models` array is configured and tested
- Telemetry schema — concrete `llm_calls` table fields and indexing
- Snippet library mechanics — extraction triggers, retrieval/selection algorithm, expiration policy, batch jobs

This ADR codifies these as principles + concrete implementation pointers. It does not prescribe code; it prescribes the engineering surface that the spec and code must satisfy.

---

## Decision summary

| Area                   | Principle                                                                                                                                                          |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Model routing          | Primary model handles all default coaching outputs. Reasoning escape hatch (`deepseek/deepseek-r1:free`) called explicitly by application code, never automatic. |
| Output validation      | Every LLM output that downstream code parses goes through Pydantic. One retry on validation failure with stricter format hint, then fail loudly to telemetry.      |
| Fallback orchestration | OpenRouter's built-in `models` array. No custom retry loops. Chain order pinned per ADR-0001.                                                                    |
| Telemetry              | `llm_calls` table with concrete schema below. Required for every LLM call.                                                                                       |
| Snippet capture        | MVP: HC edits to AI drafts only. Other snippet types (key exchanges, stylistic patterns) deferred.                                                                 |
| Snippet selection      | MVP: recency-weighted, top-N, ~2K token cap. Embedding-based retrieval deferred.                                                                                   |
| Snippet privacy        | `client_id` foreign key with cascade-on-delete. Single-transaction purge on consent revocation.                                                                  |

---

## Principles

### 1. Model selection — primary first, reasoning explicit

The pinned chain in ADR-0001 (Llama 3.3 70B → Gemma 3 27B → GPT-OSS-120B → Nemotron-3 Super) handles **all default coaching outputs**: MOM, pre-session briefs, action items, summaries.

The reasoning escape hatch (DeepSeek R1) is **never in the automatic chain**. It is called only by application code that explicitly determines a task needs step-by-step reasoning. Examples where it might be called:

- Multi-step planning (e.g., generating a 4-week meal plan that respects N constraints)
- Conflict resolution between contradictory client signals
- Diagnosis-style logic (only ever for HC review, never for client-facing output)

Reasoning calls cost ~5–10× more output tokens than non-reasoning calls. They are slower. They are the exception, not the default.

### 2. Output validation — Pydantic is the gate

Every LLM output that downstream code parses must go through a Pydantic model. The model defines the contract; the LLM either satisfies it or it doesn't.

**Failure path**:

1. Validation fails on first attempt.
2. Re-prompt with the same content + a stricter format hint (one sentence: e.g., "Return ONLY valid JSON matching this schema, no prose."). Single retry.
3. If retry also fails: log to `llm_calls` with `validation_failed=true`, `fallback_count` incremented, return a graceful error to the caller (not a 500; a structured "draft unavailable" state the HC can see).

**`validation_failed` rate is a tracked metric** — ADR-0001 trigger #8 fires migration to paid Claude if this exceeds 5% over a 7-day rolling window.

### 3. Fallback orchestration — let OpenRouter do it

OpenRouter's request payload includes a `models` array. The first model is tried; on upstream throttling or model-deprecation errors, the next is tried automatically. **We do not write custom retry loops at the application layer.**

Application-layer retry is reserved for **validation failures only** (one retry, stricter prompt). Network-layer / provider-side retry is OpenRouter's job.

The chain order is pinned per ADR-0001. Changing chain composition requires an ADR amendment.

### 4. Telemetry — `llm_calls` is mandatory, not optional

Every LLM call writes one row to `llm_calls`. No exceptions. This is the data foundation for every cost, quality, and reliability decision downstream.

**Schema (concrete)**:

```sql
CREATE TABLE llm_calls (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hc_user_id        UUID NOT NULL REFERENCES users(id),
    client_id         UUID REFERENCES clients(id),       -- nullable: not all calls are client-scoped
    session_id        UUID REFERENCES sessions(id),      -- nullable
    request_id        UUID,                              -- FastAPI request_id for tracing
    use_case          TEXT NOT NULL,                     -- 'mom_generation', 'brief_generation', 'action_items', etc.
    prompt_version    TEXT NOT NULL,                     -- e.g., 'mom_v2' — semver string, pinned in code
    model_requested   TEXT NOT NULL,                     -- first model in chain e.g., 'meta-llama/llama-3.3-70b-instruct:free'
    model_served      TEXT,                              -- actual model that responded (may differ if fallback)
    fallback_count    INTEGER NOT NULL DEFAULT 0,        -- how many models in the chain were tried before success
    input_tokens      INTEGER NOT NULL,
    output_tokens     INTEGER NOT NULL,
    latency_ms        INTEGER NOT NULL,
    validation_failed BOOLEAN NOT NULL DEFAULT FALSE,
    snippet_count     INTEGER NOT NULL DEFAULT 0,        -- how many snippets were injected
    snippet_tokens    INTEGER NOT NULL DEFAULT 0,        -- token count of injected snippets
    inr_cost_estimate NUMERIC(10, 4),                    -- nullable: ~0 for free models, real value for paid
    raw_request_id    TEXT,                              -- OpenRouter request ID for support tickets
    error_message     TEXT,                              -- nullable: populated on hard failure
    prompt_text       BYTEA,                             -- pgp_sym_encrypt(<assembled prompt>, key); pseudonymized — see ADR-0006 §5 amendment 2026-05-04
    completion_text   BYTEA                              -- pgp_sym_encrypt(<raw LLM response>, key); written before HC edits
);

CREATE INDEX idx_llm_calls_created_at ON llm_calls (created_at DESC);
CREATE INDEX idx_llm_calls_hc_use_case ON llm_calls (hc_user_id, use_case);
CREATE INDEX idx_llm_calls_validation_failed ON llm_calls (validation_failed) WHERE validation_failed = TRUE;
```

**Encryption note** (added 2026-05-04 amendment): `prompt_text` and `completion_text` are stored as `BYTEA` containing the output of `pgp_sym_encrypt(plaintext, current_setting('app.llm_call_encryption_key'))`. Reads use `pgp_sym_decrypt` and are tenant-scoped per ADR-0006 §5. The encryption key is sourced from env var `LLM_CALL_ENCRYPTION_KEY` and injected into the session via `SET LOCAL` at the start of each query that needs to decrypt. Key rotation is out of scope for P4.

**Pseudonymization note** (added 2026-05-04 amendment): `prompt_text` content references clients by `clients.code` (per-HC `CP<NNNN>`), never by name/email/phone. The `clients` table gains a `code` column for this purpose; values are stable once assigned. The prompt-assembly module is the single chokepoint enforcing this; a unit test asserts no client-name strings appear in stored `prompt_text`. See ADR-0006 §5 amendment for the full policy.

**Retention**: 1 year per ADR-0006 §9 (overrides earlier "indefinite during MVP" framing — amended 2026-05-04). Encrypted prompt and completion content (`prompt_text`, `completion_text`) is in scope for retention; rows older than 1 year are purged by the scheduled job referenced in ADR-0006 §9. **DPDP note**: with the 2026-05-04 amendment, `llm_calls` now contains personal data (encrypted, pseudonymized — but still personal data under DPDP). It is in scope for consent-revocation deletion; see §7 below.

### 5. Snippet capture — MVP is HC edits only

ADR-0001 names three snippet types: HC edits, key exchanges, stylistic patterns. **MVP captures only HC edits.**

**Why**: edits are mechanically captured (diff between AI draft and HC-sent version). Key exchanges and stylistic patterns require heuristics that will be wrong some of the time, costing trust early when there's no signal to tune them on.

**Capture trigger**: any time the HC modifies an AI-produced output (MOM, brief, action item) before sending. Mechanism:

- AI draft is stored when generated (`drafts` table, schema in ADR-0004 / spec)
- HC's final-sent version is captured when sent
- If the two differ beyond whitespace, write a snippet row of type `edit`

**Schema sketch** (full schema in `diagrams/0002-data-model.md`):

```sql
CREATE TABLE hc_style_snippets (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hc_user_id        UUID NOT NULL REFERENCES users(id),
    client_id         UUID REFERENCES clients(id),  -- nullable, but enforced where applicable for deletion traceability
    snippet_type      TEXT NOT NULL CHECK (snippet_type IN ('edit', 'exchange', 'pattern')),
    original_text     TEXT NOT NULL,                -- AI draft, or original exchange
    hc_modified_text  TEXT,                         -- nullable for non-edit snippets
    context_summary   TEXT,                         -- short LLM-generated summary of when/why this came up
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at      TIMESTAMPTZ,                  -- updated when snippet is selected for injection
    relevance_tags    TEXT[],                       -- e.g., ['stress_eating', 'water_intake', 'rapport']
    use_count         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_snippets_hc_user_id ON hc_style_snippets (hc_user_id);
CREATE INDEX idx_snippets_client_id ON hc_style_snippets (client_id);
CREATE INDEX idx_snippets_last_used ON hc_style_snippets (hc_user_id, last_used_at DESC NULLS LAST);
```

### 6. Snippet selection — MVP is recency-weighted top-N

When assembling a system prompt, select snippets:

1. **Filter** to snippets where `hc_user_id` matches and (if applicable) `client_id` matches the current session's client.
2. **Rank** by `last_used_at` DESC, NULLS first (unused recent snippets get priority over recently-injected ones — gives variety).
3. **Take top N** until token budget (~2K tokens) is hit.
4. **Update `last_used_at` and `use_count`** for selected snippets.

**Why this works at MVP**: simple, deterministic, debuggable. Embeddings + similarity search is better but premature until we have hundreds of snippets per HC.

**Token budget configurable per use-case** in code: MOM generation might allow 2K, action-item extraction 500. Default 2K.

### 7. Snippet privacy — purge on consent revocation

Every snippet that references a specific client must have `client_id` populated. Consent revocation runs:

```sql
BEGIN;
DELETE FROM llm_calls WHERE client_id = $revoked_client_id;       -- added 2026-05-04 amendment: encrypted prompt_text/completion_text rows
DELETE FROM hc_style_snippets WHERE client_id = $revoked_client_id;
DELETE FROM sessions WHERE client_id = $revoked_client_id;
-- ... other client-scoped tables ...
DELETE FROM clients WHERE id = $revoked_client_id;
COMMIT;
```

Foreign keys with `ON DELETE CASCADE` on every client-scoped table make this safe even if some FKs are missed in app code. **Test coverage**: a deletion test suite that asserts no orphaned rows remain after a `DELETE FROM clients WHERE id = X`. The 2026-05-04 amendment requires this test suite to explicitly verify `llm_calls` rows are deleted (the encrypted columns make this less obviously a deletion target on quick inspection).

---

## Consequences

### What this enables

- LLM behavior is observable from day one (`llm_calls` is the foundation for every quality/cost decision).
- Migration to paid Claude is a model-ID change in OpenRouter config + prompt re-tuning. Snippet library and validation logic survive the migration unchanged.
- HC personalization compounds in value over time without per-HC fine-tuning.

### What this costs

- Every LLM call has a DB write overhead (`llm_calls` insert) — small, but real. Async write, not blocking the response.
- Snippet selection logic must be maintained as the data grows. MVP simplicity may prove insufficient by the time the library has 500+ snippets per HC.
- Token budget for snippets eats from the task-context budget. ~2K tokens is ~2K fewer for transcript or task-specific context.

### Things to revisit

- **Embedding-based snippet retrieval**: when MVP recency-weighted selection visibly fails (HC reports irrelevant snippets being used), introduce embeddings + cosine similarity. New ADR.
- **Key-exchange and stylistic-pattern snippet types**: when HC-edit data is rich enough to validate the heuristics, expand snippet capture. New ADR.
- **Snippet expiration / archival**: at MVP, no expiration. When the library grows large enough to slow selection or eat too much context, define an archival rule.
- **Snippet visibility to HC**: ADR-0001 open follow-up. Whether HC sees a "what the AI has learned about you" view affects trust and DPDP transparency.

---

## References

- `decisions/0001-stack-selection.md` §LLM model chain, §Snippet library
- `diagrams/0002-data-model.md` — full schema
- `specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` — the workflow the LLM serves

---

## Changelog

| Date       | Change                          | Reason                                                                                       |
| ---------- | ------------------------------- | -------------------------------------------------------------------------------------------- |
| 2026-04-28 | Initial draft, Proposed status. | Codifies operational details deferred from ADR-0001 §LLM model chain and §Snippet library. |
| 2026-05-04 | Amendment: §4 schema gains encrypted `prompt_text` / `completion_text` columns; retention parenthetical rewritten (1 year per ADR-0006 §9; `llm_calls` is now in DPDP scope); §7 consent-revocation purge sequence prepended with `DELETE FROM llm_calls` so encrypted rows are cleared. References ADR-0006 §5 amendment (same date) for the pseudonymization + encryption + tenant-scoping policy that governs the new columns. | Paired with ADR-0006 §5 amendment. Originally ADR-0003 §4 said `llm_calls` had no PII and could be retained indefinitely; the amendment to ADR-0006 §5 invalidates that premise. ADR-0003 must reflect the new schema and the new DPDP scope, and the consent-revocation cascade must include the new columns to keep the cascade complete. |
