# Glossary

> **MERGE-REQUIRED**: this draft is generated fresh against current ADR-0001 and the HC-cycle spec. An existing `glossary.md` is in your repo from earlier sessions. Reconcile the two when committing — keep terms from both unless they conflict.

> Authoritative source for terms used across specs, ADRs, schema, and code. When a term changes meaning, update here first; downstream code follows.

---

## Actors

**Health Coach (HC)** — independent practitioner, the platform's primary paying user. Owns client relationships; sole client-facing voice. Reviews and edits AI drafts before sending.

**Client** — end user receiving coaching. Interacts with the HC, not directly with the AI. (May see HC-sent outputs that were AI-drafted.)

**Junior HC** — internal label for the AI persona that produces drafts. Not visible to the client. The HC is always positioned as the senior reviewer.

**SoJo / Operator** — the platform builder. Has admin access; not a coach.

---

## HC Cycle terms

**HC Cycle** — the full repeating workflow per client, from onboarding through ongoing sessions to course completion. The product's central workflow.

**M000** — the first meeting between HC and client. Onboarding. Goals are set, history captured, course agreed.

**M00N** — the Nth meeting in the cycle. M001 is the first regular session after M000; numbering continues for the duration of the course.

**MOM** — Minutes of Meeting. The formal post-session summary the HC sends to the client. AI-drafted, HC-edited, HC-sent. Singular form (one MOM per session, not "MOMs").

**Pre-session brief** — AI-generated summary the HC reads before the session. Pulls from previous MOM, AST, snippet library, recent client check-ins. Internal — never sent to client.

**Post-meeting** — the workflow stage between session end and MOM-sent. Triage flag check, MOM draft generation, HC edit, HC send.

**Prep work** — what the HC does before a session. The product's prep-work surface assembles the pre-session brief plus any open action items, recent check-ins, and triage flags.

**AST** — Action / Status / Trends. A structured slice of the client's state used in pre-session briefs. Tracks open action items, recent status updates, and emerging trends across sessions.

**Action item** — a specific commitment the client makes during a session, with optional due date. Captured during MOM, surfaced in AST and check-ins.

**Triage flag** — a warning surfaced in pre-session brief (e.g., client missed last action item, sentiment shift in last check-in, mention of distress in recent message). HC reviews before session.

**Sentiment flag** — automated tag on client check-in or session content indicating notable affect (e.g., distress, frustration, excitement). One input to triage flags.

**Coach-reviewed gate** — the architectural rule that no AI-generated content reaches the client without HC review. Implemented as a state on every draft (`status='draft' | 'reviewed' | 'sent'`); only `sent` is visible to client.

---

## Course terms

**Course** — the full coaching engagement with a client. Has a defined duration (e.g., 12 weeks, 6 months) and a stated goal. M000 establishes; subsequent sessions execute.

**Journey stage** — high-level phase of a course (onboarding, active, plateau, off-track, completion). One enum per course at any time. Used for triage and reporting.

**Lead** — a prospective client who has expressed interest but has not yet completed M000. Distinct from a client.

---

## Content terms

**Content library** — HC's repository of reusable assets: handouts, recipes, exercise routines, educational material. Two libraries:
- **Diet charts** — structured meal plans, often parameterized (calories, macros, restrictions)
- **Prep recipes** — recipes for client meal-prep, indexed by diet chart compatibility

**Content assignment** — when an HC sends content to a specific client, with context (which session, what for). Tracked as a separate entity for reporting.

**Two-library structure** — the diet-chart library and the prep-recipe library are linked but separate. A diet chart references one or more prep recipes; recipes can belong to multiple charts. This is the data-model rationale for separating them.

---

## Snippet library terms

**Snippet** — a captured fragment of HC voice or decision-making, stored in `hc_style_snippets`, injected into LLM system prompts to keep AI output stylistically aligned with the HC.

**Snippet types**:
- **Edit snippet** — captured when HC modifies an AI draft before sending. Highest signal. (MVP scope.)
- **Exchange snippet** — captured from a notable HC↔client exchange. Deferred to post-MVP.
- **Pattern snippet** — extracted by batch job from recurring stylistic patterns. Deferred to post-MVP.

**Snippet injection** — the runtime step where selected snippets are formatted into the system prompt. Token-budgeted (~2K default).

---

## LLM terms

**OpenRouter** — the LLM gateway. OpenAI-compatible HTTP API. Single integration point for all model calls; supports `models` array for built-in fallback.

**Pinned chain** — the ordered list of free models in `models` array. Pinned (not random) for reproducibility.

**Reasoning escape hatch** — `deepseek/deepseek-r1:free`. Called by application code for explicitly-difficult tasks; never in the automatic chain.

**`llm_calls`** — telemetry table; one row per LLM call.

**`validation_failed`** — boolean column on `llm_calls`. Set true when Pydantic validation fails on the model output even after one retry. The 5%-rolling-7-day rate is ADR-0001 trigger #8.

**`fallback_count`** — integer column on `llm_calls`. How many models in the chain were tried before success. Healthy = 0 or 1; rising = chain attrition signal (ADR-0001 trigger #9).

---

## Architecture terms

**Multi-tenancy** — the data model is scoped by `hc_user_id` (the HC). Every client-scoped query joins through the HC. RLS optional at MVP; enforced at app layer.

**Row-level security (RLS)** — Postgres feature that scopes rows per session. Considered for MVP, not adopted (overhead vs. benefit at single-HC scale). Re-evaluate at multi-HC scale.

**JSONB** — Postgres binary JSON column type. Used for flexible / evolving structures (e.g., `relevance_tags` on snippets).

**Tenant ID** — synonym for `hc_user_id` in this product. Future scaling may introduce a separate `tenant_id` if HCs share a workspace.

**ADR** — Architecture Decision Record. Markdown file in `docs/decisions/`. Format defined in `docs/decisions/0000-template.md`.

---

## Operational terms

**Migration trigger** — a concrete, falsifiable condition that, when met, mandates a defined response (per the relevant ADR). ADR-0001 has six hosting triggers and four LLM triggers; ADR-0002 has the diagnostic decision tree for hosting triggers.

**Surface** — claude.ai vs. Claude Code. Per Project rules, every task names which surface it belongs on.

**Preflight** — the structured block at the top of every substantive Claude response in this Project. Reference: `PREFLIGHT.md`.

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-28 | Fresh draft from current ADR-0001 + HC cycle spec. MERGE-REQUIRED with existing repo file. |
