# Data Model (ERD + Schema)

> **MERGE-REQUIRED**: existing data model in repo from prior session lacked snippets, llm_calls, identities, consents, content libraries. This is a fresh draft incorporating all entities from current ADRs. Visual ERD lives on Miro; this file is the textual companion + DDL sketches.

> **Schema is authoritative**; field names here are what code/migrations should use.

---

## Entity overview

```
┌──────────────┐
│   users      │  (HCs and operators; identities collapse into here at MVP)
└──────┬───────┘
       │ 1
       │
       │ M
┌──────▼───────┐    ┌────────────────┐    ┌──────────────────┐
│   clients    │───▶│   sessions     │───▶│      moms        │
└──────┬───────┘ M  └────────┬───────┘ 1  └──────────────────┘
       │ 1                   │
       │                     │
       │ M                   │ 1
       │              ┌──────▼──────┐    ┌─────────────────┐
       │              │   briefs    │    │  action_items   │
       │              └─────────────┘    └─────────────────┘
       │                                         ▲
       │                                         │
       │ M                                       │
       ├─────────────────┐                       │
       ▼                 ▼                       │
┌──────────────┐  ┌──────────────────┐           │
│   consents   │  │  hc_style_       │           │
│              │  │   snippets       │           │
└──────────────┘  └──────────────────┘           │
                                                 │
       ┌─────────────────────────────────────────┘
       │
┌──────▼───────────┐    ┌──────────────────────┐
│  check_ins       │    │   diet_charts        │
└──────────────────┘    └──────────┬───────────┘
                                   │ M
                                   │
                                   │ M
                          ┌────────▼─────────┐
                          │  prep_recipes    │
                          └──────────────────┘

┌──────────────────┐    ┌──────────────────┐
│   llm_calls      │    │   audit_log      │
│ (telemetry,      │    │ (operator        │
│  no client PII)  │    │   actions)       │
└──────────────────┘    └──────────────────┘

┌──────────────────────┐
│   content_           │
│    assignments       │
│ (which content was   │
│  sent to which       │
│  client when)        │
└──────────────────────┘
```

---

## Tables — concrete schemas

### `users`

The HC table. `is_operator` flag for the SoJo / admin role. No separate `coaches` table at MVP.

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    google_sub      TEXT UNIQUE NOT NULL,             -- Google OAuth subject
    display_name    TEXT,
    photo_url       TEXT,
    is_operator     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ                       -- soft delete only for HC accounts (audit retention)
);

