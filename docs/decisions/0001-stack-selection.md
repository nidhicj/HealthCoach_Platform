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
| Backend framework                | FastAPI (Python 3.12), SQLAlchemy 2.0, Alembic, Pydantic v2.                                                                                                                                                                                                                                                                                                                                                                                                            |
| Backend hosting (primary)        | **GCP Cloud Run (`asia-south1`, Mumbai)** — containerised FastAPI via Docker; scales to zero; free tier covers MVP (2 M req/month + 360 K GB-seconds). GitHub Actions CI/CD via `gcloud run deploy`.                                                                                                                                                                                                                                                                    |
| Backend hosting (named fallback) | DigitalOcean Bangalore Droplet (~$18/month, India region) — same FastAPI Docker image; activated when Cloud Run monthly cost exceeds $25 or cold-start p95 is unacceptable at scale. Effort: 1–2 days (repoint DNS, update env vars).                                                                                                                                                                                                                                    |
| Frontend framework               | Next.js 15 (App Router, TypeScript), Tailwind, shadcn/ui                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Frontend hosting                 | Cloudflare Pages                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Database                         | **Supabase (free tier, `ap-south-1` Mumbai)** — managed Postgres; 500 MB DB, 50 K MAU; India region confirmed. Keep-alive via GitHub Actions cron ping every 4 days (prevents free-tier pause). Upgrade path: Supabase Pro ($25/month) when 500 MB exceeded.                                                                                                                                                                                                            |
| Object storage                   | Cloudflare R2 (free tier — 10 GB / 1 M writes / 10 M reads / zero egress). No India-region pinning at MVP scale; documented known limitation. See changelog 2026-05-05.                                                                                                                                                                                                                                                                                                  |
| Authentication                   | Backend-issued JWT, Google OAuth as identity provider, owned implementation. `User-Agent` set on every `httpx` client via `make_http_client()` factory (good practice; retained from prior implementation).                                                                                                                                                                                                                                                       |
| LLM gateway                      | **OpenRouter** (OpenAI-compatible HTTP API via `httpx`). <br />$10 one-time credit purchase to unlock the 1000 free reqs/day tier (50/day without it).                                                                                                                                                                                                                                                                                                           |
| LLM model strategy               | **Pinned free-model fallback chain** (see "LLM model chain" below), invoked via <br />OpenRouter's built-in `models` array parameter. Migration to paid Claude (Haiku/Sonnet)via the same integration when LLM-layer triggers fire.                                                                                                                                                                                                                              |
| HC style adaptation              | **Per-HC snippet library** in Supabase Postgres Mumbai (table: `hc_style_snippets`, scoped to `hc_user_id`). Captures HC's voice from key exchanges and HC edits to AI drafts. Injected into system <br />prompt on every LLM call (top-N selected by recency + relevance). **Model-agnostic by design** — <br />survives model migration (free → paid Claude) unchanged because every model reads the same snippets. <br />See "Snippet library" section below. |
| Background jobs                  | **GitHub Actions cron** (or GCP Cloud Scheduler) hitting Cloud Run endpoints via HTTPS. No Cron Trigger workarounds needed — Cloud Run is a standard container, any external scheduler works. At scale: Celery + Redis on DO Bangalore.                                                                                                                                                                                                                   |
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

**Storage**: `hc_style_snippets` table in Supabase Postgres (Mumbai). Schema (sketch): `id`, `hc_user_id`, `snippet_type` (enum: `edit`, `exchange`, `pattern`), `original_text`, `hc_modified_text` (nullable), `context_summary`, `created_at`, `relevance_tags`, `client_id` (nullable, for deletion-on-revocation traceability).

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

**Why GCP Cloud Run `asia-south1` (primary host)**:

- Cloudflare Python Workers (the original primary) was eliminated after confirmed lack of FastAPI support. Cloud Run is the natural replacement: full Python ecosystem, no Pyodide constraints, FastAPI runs natively.
- `asia-south1` (Mumbai) — India region, DPDP-defensible, same region as Supabase DB (no cross-region hop at MVP).
- Free tier (2 M req/month + 360 K GB-seconds compute) covers the pilot HC + 5 clients with significant headroom.
- Scales to zero — $0 when idle, which is most of the time at MVP.
- Container-based: the same Docker image that runs locally runs in production. No platform-specific runtime concerns.
- GitHub Actions CI/CD: `gcloud run deploy` on push to `main` — simple, no new tooling.

