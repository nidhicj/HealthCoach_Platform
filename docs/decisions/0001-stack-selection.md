# ADR-0001: Stack Selection for Health Coach Platform

**Status**: Accepted
**Date**: 2026-04-26 (last updated 2026-04-28)
**Decision driver**: SoJo (solo founder)
**Supersedes**: n/a

---

## Context

The Health Coach Platform is a SaaS for independent Indian health coaches: onboarding clients, running AI-assisted sessions (recap, MOM, action items), conducting between-session check-ins, and collecting reviews. AI is the core value layer (drafts produced by an LLM-powered "junior HC" via OpenRouter), with the human coach as supervisor and sole client-facing voice.

Constraints shaping this decision:

- **Solo founder, dedicated full-time to building this platform.**
- **AI-heavy product.** The Python ecosystem (eval harnesses, retrieval, prompt versioning, future ML) is genuinely useful here.
- **India-first.** Coaches and clients in India; latency to Indian users matters.
- **Pragmatic DPDP stance.** Architectural hooks for compliance (consent table, India-region DB, real deletion) but full DPDP UX deferred until post-prototype. Negative-list cross-border regime as of 13 Nov 2025 makes this approach defensible.
- **Prototype scale, time not constrained.** 1 pilot HC, ~5 clients. Time-to-migrate is acceptable if a chosen platform fails.
- **Cost matters at MVP.** "Free as much as possible while quality holds" is the explicit MVP posture. LLM is the dominant variable cost line; making it ~$0 during MVP is a deliberate choice with named tradeoffs (see Consequences).
- **Model-agnostic personalization.** The HC's voice and decision-making style must be captured separately from the LLM choice, so today's free-model output and tomorrow's paid-Claude output stay continuous from the HC's perspective. This is the architectural insulation that makes "use free models now, upgrade later" non-disruptive — and the reason for the snippet library decision below.

This decision settles the language, framework, hosting, AI gateway, AI model strategy, and HC style-adaptation mechanism for the prototype. Repo structure is a separate decision (ADR-0002, pending).

---

## Decision

**Option 1 — Python-first stack — is accepted with the following concrete bindings:**