CREATE INDEX idx_users_email ON users (email);
```

### `identities` (optional — defer if simple Google OAuth covers all HCs)

If/when HCs need more than one auth method (e.g., email/password + Google), split identities out:

```sql
CREATE TABLE identities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL,                    -- 'google', 'email', 'apple', etc.
    provider_subject TEXT NOT NULL,                   -- the provider's user ID
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_subject)
);
```

**MVP**: skip this table; put `google_sub` directly on `users`. Introduce when second auth method is needed.

### `clients`

The HC's clients. **Tenanted by `hc_user_id`** — every query joins through this.

```sql
CREATE TABLE clients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hc_user_id      UUID NOT NULL REFERENCES users(id),
    full_name       TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    timezone        TEXT,
    journey_stage   TEXT NOT NULL DEFAULT 'onboarding',  -- 'onboarding', 'active', 'plateau', 'off_track', 'completed'
    course_start_date DATE,
    course_end_date   DATE,
    course_goal     TEXT,
    metadata        JSONB,                            -- demographics, restrictions, anything HC tracks
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clients_hc_user_id ON clients (hc_user_id);
CREATE INDEX idx_clients_journey_stage ON clients (hc_user_id, journey_stage);
```

### `sessions`

One row per session (M000, M00N).

```sql
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hc_user_id      UUID NOT NULL REFERENCES users(id),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    session_number  INTEGER NOT NULL,                 -- 0 for M000, 1 for M001, etc.
    scheduled_at    TIMESTAMPTZ NOT NULL,
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    zoom_meeting_id TEXT,
    transcript_s3_key TEXT,                           -- S3 reference to raw transcript
    summary_s3_key    TEXT,                           -- Zoom AI Companion summary
    notes_internal  TEXT,                             -- HC private notes
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_client_id ON sessions (client_id);
CREATE INDEX idx_sessions_hc_user_id_scheduled ON sessions (hc_user_id, scheduled_at DESC);
CREATE UNIQUE INDEX idx_sessions_client_session_number ON sessions (client_id, session_number);
```

### `moms` (Minutes of Meeting)

```sql
CREATE TABLE moms (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
    hc_user_id      UUID NOT NULL REFERENCES users(id),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    draft_text      TEXT NOT NULL,                    -- AI-generated
    final_text      TEXT,                             -- HC-edited; populated when sent
    status          TEXT NOT NULL DEFAULT 'draft',    -- 'draft', 'reviewed', 'sent'
    sent_at         TIMESTAMPTZ,
    sent_to_email   TEXT,
    llm_call_id     UUID REFERENCES llm_calls(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_moms_status ON moms (status);
CREATE INDEX idx_moms_client_id ON moms (client_id);
```

### `briefs` (pre-session briefs, internal only)

```sql
CREATE TABLE briefs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL UNIQUE REFERENCES sessions(id) ON DELETE CASCADE,
    hc_user_id      UUID NOT NULL REFERENCES users(id),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    brief_text      TEXT NOT NULL,
    triage_flags    TEXT[],                           -- e.g., ['missed_action_item', 'sentiment_drop']
    llm_call_id     UUID REFERENCES llm_calls(id),
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_briefs_session_id ON briefs (session_id);
```

### `action_items`

```sql
CREATE TABLE action_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES sessions(id) ON DELETE CASCADE,
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    hc_user_id      UUID NOT NULL REFERENCES users(id),
    description     TEXT NOT NULL,
    due_date        DATE,
    status          TEXT NOT NULL DEFAULT 'open',     -- 'open', 'completed', 'missed', 'rolled_over'
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_action_items_client_status ON action_items (client_id, status);
```

### `check_ins`

Between-session client signals (mood, weight, food log, free-text note).

```sql
CREATE TABLE check_ins (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    hc_user_id      UUID NOT NULL REFERENCES users(id),
    payload         JSONB NOT NULL,                   -- flexible: {mood, weight, food, note, ...}
    sentiment_flag  TEXT,                             -- 'positive', 'neutral', 'concern', null
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_check_ins_client_created ON check_ins (client_id, created_at DESC);
```

### `hc_style_snippets`

(Per ADR-0003 §5.)

```sql
CREATE TABLE hc_style_snippets (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hc_user_id        UUID NOT NULL REFERENCES users(id),
    client_id         UUID REFERENCES clients(id) ON DELETE CASCADE,  -- nullable for HC-only snippets
    snippet_type      TEXT NOT NULL CHECK (snippet_type IN ('edit', 'exchange', 'pattern')),
    original_text     TEXT NOT NULL,
    hc_modified_text  TEXT,
    context_summary   TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at      TIMESTAMPTZ,
    retired_at        TIMESTAMPTZ,                      -- set by P7 retirement sweep when snippet is stale
    relevance_tags    TEXT[],
    use_count         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_snippets_hc_user_id ON hc_style_snippets (hc_user_id);
CREATE INDEX idx_snippets_client_id ON hc_style_snippets (client_id);
CREATE INDEX idx_snippets_last_used ON hc_style_snippets (hc_user_id, last_used_at DESC NULLS LAST);
```

### `consents`

```sql
CREATE TABLE consents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    hc_user_id      UUID NOT NULL REFERENCES users(id),
    purpose         TEXT NOT NULL,                    -- 'service', 'ai_drafting', 'cross_border', 'snippets', etc.
    granted         BOOLEAN NOT NULL,
    granted_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ,
    source          TEXT NOT NULL,                    -- 'pdf_signed', 'in_app', 'email_confirm'
    source_artifact_s3_key TEXT,                      -- S3 ref to signed PDF if applicable
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_consents_client_purpose ON consents (client_id, purpose);
```

### `diet_charts`

```sql
CREATE TABLE diet_charts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hc_user_id      UUID NOT NULL REFERENCES users(id),
    name            TEXT NOT NULL,
    description     TEXT,
    parameters      JSONB,                            -- {calories, macros, restrictions, ...}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at     TIMESTAMPTZ
);

CREATE INDEX idx_diet_charts_hc_user_id ON diet_charts (hc_user_id) WHERE archived_at IS NULL;
```

### `prep_recipes`

```sql
CREATE TABLE prep_recipes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hc_user_id      UUID NOT NULL REFERENCES users(id),
    name            TEXT NOT NULL,
    ingredients     JSONB NOT NULL,
    instructions    TEXT,
    metadata        JSONB,                            -- {prep_time, calories_per_serving, tags, ...}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    archived_at     TIMESTAMPTZ
);

CREATE INDEX idx_prep_recipes_hc_user_id ON prep_recipes (hc_user_id) WHERE archived_at IS NULL;

-- Many-to-many between diet_charts and prep_recipes
CREATE TABLE diet_chart_recipes (
    diet_chart_id   UUID NOT NULL REFERENCES diet_charts(id) ON DELETE CASCADE,
    prep_recipe_id  UUID NOT NULL REFERENCES prep_recipes(id) ON DELETE CASCADE,
    PRIMARY KEY (diet_chart_id, prep_recipe_id)
);
```

### `content_assignments`

When HC assigns a piece of content (diet chart, recipe, generic handout) to a client.

```sql
CREATE TABLE content_assignments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hc_user_id      UUID NOT NULL REFERENCES users(id),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    session_id      UUID REFERENCES sessions(id),     -- nullable: assignment may not be tied to a session
    content_type    TEXT NOT NULL,                    -- 'diet_chart', 'prep_recipe', 'document'
    content_id      UUID NOT NULL,                    -- references diet_charts.id, prep_recipes.id, or documents.id
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes           TEXT
);

CREATE INDEX idx_content_assignments_client ON content_assignments (client_id, assigned_at DESC);
```

### `llm_calls`

(Per ADR-0003 §4, schema reconciled 2026-04-30.)

```sql
CREATE TABLE llm_calls (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hc_user_id        UUID NOT NULL REFERENCES users(id),
    client_id         UUID REFERENCES clients(id),
    session_id        UUID REFERENCES sessions(id),
    request_id        UUID,
    use_case          TEXT NOT NULL,
    prompt_version    TEXT NOT NULL,
    model_requested   TEXT NOT NULL,
    model_served      TEXT,
    fallback_count    INTEGER NOT NULL DEFAULT 0,
    input_tokens      INTEGER NOT NULL,
    output_tokens     INTEGER NOT NULL,
    latency_ms        INTEGER NOT NULL,
    validation_failed BOOLEAN NOT NULL DEFAULT FALSE,
    snippet_count     INTEGER NOT NULL DEFAULT 0,
    snippet_tokens    INTEGER NOT NULL DEFAULT 0,
    inr_cost_estimate NUMERIC(10, 4),
    raw_request_id    TEXT,
    error_message     TEXT
);

CREATE INDEX idx_llm_calls_created_at ON llm_calls (created_at DESC);
CREATE INDEX idx_llm_calls_hc_use_case ON llm_calls (hc_user_id, use_case);
CREATE INDEX idx_llm_calls_validation_failed ON llm_calls (validation_failed) WHERE validation_failed = TRUE;
```

### `auth_refresh_tokens`

(Per ADR-0005 §10.)

```sql
CREATE TABLE auth_refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    last_used_at    TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    successor_id    UUID REFERENCES auth_refresh_tokens(id),
    user_agent      TEXT,
    ip_at_issue     INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_refresh_tokens_user_id ON auth_refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON auth_refresh_tokens (token_hash);
CREATE INDEX idx_refresh_tokens_active ON auth_refresh_tokens (user_id)
    WHERE revoked_at IS NULL AND expires_at > NOW();
```

### `audit_log`

Operator actions on HC data.

```sql
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id   UUID NOT NULL REFERENCES users(id),
    action          TEXT NOT NULL,                    -- 'read', 'export', 'modify', 'delete'
    target_table    TEXT NOT NULL,
    target_id       UUID,
    target_hc_user_id UUID,                          -- whose HC's data was touched
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_target ON audit_log (target_hc_user_id, created_at DESC);
```

---

## Key constraints and invariants

1. **Tenant scoping**: every client-scoped query MUST filter by `hc_user_id`. Either via JOIN through `clients` or directly on the row's `hc_user_id` field. App-layer enforcement (no RLS at MVP).
2. **Cascade on delete**: every FK to `clients` has `ON DELETE CASCADE`. Deleting a client deletes their sessions, MOMs, briefs, action items, check-ins, snippets, consents, content_assignments. **One transaction; no orphans.**
3. **`coach-reviewed gate`**: the frontend never displays AI-generated content with `status = 'draft'` to clients. Enforced in API layer (status filter on outbound endpoints).
4. **`async def` everywhere**: per ADR-0001, every FastAPI route handler and dependency must be `async def`. Lint rule + code review enforced.

---

## Migration order (when first implementing)

Dependency-constrained order — `llm_calls` must precede `moms`/`briefs` (which FK into it):

1. `users`
2. `clients`
3. `sessions`
4. `llm_calls` (references users, clients, sessions)
5. `moms`, `briefs` (reference llm_calls)
6. `action_items`, `check_ins`
7. `consents`
8. `hc_style_snippets`
9. `audit_log`, `auth_refresh_tokens`
10. `diet_charts`, `prep_recipes`, `diet_chart_recipes`, `content_assignments`

Each migration as its own Alembic file, named `NNNN_description.py`.

---

## References

- `decisions/0003-llm-strategy.md` — `llm_calls` and `hc_style_snippets` rationale
- `domain/glossary.md` — term definitions
- `specs/0001-hc-core-cycle.md` — workflow this schema supports
- Miro ERD: https://miro.com/app/board/uXjVIM847Lg=/

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-28 | Fresh draft incorporating snippets, llm_calls, consents, content libraries. MERGE-REQUIRED with existing repo file. |
| 2026-04-30 | Reconciled llm_calls schema (model_id → model_requested/model_served, added prompt_version, request_id). Added retired_at to hc_style_snippets. Added auth_refresh_tokens (from ADR-0005). Fixed migration order (llm_calls before moms/briefs). |