**Why DigitalOcean Bangalore (named fallback)**:

- Cheapest reliable India-region host (Bangalore datacenter, mature, ~$18/month for 2vCPU/4GB).
- Concrete fallback target — not "we'll figure it out later." When Cloud Run cost or cold-start triggers fire, this is where we go.
- Same FastAPI Docker image; migration is repoint DNS + update env vars (1–2 days effort).
- Single-machine reliability acceptable at prototype + early production scale.

**Why Supabase (free tier, Mumbai) for database**:

- Free tier confirmed available in `ap-south-1` (Mumbai) — DPDP-defensible India-region Postgres.
- 500 MB DB + 50 K MAU is generous for MVP (1 HC, ~5 clients).
- Managed: no RDS provisioning, no VPC/security-group configuration, no IAM user setup.
- Free-tier pause risk mitigated by a GitHub Actions keep-alive ping every 4 days (see `docs/ops/supabase-keepalive.yml`). Data is not lost on pause — only accessibility is suspended.
- Upgrade path is a single click: Supabase Pro ($25/month) when the 500 MB ceiling is approached.
- RLS (Row-Level Security) is available natively — used when a second backend service is introduced (per ADR-0005 follow-up on RLS).

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
2. **Free hosting + ~$0/month LLM at prototype scale.** Cloud Run free tier covers the pilot HC + 5 clients with significant headroom. Supabase free tier covers the DB. OpenRouter $10 one-time + ~$0/month inference. Total ongoing infra cost ≈ **$0/month** at MVP (Sentry free tier, R2 free tier, Cloud Run free tier, Supabase free tier).
3. **Clean migration path named.** When Cloud Run costs rise, DO Bangalore is one Docker container away — same FastAPI image, different host. When free-tier LLM quality fails, paid Claude via OpenRouter is a model-ID change, not a code rewrite.
4. **LLM strategy as first-class concern.** `llm_calls` table from day one means we measure, then decide. ADR-0003 will codify model-selection criteria, output validation patterns, fallback orchestration, and snippet-library retrieval strategy. *Scope update from prior plan*: prompt caching and Batch API discussion deferred until/unless paid-Claude migration — both are Anthropic-direct features unavailable through OpenRouter free tier.
5. **DPDP-defensible architecture.** India-region DB and storage; consent table in data model; real deletion on revocation. Negative-list cross-border regime (Rules finalized 13 Nov 2025) means LLM calls to OpenRouter (US-routed gateway) are permitted today, subject to consent, purpose-limitation disclosure, and verified no-training/no-retention settings on every model in the chain.
6. **Reduced Pyodide-compat risk.** OpenRouter's HTTP-only integration removes the Anthropic-SDK-on-Pyodide unknown that would otherwise have been a smoke-test gate.
7. **Compounding HC personalization.** The snippet library improves on every session through HC edits and key exchanges. Quality grows monotonically with usage, independent of model choice. By the time paid Claude migration fires, the snippets are a quality asset that makes the migration return more.

---

## Consequences — what this costs

Each cost is paired with the workaround we apply, OR explicitly marked as an accepted trade-off (live with it; mitigation only via migration triggers below).