| Layer                            | Choice                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Backend framework                | FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic,<br />Pydantic v2.**All FastAPI dependencies must be `async def` (no threadpool — see Consequences #3).**                                                                                                                                                                                                                                                                                                        |
| Backend hosting (primary)        | **Cloudflare Python Workers** (open beta)                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Backend hosting (named fallback) | DigitalOcean Bangalore Droplet (~$18/month, India region)                                                                                                                                                                                                                                                                                                                                                                                                                |
| Frontend framework               | Next.js 15 (App Router, TypeScript), Tailwind, shadcn/ui                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Frontend hosting                 | Cloudflare Pages                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Database                         | AWS RDS Postgres, Mumbai (ap-south-1)                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| Object storage                   | AWS S3, Mumbai (ap-south-1)                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Authentication                   | Backend-issued JWT, Google OAuth as identity provider, owned implementation. Explicit `User-Agent` set on every `httpx` client (workaround for `workers-py` #68).                                                                                                                                                                                                                                                                                                  |
| LLM gateway                      | **OpenRouter** (OpenAI-compatible HTTP API via `httpx`). <br />$10 one-time credit purchase to unlock the 1000 free reqs/day tier (50/day without it).                                                                                                                                                                                                                                                                                                           |
| LLM model strategy               | **Pinned free-model fallback chain** (see "LLM model chain" below), invoked via <br />OpenRouter's built-in `models` array parameter. Migration to paid Claude (Haiku/Sonnet)via the same integration when LLM-layer triggers fire.                                                                                                                                                                                                                              |
| HC style adaptation              | **Per-HC snippet library** in AWS RDS Mumbai (table: `hc_style_snippets`, scoped to `hc_user_id`). Captures HC's voice from key exchanges and HC edits to AI drafts. Injected into system <br />prompt on every LLM call (top-N selected by recency + relevance). **Model-agnostic by design** — <br />survives model migration (free → paid Claude) unchanged because every model reads the same snippets. <br />See "Snippet library" section below. |
| Background jobs                  | **External scheduler** (GitHub Actions cron *or* EasyCron) hitting Worker endpoints, until `workers-py` #27 (Cron Triggers broken on Python Workers) lands.<br /> APScheduler explicitly **NOT** used (incompatible with Workers no-threading constraint).<br /> At scale: Celery + Redis on DO Bangalore.                                                                                                                                               |
| Observability                    | Sentry + structured logs + custom `llm_calls` telemetry table (per-call: `model_id`, input/output tokens, latency, `fallback_count`, `validation_failed` flag, INR cost estimate where applicable).                                                                                                                                                                                                                                                              |
| Repo structure                   | One repo, two configurations (prototype config + scale config of same architecture).                                                                                                                                                                                                                                                                                                                                                                                     |

### LLM model chain (initial pinned order)

OpenRouter's free-tier rate limit is **per account, not per model** (50 reqs/day under $10 credit; 1000 reqs/day with $10+ credit purchased — limit persists if balance later drops below $10). The fallback chain therefore exists to handle **upstream provider throttling and model deprecation**, not to multiply daily quota. Invoke via OpenRouter's `models` array — no custom retry orchestration.

| Position                                            | Model (free tier)                               | Use case                                                                                                                               | Why in this position                                                                                                   |
| --------------------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Primary                                             | `meta-llama/llama-3.3-70b-instruct:free`      | All default coaching outputs <br />(MOM, briefs, action items, summaries)                                                              | Strong instruction-following, non-reasoning model (no `<think>` tag noise), <br />good structured-output reliability |
| Fallback 1                                          | `google/gemma-3-27b-it:free`                  | Same as primary                                                                                                                        | Different upstream provider, comparable capability tier, <br />well-behaved on structured output                       |
| Fallback 2                                          | `openai/gpt-oss-120b:free`                    | Same as primary                                                                                                                        | Different upstream again; larger model, <br />slightly slower but high quality                                         |
| Fallback 3                                          | `nvidia/nemotron-3-super:free` (262K context) | Long-context tasks <br />(full session transcripts → MOM)                                                                             | Largest free context window in the chain                                                                               |
| Reasoning escape <br />hatch (NOT in default chain) | `deepseek/deepseek-r1:free`                   | Explicitly-difficult tasks where <br />step-by-step reasoning helps; <br />called by application code, <br />not by automatic fallback | Reasoning model — produces 5–10× more output tokens,<br /> slower; included for cases where it's worth that cost    |

> **Action item before deployment**: verify exact model IDs against `https://openrouter.ai/models?fmt=cards&q=:free`. Free-tier IDs and naming conventions evolve; the chain above reflects intent, not a frozen ID list.

**Mandatory engineering practices** (these flow into ADR-0003):

- All output that downstream code parses goes through **Pydantic validation**. On validation failure: re-prompt with a stricter format hint (1 retry), then fail loudly to telemetry. The `validation_failed` flag in `llm_calls` is the metric for trigger #8 below.
- **No-training / no-retention settings verified** at the OpenRouter account level AND per-call (`X-Provider-Routing` policies, where supported), before any real client data flows.
- **No model substitutions outside the documented chain** without an ADR amendment.

### Snippet library — model-agnostic HC style adaptation

The HC's voice, decision-making style, and characteristic phrasings are captured in a **per-HC snippet library** that any model in the chain reads on every call. This is the architectural insulation that makes free-model-now, paid-Claude-later non-disruptive.

**What gets captured (snippet types)**:

| Type                  | Source                                                                                                            | Signal strength                                                    | Example                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| HC edits to AI drafts | Captured automatically when HC<br />modifies an AI-produced MOM, <br />brief, or action item before sending       | **Highest** — <br />HC literally <br />correcting the model | AI draft said<br />"Try to drink more water"; <br />HC changed to "Aim for 2.5L water/day,track in app" |
| Key exchanges         | Notable HC↔client moments, flagged<br />automatically (sentiment shift, decision points) or<br /> manually by HC | High                                                               | HC's response when client mentioned<br />binge-eating after stress                                      |
| Stylistic patterns    | Recurring phrasings, opening/closing lines,<br />tone markers — extracted by a periodic batch job                | Medium                                                             | "Let's reset" as session-opener;<br />uses "we" not "you"                                               |

**Storage**: `hc_style_snippets` table in AWS RDS Mumbai. Schema (sketch): `id`, `hc_user_id`, `snippet_type` (enum: `edit`, `exchange`, `pattern`), `original_text`, `hc_modified_text` (nullable), `context_summary`, `created_at`, `relevance_tags`, `client_id` (nullable, for deletion-on-revocation traceability).

**How models use it**: each LLM call assembles a system prompt containing (a) the static role/format instructions, (b) the top-N snippets for this HC selected by recency + relevance to the current task. Token budget for snippets capped at ~2K so it leaves room for actual task context. Selection is simple recency-weighted at MVP; retrieval (embeddings, similarity) deferred to ADR-0003.

**Why this works across models**: snippets are plain English with structure. Llama 3.3 70B reads them. Claude Haiku reads them. Future Sonnet reads them. Style transfers automatically; no per-model fine-tuning, no retraining, no lock-in.

**Privacy / DPDP**: snippets contain client conversation context. The `client_id` field enables targeted deletion when a client revokes consent — every snippet referencing that client is purged in the same operation as the client's primary records. This is captured as a hard requirement, not a nice-to-have.

**What this is NOT**:

- Not a routing logbook (chain order is determined by the `models` array, not by snippets)
- Not a fine-tuned model (no training; snippets are runtime context)
- Not stored on the HC's local machine (current architecture is web SaaS — there is no local install. If true local-first is later required, that's a different deployment model and a separate ADR)

---

## Rationale

**Why Option 1 (Python primary)** beats Options 2/3/4 for this product:

- AI-product engineering surface (eval harnesses, retrieval, structured prompt management, future ML work) is materially better in Python.
- LLM cost engineering — model selection, output validation, fallback orchestration — is stack-agnostic. Stack choice does not impact LLM unit cost. Optimizing the stack for "cheap AI" is optimizing the wrong line item.
- Multi-actor data model and DPDP-friendly architecture (consent table, real deletion, India-region DB) are framework-neutral.
- One-repo-dual-config principle is naturally expressible in a Python+Next.js layout.

**Why Cloudflare Python Workers (primary host)**:

- Python Workers is now first-class as of Jan 2026: FastAPI runs natively, cold starts ~1s with snapshots, free tier of 100k requests/day covers prototype scale completely.
- Edge distribution gives latency benefits over single-region hosting.
- Cloudflare Pages + Workers + R2 (and optionally D1) form a coherent platform for the frontend-backend pair.
- Prototype scale + time-not-constrained = beta-platform risk is acceptable.

**Why DigitalOcean Bangalore (named fallback)**:

- Cheapest reliable India-region host (Bangalore datacenter, mature, $18/month for 2vCPU/4GB).
- Concrete migration target — not "we'll figure it out later." When triggers fire, this is where we go.
- Single-machine reliability acceptable at prototype + early production scale.

**Why AWS for DB/storage despite Cloudflare for compute**:

- AWS RDS Mumbai gives India-region data residency for DPDP defensibility.
- Postgres + S3 are well-understood and migrate cleanly to other clouds later.
- Tradeoff (network hop) is named explicitly in Consequences and accepted at prototype scale.

**Why OpenRouter as the LLM gateway**:

- **OpenAI-compatible HTTP API via `httpx`** — eliminates the "does the Anthropic SDK work inside Pyodide?" risk on Python Workers. `httpx` is officially supported on Workers; we sidestep the deeper SDK layers.
- **Provider abstraction** — same integration code talks to Claude, GPT, Llama, DeepSeek, Gemma. Migration from free models to paid Claude is a model-ID change, not a code rewrite.
- **Single billing surface** — one credit pool, one telemetry source.
- **Built-in fallback orchestration** via the `models` array — no custom retry logic to maintain.

**Why a pinned free-model chain (MVP-only posture)**:

- Cost — at MVP scale (1 HC, ~5 clients), paid Claude Sonnet usage would run ~$5–20/month; free models bring that to $10 once. Small absolute savings, but real for a self-funded MVP, and the architectural learning is identical.
- This is **explicitly an MVP posture**. The "User #2 onboarded" milestone in migration triggers below forces a re-evaluation. Quality of free models on user-facing differentiating features (MOM, pre-session briefs) is the deliberate trade.

**Why pinned (not the random `openrouter/free` router)**:

- Reproducibility. Prompts are tuned per model. Random selection makes outputs non-deterministic across requests, breaks Pydantic validation rate analysis, and makes prompt iteration impossible.

**Why a per-HC snippet library (model-agnostic personalization)**:

- The HC's voice and decision-making patterns are the differentiating asset of the product. Encoding them in plain-English snippets (not in fine-tuned weights) means the asset survives every model change — free→paid, OpenRouter→direct, Llama→Claude.
- It dampens the free-model quality gap. A free model with strong HC context performs closer to a paid model running blind. Snippet quality is the lever that compounds while LLM cost stays flat.
- HC edits to AI drafts are the highest-signal training data the product will ever produce — capturing them is essentially free (HC was going to edit anyway) and the value compounds with every session.
- It is the *only* lever that genuinely scales independently of model choice. Migrating models gets a one-time quality bump; the snippet library gets better every week regardless of which model is in use.

---

## Consequences — what this enables

1. **Python ecosystem fully available.** Prompt versioning in `prompts/*.md`, evals via promptfoo or similar, retrieval via pgvector, future ML work — all clean.
2. **Free hosting + ~$0/month LLM at prototype scale.** Cloudflare Workers free tier (100k req/day) covers the pilot HC + 5 clients with significant headroom. OpenRouter $10 one-time + ~$0/month inference. Total ongoing infra cost ≈ $25–30/month (AWS RDS + S3 + Sentry).
3. **Clean migration path named.** When Workers fails (see triggers below), DO Bangalore is one Docker container away — same FastAPI code, different host. When free-tier LLM quality fails, paid Claude via OpenRouter is a model-ID change, not a code rewrite.
4. **LLM strategy as first-class concern.** `llm_calls` table from day one means we measure, then decide. ADR-0003 will codify model-selection criteria, output validation patterns, fallback orchestration, and snippet-library retrieval strategy. *Scope update from prior plan*: prompt caching and Batch API discussion deferred until/unless paid-Claude migration — both are Anthropic-direct features unavailable through OpenRouter free tier.
5. **DPDP-defensible architecture.** India-region DB and storage; consent table in data model; real deletion on revocation. Negative-list cross-border regime (Rules finalized 13 Nov 2025) means LLM calls to OpenRouter (US-routed gateway) are permitted today, subject to consent, purpose-limitation disclosure, and verified no-training/no-retention settings on every model in the chain.
6. **Reduced Pyodide-compat risk.** OpenRouter's HTTP-only integration removes the Anthropic-SDK-on-Pyodide unknown that would otherwise have been a smoke-test gate.
7. **Compounding HC personalization.** The snippet library improves on every session through HC edits and key exchanges. Quality grows monotonically with usage, independent of model choice. By the time paid Claude migration fires, the snippets are a quality asset that makes the migration return more.

---

## Consequences — what this costs

Each cost is paired with the workaround we apply, OR explicitly marked as an accepted trade-off (live with it; mitigation only via migration triggers below).

| #  | Consequence                                                                                                                                                                                                                                                                                                      | Workaround / Acceptance                                                                                                                                                                                                                                                               |
| -- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | **Cloudflare Python Workers is open beta** — package compat surprises, <br />runtime patches that occasionally break things, less SO/Reddit answer surface. <br />Practitioner reports as recently as Nov 2025 still show people hitting <br />"FastAPI module not found" errors during runtime upgrades. | **Accepted trade-off.** No code-level workaround. Migrate to DO <br />Bangalore if hosting triggers 1–6 fire.                                                                                                                                                                  |
| 2  | **Network hop: Cloudflare edge → AWS Mumbai DB.** 10–30ms per <br />query depending on which Cloudflare PoP serves the request, on top of <br />actual query time.                                                                                                                                       | **Workaround**: connection pooling (Hyperdrive / PgBouncer / <br />Supavisor). Decision deferred until the Workers→RDS pattern <br />is exercised in real code, then implemented if needed.                                                                                    |
| 3  | **No threading on Python Workers.** All FastAPI deps must be `async def`. <br />A sync dep triggers `run_in_threadpool` <br />which throws `RuntimeError: can't start new thread` at runtime, not at deploy.                                                                                         | **Workaround**: enforce `async def` everywhere via code review +<br /> a lint rule. Engineering checklist item. Free of cost once disciplined.                                                                                                                                |
| 4  | **`workers-py` #27 — Cron Triggers broken** (open since Sep 2025).                                                                                                                                                                                                                                      | **Workaround** (already in Decision table): external scheduler — <br />GitHub Actions cron or EasyCron — hits Worker endpoints. <br />Adds one external dependency. Auto-resolves if CF fixes #27 or <br />we migrate to DO.                                                  |
| 5  | **`workers-py` #68 — `httpx` missing User-Agent** (open since Feb 2026). <br />Breaks OAuth flows and APIs that reject empty UAs.                                                                                                                                                                     | **Workaround**: explicit `headers={"User-Agent": "<our-ua>"}` on <br />every `httpx.AsyncClient`. One line per client. Catalogued in <br />engineering checklist.                                                                                                           |
| 6  | **Beta-driven debugging will eat product time.** Hours-to-days lost per <br />platform issue.                                                                                                                                                                                                              | **Accepted trade-off.** Budget 2–4 days across the prototype build. <br />No workaround — it's the cost of being on a beta platform.                                                                                                                                          |
| 7  | **Free-model output is not Sonnet-quality** on user-facing differentiating<br /> features (MOM, pre-session briefs). HC will compare to Zoom's AI summarizer.                                                                                                                                              | **Partial mitigation**: snippet library compounds quality with HC edits. <br />**Accepted trade-off** for the absolute gap until "User #2 onboarded"<br /> trigger #10 fires (then migrate to paid Claude Haiku/Sonnet).                                                  |
| 8  | **Free-model output format is brittle.** Different models follow <br />structured-output instructions with different reliability.                                                                                                                                                                          | **Workaround**: Pydantic validation on every parsed output, 1 retry <br />with stricter format hint, then fail loudly to telemetry.<br /> `validation_failed` flag tracked in `llm_calls`. Trigger #8 <br />escalates if failure rate exceeds 5%.                           |
| 9  | **Free-model availability changes without notice** — <br />models can leave free tier or be retired.                                                                                                                                                                                                      | **Workaround**: pinned fallback chain with 4 alternates from <br />different upstream providers, invoked via OpenRouter's `models` <br />array. Trigger #9 escalates if 2+ chain members deprecated in 90<br /> days.                                                         |
| 10 | **Edge compute location is non-Indian.** Workers run on global edge; <br />data is in AWS Mumbai but request processing happens at whichever <br />PoP the user routes to.                                                                                                                                 | **Accepted trade-off** under negative-list DPDP regime <br />(Rules finalized 13 Nov 2025). Full mitigation = migrate to DO <br />Bangalore (puts compute in India too). Revisit during <br />`compliance-india.md` update.                                                   |
| 11 | **One-repo-dual-config requires discipline.** Easy to let prototype-only <br />patterns leak into the architecture.                                                                                                                                                                                        | **Workaround**: monthly architecture review; flag prototype-only <br />patterns explicitly in code comments (`# PROTOTYPE-ONLY:`).                                                                                                                                            |
| 12 | **Snippet library cold-start.** First few sessions per HC have an empty library<br /> — output quality is at free-model baseline.                                                                                                                                                                         | **Accepted trade-off** by nature (you can't have history without <br />history). Mitigations: HC can pre-seed library with sample edits <br />during onboarding; expect first 5–10 sessions to look generic and <br />document this in HC onboarding flow.                     |
| 13 | **Snippets eat context tokens on every call.** ~2K token budget <br />= ~2K fewer for actual task context.                                                                                                                                                                                                 | **Workaround**: code-enforced cap on snippet budget <br />(configurable per use case, default 2K). Manageable on 70B+ <br />models with 32K–262K context windows. Tighten cap if we fall <br />back to smaller-context models.                                                 |
| 14 | **Snippet curation is real engineering.** Capturing HC edits is mechanical; <br />selecting "key exchanges" and "stylistic patterns" needs heuristics that will <br />sometimes be wrong.                                                                                                                  | **Workaround**: MVP captures **only HC edits to AI drafts** <br />(the highest-signal, simplest path). Other snippet types (key <br />exchanges, stylistic patterns) deferred to ADR-0003 once edit-<br />data justifies the heuristics.                                  |
| 15 | **Privacy traceability per snippet.** Every snippet must be deletable on <br />consent revocation. Easy to forget when tagging snippets.                                                                                                                                                                   | **Workaround**: enforce `client_id` at the data-model level (NOT NULL where applicable, <br />foreign key with cascade-on-delete). Consent revocation runs a <br />single transactional purge across all tables containing `client_id`. Test coverage: deletion test suite. |

---

## Migration triggers

Concrete, falsifiable conditions. Triggers are grouped by which migration they invoke. Frontend stays on Cloudflare Pages in all migration paths.

### Hosting layer — migrate backend to DigitalOcean Bangalore

Each is sufficient on its own to fire migration.

1. **Cold-start regression**: cold start consistently exceeds 3 seconds for our FastAPI bundle (uptime monitoring p95 over a 7-day window).
2. **Beta-driven outages**: more than 2 platform-attributable outages or breaking-change incidents in any 30-day window — defined as: incidents where the FastAPI bundle stopped working without our code change, traceable to a Pyodide / Workers runtime update.
3. **Required Python package not Pyodide-compatible**: any package the product genuinely needs is unavailable in Pyodide and has no equivalent.
4. **Subrequest or wall-time limit hit**: an LLM call or DB-heavy endpoint regularly exceeds Workers' wall-time limits (30s default CPU; 50 free / 1000 paid subrequests).
5. **Cost crossover**: monthly Cloudflare Workers paid usage exceeds $20 in any month while still serving prototype-scale traffic.
6. **`workers-py` blocker matures into a hard requirement**: e.g., the product's roadmap requires native Cron Triggers (#27 still unfixed) and external scheduler workarounds become operationally untenable; or OAuth flow requirements (#68) become un-workaroundable.

Migration target: DigitalOcean Bangalore Droplet 2vCPU/4GB ($18/month). Effort: 1–3 days (dockerize FastAPI, deploy via Coolify or `docker compose`, repoint DNS, update env vars). Database and frontend unchanged.

### LLM layer — migrate to paid Claude via OpenRouter

These are about model quality and operational fragility, not hosting. Same OpenRouter integration; only model IDs change. Each is sufficient on its own.

7. **HC-visible quality regression** on user-facing outputs: the pilot HC reports that MOM, pre-session briefs, or action items are visibly worse than Zoom's built-in summarizer (or worse than a comparison sample of Sonnet output) on more than 1 in 5 reviewed sessions.
8. **Output-format failure rate exceeds 5%**: Pydantic validation failures on the primary model exceed 5% of calls over a rolling 7-day window, even after the one-retry re-prompt. Indicates the chain is too brittle for production.
9. **Chain attrition**: 2 or more models in the pinned chain are deprecated or moved off free tier within any 90-day window.
10. **User #2 onboarded**: independent of any of the above, the moment a second paying HC is onboarded, re-evaluate the LLM strategy. With multiple users comparing output, the quality gap becomes more visible and the absolute cost of paid Claude is still small.

Migration target: same OpenRouter integration, switch primary model ID to `anthropic/claude-haiku-4.5` (default) and `anthropic/claude-sonnet-4.6` (premium paths). Effort: minutes for code change; days for prompt re-tuning if quality differences require it.

---

## Open follow-ups (deliberately deferred)

- **ADR-0003** (planned): LLM strategy principles — model-selection criteria, output validation patterns, fallback orchestration, telemetry schema for `llm_calls`, **and snippet-library mechanics** (extraction triggers, retrieval/selection algorithm, expiration/archival policy, batch jobs for stylistic-pattern extraction). *Scope update*: prompt caching and Batch API discussion deferred until/unless paid-Claude migration; both are Anthropic-direct features unavailable through OpenRouter free tier.
- **Connection pooling for AWS RDS Mumbai from Cloudflare Workers**: whether to introduce Hyperdrive, PgBouncer, or Supavisor between Workers and RDS to reduce connection overhead. Decide once the Workers-to-RDS pattern is exercised in real code.
- **DPDP consent UX scope for prototype**: data model has the hooks; UX implementation is the open question. Captured in `compliance-india.md` (pending update).
- **Cloudflare D1 vs AWS RDS for prototype**: D1 (SQLite at Cloudflare edge) is much closer to Workers compute and dramatically cheaper. Not chosen here because (a) Postgres-specific features (jsonb, full-text search) we'll likely need, and (b) AWS Mumbai = India region for DPDP. Worth revisiting if the Workers-RDS hop turns out to be painful.
- **Smoke-test gate before pilot launch**: a minimal end-to-end Worker that does (1) a Postgres query against a test RDS Mumbai instance via the chosen pooling approach, (2) one OpenRouter call against the primary model **with a sample snippet payload injected**, (3) one S3 read from Mumbai. Pass = architecture is real; fail on any leg = revise this ADR before pilot. Owned in Claude Code, not claude.ai.
- **Snippet visibility to HC**: whether the HC sees the snippet library (e.g., a "what the AI has learned about your style" view) or whether it stays internal. Affects trust posture and DPDP transparency obligations. Defer until first HC feedback session.
- **Local-first deployment option**: SoJo expressed interest in storing snippets on the HC's local machine for stronger privacy. Current architecture (web SaaS, browser-based) does not support this; would require an Electron desktop app or a local-first sync layer. Captured here as a possible future direction, not a current commitment.

---

## Options considered

The following options were considered before settling on Option 1. Listed in order of professional soundness for this specific product (Rule 18). The chosen option's full case is in the Decision and Rationale sections above; the others are summarized for traceability.

### Option 1 — Python-first (chosen)

FastAPI (Python) backend + Next.js frontend + OpenRouter LLM gateway + Postgres. AI-product engineering surface, multi-actor data model, India-region data, owned auth.

### Option 2 — TypeScript full-stack

Next.js (frontend + API routes) + Anthropic/OpenAI SDK + Postgres + Supabase Auth or Auth.js. Single-language stack, ship-fast, mature Cloudflare/Vercel hosting story.

**Why not chosen**: weaker Python ecosystem for AI work (eval harnesses, retrieval, future ML); Vercel timeout constraints on long LLM calls; auth lock-in if using Supabase Auth; one-repo-dual-config principle harder to express cleanly.

### Option 3 — Python + AWS-only

FastAPI on AWS Fargate Mumbai or App Runner Mumbai + RDS Mumbai + S3 + Bedrock-with-Anthropic. Pure AWS stack, enterprise-ready posture from day one.

**Why not chosen**: ~$60–90/month at prototype scale (vs ~$25–30/month with Cloudflare + AWS DB); operational complexity (ECS task def + ALB + VPC + IAM) is real time spent on infrastructure rather than product. Worth revisiting if/when enterprise buyers require it.

### Option 4 — Convex / fully managed BaaS

Convex or similar as the entire backend (auth + DB + functions + realtime). Fastest possible time-to-prototype.

**Why not chosen**: Convex region availability and DPDP-defensibility unverified; vendor lock-in is total; AI engineering surface limited; multi-actor data model harder to evolve outside Convex's paradigm.

---

## Things verified before accepting

These external facts were verified during the decision-making process. Findings folded into Rationale and Consequences above; this section retained as a record of due diligence.

- ✅ **Supabase Mumbai (ap-south-1)**: confirmed available, Pro tier $25/mo. *(Not chosen as DB; AWS RDS Mumbai chosen instead per "AWS for DB/storage" preference.)*
- ✅ **Vercel Mumbai (bom1)**: confirmed available. *(Not chosen as frontend host; Cloudflare Pages chosen for provider consistency with backend.)*
- ❌ **Railway India region**: does not exist. Closest is Asia Southeast (Singapore). Eliminated as fallback.
- ⚠️ **Fly.io Mumbai (bom)**: exists but capacity-constrained per Fly's own docs and multiple user reports through late 2025. Not chosen as fallback; DigitalOcean Bangalore preferred.
- ✅ **AWS Mumbai (ap-south-1) services**: RDS, S3, ECS Fargate, App Runner, Lambda, Bedrock-with-Anthropic all confirmed available.
- ✅ **Anthropic API pricing** (for reference; not used in MVP): Sonnet 4.6 = $3/$15 per MTok; Haiku 4.5 = $1/$5; Opus 4.7 = $5/$25.
- ✅ **OpenRouter mechanics** (verified Apr 2026): OpenAI-compatible API. Free-tier rate limit is **per account, not per model** — 50 reqs/day under $10 credit purchased, 1000 reqs/day with $10+ credit purchased; 20 reqs/min cap. Failed attempts count toward quota. Account-level "no training" and per-call retention controls available. Built-in `models` array for fallback ordering. Free-tier model availability documented as subject to change.
- ✅ **DPDP cross-border transfer rules**: Rules finalized 13 November 2025. Negative-list approach (transfers permitted unless country blacklisted; no blacklist as of this date). Staggered enforcement: foundational sections immediate, consent manager rules at 12 months, remainder at 18 months. Confirmed via IAPP and KSandK coverage.
- ✅ **Cloudflare Python Workers + FastAPI**: open beta as of late 2025; FastAPI officially supported per Cloudflare docs and Jan 2026 redux blog post (cold starts ~1s with snapshots, package support via Pyodide + uv, free tier 100k req/day). Practitioner reports (mkdev.me, Cloudflare Community Nov 2025) flag continued beta-status issues.
- ⚠️ **`workers-py` known issues** (review of open issues, Apr 2026): #27 Cron Triggers broken (Sep 2025, still open); #68 `httpx` missing User-Agent header (Feb 2026, still open); #92 `.venv` uploaded with worker (Apr 2026, workaroundable via `.wranglerignore`). Threading unsupported in Pyodide runtime (requires async-only FastAPI dependencies). Captured in Consequences and Migration triggers.

---

## References

- `CLAUDE.md` §8 — architectural principles (multi-actor, prompts versioned, LLM observable, etc.)
- `docs/domain/compliance-india.md` — DPDP summary (pending update for 13 Nov 2025 rules)
- `docs/specs/spec-0001-hc-core-cycle.md` — the actual product the stack must support
- `docs/diagrams/0001-system-architecture.md` — visual architecture (will be updated post-decision)
- Cloudflare Python Workers redux (blog, Jan 2026): https://blog.cloudflare.com/python-workers-advancements/
- Cloudflare `workers-py` issue tracker: https://github.com/cloudflare/workers-py/issues
- DigitalOcean Bangalore pricing: https://www.digitalocean.com/pricing/droplets
- OpenRouter API rate limits: https://openrouter.ai/docs/api/reference/limits
- OpenRouter FAQ: https://openrouter.ai/docs/faq
- OpenRouter free models browser: https://openrouter.ai/models?fmt=cards&q=:free
- Anthropic API pricing (for reference): https://platform.claude.com/docs/en/about-claude/pricing
- DPDP Rules finalization (IAPP, Nov 2025): https://iapp.org/news/a/with-rules-finalized-india-s-dpdpa-takes-force

---

## Changelog

| Date                 | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Reason                                                                                                                                                                                                                                                                                                        |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-04-28 (latest)  | **Consequences-costs reformatted as a table** with a <br />Workaround / Acceptance column on every row. <br />Each of the 15 cost items is now explicitly marked <br />as either having a code-level workaround (and what it is) <br />or as an accepted trade-off <br />(with the migration trigger that fully mitigates it). <br />No costs added or removed; existing prose condensed into table cells.                                                                                                                                                                                                                                                                                                                                                                                              | Readability — flat list made it hard to tell which<br />costs are mitigated vs. lived-with. Forcing every row to declare its <br />disposition surfaces gaps and makes the engineering checklist <br />concrete.                                                                                             |
| 2026-04-28 (later)   | **HC personalization architecture added.** <br />Introduced per-HC snippet library (`hc_style_snippets` <br />table in RDS Mumbai) as a model-agnostic style-adaptation layer. <br />Captures HC edits to AI drafts (highest signal), <br />key exchanges, and recurring stylistic patterns. <br />Injected into system prompt on every LLM call. <br />Decision-table row added; new "Snippet library" <br />section after Decision; rationale subsection added; <br />4 new Consequences-cost items; ADR-0003 scope expanded; <br />new follow-ups for HC visibility and local-first option.                                                                                                                                                                                                        | Free-model output gap is best mitigated by<br />stronger context, not better models. <br />Snippet library compounds in value over time, transfers <br />across model migrations unchanged, and turns HC editing <br />behavior (which they were going to do anyway) into a first-class <br />quality signal. |
| 2026-04-28           | **LLM strategy revised.** Replaced Anthropic SDK direct with <br />OpenRouter (OpenAI-compatible HTTP gateway) + <br />pinned free-model fallback chain. <br />Added LLM-layer migration triggers (separate group from hosting triggers). <br />Background jobs row updated: <br />APScheduler removed (incompatible with Workers no-threading constraint), <br />external scheduler named as workaround for `workers-py` #27.<br /> Added Consequences items for free-model output brittleness, quality gap, <br />availability changes, threading constraint, and `workers-py` <br />known issues (#27, #68). Verification section extended with <br />OpenRouter mechanics and `workers-py` issue review. <br />Two render typos in prior version corrected ("Co \nnsequences", "4loudflare"). | MVP cost posture — "free as much as possible while quality holds" —<br /> paid Claude deferred to migration triggers. Side benefit: removes <br />Anthropic-SDK-on-Pyodide unknown. Architectural inconsistencies <br />(APScheduler on Workers, threading assumptions) caught and <br />corrected.         |
| 2026-04-26           | **Accepted.** Filled Decision block: Cloudflare Python Workers (primary) + <br />DigitalOcean Bangalore (fallback) + AWS Mumbai DB/storage + <br />Anthropic Sonnet 4.6 default. Added concrete migration triggers. <br />Condensed verification section into findings record. <br />Reordered Options Considered section to put chosen option first.                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Stack decision finalized after verification of all open questions<br />(hosting, DPDP, pricing, beta status).                                                                                                                                                                                                 |
| 2026-04-26 (earlier) | Full rewrite. Removed n8n. Reordered options 1/2/3/4 by professional<br />soundness (Rule 18). <br />Reflected one-repo-dual-config principle. Added <br />"Things to verify" checklist.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | n8n killed; Rule 18 added to anthem; one-repo principle adopted.                                                                                                                                                                                                                                              |