| #  | Consequence                                                                                                                                                                                                                                                                                                      | Workaround / Acceptance                                                                                                                                                                                                                                                               |
| -- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | **Cloud Run cold starts (~1–3s)** on first request after idle. At MVP <br />scale (low traffic), most requests after a period of inactivity will <br />hit a cold container.                                                                                                                             | **Workaround**: set `min-instances: 1` if p95 cold start exceeds 3s <br />(adds ~$10/month). At MVP with a single pilot HC checking in <br />daily, cold starts are infrequent and acceptable. Monitor via <br />GCP Cloud Monitoring.                                          |
| 2  | **Supabase free-tier project pauses** after 1 week of inactivity. <br />API becomes inaccessible until manually unpaused; data is preserved. | **Workaround**: GitHub Actions cron (`supabase-keepalive.yml`) pings <br />the Supabase REST API every 4 days — counts as activity, <br />prevents pause. If pause happens anyway: log in to Supabase <br />dashboard → unpause; takes ~1 min; data intact.                     |
| 3  | **Supabase free tier 500 MB DB ceiling.** If the product grows <br />unexpectedly, the ceiling could be hit before the paid upgrade <br />decision is reviewed.                                                                                                                                           | **Workaround**: ADR-0001 trigger (DB layer, trigger #1) fires at <br />450 MB (90% usage). Monitor via Supabase dashboard. Upgrade to <br />Pro ($25/month) is one click with zero migration.                                                                                  |
| 4  | **R2 object storage has no India-region pinning.** Files stored in R2 <br />are globally distributed; physical location is not India.                                                                                                                                                                    | **Accepted trade-off** under negative-list DPDP regime (Rules <br />finalized 13 Nov 2025). Object storage content (session notes, <br />file library) is covered by this. Revisit before broad launch <br />if legal counsel advises otherwise.                                |
| 5  | **Free-model output is not Sonnet-quality** on user-facing differentiating<br /> features (MOM, pre-session briefs). HC will compare to Zoom's AI summarizer.                                                                                                                                              | **Partial mitigation**: snippet library compounds quality with HC edits. <br />**Accepted trade-off** for the absolute gap until "User #2 onboarded"<br /> trigger #10 fires (then migrate to paid Claude Haiku/Sonnet).                                                  |
| 6  | **Free-model output format is brittle.** Different models follow <br />structured-output instructions with different reliability.                                                                                                                                                                          | **Workaround**: Pydantic validation on every parsed output, 1 retry <br />with stricter format hint, then fail loudly to telemetry.<br /> `validation_failed` flag tracked in `llm_calls`. Trigger #8 <br />escalates if failure rate exceeds 5%.                           |
| 7  | **Free-model availability changes without notice** — <br />models can leave free tier or be retired.                                                                                                                                                                                                      | **Workaround**: pinned fallback chain with 4 alternates from <br />different upstream providers, invoked via OpenRouter's `models` <br />array. Trigger #9 escalates if 2+ chain members deprecated in 90<br /> days.                                                         |
| 8  | **One-repo-dual-config requires discipline.** Easy to let prototype-only <br />patterns leak into the architecture.                                                                                                                                                                                        | **Workaround**: monthly architecture review; flag prototype-only <br />patterns explicitly in code comments (`# PROTOTYPE-ONLY:`).                                                                                                                                            |
| 9  | **Snippet library cold-start.** First few sessions per HC have an empty library<br /> — output quality is at free-model baseline.                                                                                                                                                                         | **Accepted trade-off** by nature (you can't have history without <br />history). Mitigations: HC can pre-seed library with sample edits <br />during onboarding; expect first 5–10 sessions to look generic and <br />document this in HC onboarding flow.                     |
| 10 | **Snippets eat context tokens on every call.** ~2K token budget <br />= ~2K fewer for actual task context.                                                                                                                                                                                                 | **Workaround**: code-enforced cap on snippet budget <br />(configurable per use case, default 2K). Manageable on 70B+ <br />models with 32K–262K context windows. Tighten cap if we fall <br />back to smaller-context models.                                                 |
| 11 | **Snippet curation is real engineering.** Capturing HC edits is mechanical; <br />selecting "key exchanges" and "stylistic patterns" needs heuristics that will <br />sometimes be wrong.                                                                                                                  | **Workaround**: MVP captures **only HC edits to AI drafts** <br />(the highest-signal, simplest path). Other snippet types (key <br />exchanges, stylistic patterns) deferred to ADR-0003 once edit-<br />data justifies the heuristics.                                  |
| 15 | **Privacy traceability per snippet.** Every snippet must be deletable on <br />consent revocation. Easy to forget when tagging snippets.                                                                                                                                                                   | **Workaround**: enforce `client_id` at the data-model level (NOT NULL where applicable, <br />foreign key with cascade-on-delete). Consent revocation runs a <br />single transactional purge across all tables containing `client_id`. Test coverage: deletion test suite. |

---

## Migration triggers

Concrete, falsifiable conditions. Triggers are grouped by which migration they invoke. Frontend stays on Cloudflare Pages in all migration paths.

### Hosting layer — migrate backend to DigitalOcean Bangalore

Each is sufficient on its own to fire migration.

1. **Cold-start user impact**: Cloud Run cold start p95 consistently exceeds 3 seconds over a 7-day window AND `min-instances: 1` (one always-warm instance, ~$10/month extra on Cloud Run) is insufficient or unacceptably expensive. Single warm instance eliminates cold starts at low traffic.
2. **Cost crossover**: monthly Cloud Run usage (compute + requests) exceeds $25 in any month while still serving prototype-scale traffic. A flat-rate DO Droplet ($18/month) becomes cheaper above this threshold.
3. **GCP platform outage**: more than 2 Cloud Run outages attributable to GCP infrastructure (not our code) in any 30-day window.
4. **Hard process requirement**: a background job genuinely requires a persistent long-running process incompatible with Cloud Run's request-scoped model (e.g., a WebSocket server holding thousands of connections). Evaluate before migrating — most cases are solved by Cloud Run concurrency settings.

Migration target: DigitalOcean Bangalore Droplet 2vCPU/4GB (~$18/month). Effort: 1–2 days (same Docker image, deploy via Coolify or `docker compose`, repoint DNS, update env vars). Database (Supabase) and frontend (Cloudflare Pages) unchanged.

### Database layer — upgrade Supabase free → Pro

1. **Storage ceiling**: Supabase free tier DB approaches 450 MB (90% of 500 MB limit).
2. **MAU ceiling**: active users approach 45 K (90% of 50 K limit).
3. **Pause risk becomes real**: if development pauses for >3 weeks and the keep-alive job is not running, upgrade to Pro to eliminate pause risk entirely.

Upgrade target: Supabase Pro ($25/month). Zero migration effort — same connection string, same region, data intact.

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
- **Supabase keep-alive job**: commit `.github/workflows/supabase-keepalive.yml` that pings the Supabase REST API every 4 days. Prevents free-tier project pause. Tracked in `docs/ops/supabase-keepalive.yml` (to be created in P0 / infra setup).
- **Cloud Run `min-instances` decision**: at MVP, `min-instances: 0` (scale to zero). If cold starts become user-visible, set `min-instances: 1` (~$10/month extra). Decision point: monitor p95 cold start after pilot HC starts using daily.
- **Connection pooling for Supabase from Cloud Run**: Supabase provides a built-in connection pooler (Supavisor) on port 6543. Use this instead of direct port 5432 for Cloud Run deployments to avoid connection exhaustion on scale-up. Configure `DATABASE_URL` to point at the pooler endpoint.
- **DPDP consent UX scope for prototype**: data model has the hooks; UX implementation is the open question. Captured in `compliance-india.md` (pending update).
- **Smoke-test gate before pilot launch**: `scripts/smoke-test.py` hits the deployed Cloud Run service and verifies: (1) a Postgres query against Supabase Mumbai, (2) one OpenRouter call against the primary model **with a sample snippet payload injected**, (3) one R2 read. Pass = architecture is real; fail on any leg = revise this ADR before pilot. Owned in Claude Code, not claude.ai.
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

- ✅ **Supabase Mumbai (ap-south-1)**: confirmed available on **free tier** (verified 2026-06-19 by SoJo — Mumbai region selectable in Supabase dashboard on free plan). Free tier: 500 MB DB, 50 K MAU. Pro tier $25/mo. **Chosen as DB** (replaces AWS RDS Mumbai — see changelog).
- ✅ **Vercel Mumbai (bom1)**: confirmed available. *(Not chosen as frontend host; Cloudflare Pages chosen for provider consistency with backend.)*
- ❌ **Railway India region**: does not exist. Closest is Asia Southeast (Singapore). Eliminated as fallback.
- ⚠️ **Fly.io Mumbai (bom)**: exists but capacity-constrained per Fly's own docs and multiple user reports through late 2025. Not chosen as fallback; DigitalOcean Bangalore preferred.
- ✅ **AWS Mumbai (ap-south-1) services**: RDS, S3, ECS Fargate, App Runner, Lambda, Bedrock-with-Anthropic all confirmed available.
- ✅ **Anthropic API pricing** (for reference; not used in MVP): Sonnet 4.6 = $3/$15 per MTok; Haiku 4.5 = $1/$5; Opus 4.7 = $5/$25.
- ✅ **OpenRouter mechanics** (verified Apr 2026): OpenAI-compatible API. Free-tier rate limit is **per account, not per model** — 50 reqs/day under $10 credit purchased, 1000 reqs/day with $10+ credit purchased; 20 reqs/min cap. Failed attempts count toward quota. Account-level "no training" and per-call retention controls available. Built-in `models` array for fallback ordering. Free-tier model availability documented as subject to change.
- ✅ **DPDP cross-border transfer rules**: Rules finalized 13 November 2025. Negative-list approach (transfers permitted unless country blacklisted; no blacklist as of this date). Staggered enforcement: foundational sections immediate, consent manager rules at 12 months, remainder at 18 months. Confirmed via IAPP and KSandK coverage.
- ❌ **Cloudflare Python Workers + FastAPI**: attempted as primary host (Apr–Jun 2026). FastAPI is not supported on Cloudflare Python Workers as of Jun 2026 — confirmed with a deployment error. Workers eliminated as primary; Cloud Run adopted. See changelog 2026-06-19.
- ✅ **GCP Cloud Run `asia-south1` (Mumbai)**: confirmed available; free tier applies globally including Mumbai region. Container-based FastAPI with no platform-specific runtime constraints. Verified as replacement for CF Workers.

---

## References

- `CLAUDE.md` §8 — architectural principles (multi-actor, prompts versioned, LLM observable, etc.)
- `docs/domain/compliance-india.md` — DPDP summary (pending update for 13 Nov 2025 rules)
- `docs/specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` — the actual product the stack must support
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

## Local dev environment

Production uses Supabase (managed Postgres, Mumbai). For local development, run PostgreSQL in Docker — pinned to the same major version as production to catch any version-specific SQL early.

```bash
# Start (first time or after a machine restart)
docker compose up -d postgres

# Stop (keeps data in named volume)
docker compose stop postgres

# Full reset (drops all local data — re-run migrations after)
docker compose down -v && docker compose up -d postgres
```

After `docker compose up -d postgres`, wait ~10 s then run migrations:

```bash
cd backend && alembic upgrade head
```

**Why Docker, not system Postgres:** system `apt upgrade` silently creates new PG clusters on different ports (5432 → 5433 → …), breaking `DATABASE_URL` without warning. The pinned Docker image (`postgres:17.4` in `docker-compose.yml`) is immune to this. Update the pin only when PG 17 reaches EOL (November 2029).

The `parivarthan_test` database must be created manually on first start (it is not auto-created by the image):

```bash
docker exec parivarthan_platform-postgres-1 psql -U postgres -c "CREATE DATABASE parivarthan_test;"
```

---

## Changelog

| Date                 | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Reason                                                                                                                                                                                                                                                                                                        |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-06-19 (latest)  | **Backend hosting changed: Cloudflare Python Workers → GCP Cloud Run (`asia-south1`, Mumbai).** Cloudflare Python Workers eliminated — FastAPI is not supported (confirmed deployment error Jun 2026). Cloud Run adopted as primary: containerised FastAPI via Docker, free tier, India region, no platform-specific workarounds. **Database changed: AWS RDS Postgres Mumbai → Supabase (free tier, `ap-south-1` Mumbai).** Supabase free Mumbai region confirmed by SoJo. Free-tier pause mitigated by GitHub Actions keep-alive cron. DigitalOcean Bangalore remains as named fallback but now triggers against Cloud Run, not Workers. Workers-specific consequences (#1 beta instability, #3 async-only constraint, #4 subrequest limits, #5 User-Agent #68, #6 beta debugging time) removed — none apply to Cloud Run. New hosting-layer and DB-layer triggers added. Background jobs row updated: no longer a Workers workaround — standard external scheduler hitting Cloud Run endpoints. | Cloudflare Python Workers does not support FastAPI. AWS RDS dropped in favour of Supabase free tier — same India region, zero cost at MVP, zero provisioning overhead. |
| 2026-05-05           | **Object storage changed: AWS S3 → Cloudflare R2.** `config.py` fields renamed from `aws_access_key_id / aws_secret_access_key / aws_s3_bucket_name / aws_region` to `r2_access_key_id / r2_secret_access_key / r2_bucket_name / r2_account_id`. `src/lib/s3.py` host changed to `{bucket}.{account_id}.r2.cloudflarestorage.com`, region hardcoded to `"auto"`. Sig V4 signing protocol unchanged. Known MVP limitation: R2 free tier does not support India-region pinning; acceptable at MVP scale under DPDP negative-list regime — revisit before pilot launch. | Zero-cost MVP posture. R2 free tier (10 GB / 1 M writes / 10 M reads / zero egress) avoids all S3 charges at prototype scale. S3-compatible Sig V4 means the change is ~30 lines in two files. |
| 2026-04-28 (latest)  | **Consequences-costs reformatted as a table** with a <br />Workaround / Acceptance column on every row. <br />Each of the 15 cost items is now explicitly marked <br />as either having a code-level workaround (and what it is) <br />or as an accepted trade-off <br />(with the migration trigger that fully mitigates it). <br />No costs added or removed; existing prose condensed into table cells.                                                                                                                                                                                                                                                                                                                                                                                              | Readability — flat list made it hard to tell which<br />costs are mitigated vs. lived-with. Forcing every row to declare its <br />disposition surfaces gaps and makes the engineering checklist <br />concrete.                                                                                             |
| 2026-04-28 (later)   | **HC personalization architecture added.** <br />Introduced per-HC snippet library (`hc_style_snippets` <br />table in RDS Mumbai) as a model-agnostic style-adaptation layer. <br />Captures HC edits to AI drafts (highest signal), <br />key exchanges, and recurring stylistic patterns. <br />Injected into system prompt on every LLM call. <br />Decision-table row added; new "Snippet library" <br />section after Decision; rationale subsection added; <br />4 new Consequences-cost items; ADR-0003 scope expanded; <br />new follow-ups for HC visibility and local-first option.                                                                                                                                                                                                        | Free-model output gap is best mitigated by<br />stronger context, not better models. <br />Snippet library compounds in value over time, transfers <br />across model migrations unchanged, and turns HC editing <br />behavior (which they were going to do anyway) into a first-class <br />quality signal. |
| 2026-04-28           | **LLM strategy revised.** Replaced Anthropic SDK direct with <br />OpenRouter (OpenAI-compatible HTTP gateway) + <br />pinned free-model fallback chain. <br />Added LLM-layer migration triggers (separate group from hosting triggers). <br />Background jobs row updated: <br />APScheduler removed (incompatible with Workers no-threading constraint), <br />external scheduler named as workaround for `workers-py` #27.<br /> Added Consequences items for free-model output brittleness, quality gap, <br />availability changes, threading constraint, and `workers-py` <br />known issues (#27, #68). Verification section extended with <br />OpenRouter mechanics and `workers-py` issue review. <br />Two render typos in prior version corrected ("Co \nnsequences", "4loudflare"). | MVP cost posture — "free as much as possible while quality holds" —<br /> paid Claude deferred to migration triggers. Side benefit: removes <br />Anthropic-SDK-on-Pyodide unknown. Architectural inconsistencies <br />(APScheduler on Workers, threading assumptions) caught and <br />corrected.         |
| 2026-04-26           | **Accepted.** Filled Decision block: Cloudflare Python Workers (primary) + <br />DigitalOcean Bangalore (fallback) + AWS Mumbai DB/storage + <br />Anthropic Sonnet 4.6 default. Added concrete migration triggers. <br />Condensed verification section into findings record. <br />Reordered Options Considered section to put chosen option first.                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Stack decision finalized after verification of all open questions<br />(hosting, DPDP, pricing, beta status).                                                                                                                                                                                                 |
| 2026-04-26 (earlier) | Full rewrite. Removed n8n. Reordered options 1/2/3/4 by professional<br />soundness (Rule 18). <br />Reflected one-repo-dual-config principle. Added <br />"Things to verify" checklist.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | n8n killed; Rule 18 added to anthem; one-repo principle adopted.                                                                                                                                                                                                                                              |
