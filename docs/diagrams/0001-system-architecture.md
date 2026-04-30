# System Architecture (Diagram + Description)

> **MERGE-REQUIRED**: existing diagram in repo from prior session contained n8n + outdated hosting. This is a fresh description aligned with ADR-0001/0002/0003. The actual visual diagram lives on Miro (link in References); this markdown is the textual companion.

---

## Architecture at a glance

```
┌───────────────────────────────────────────────────────────────────────┐
│                          CLIENT (HC's browser)                        │
│                                                                       │
│  Next.js 15 App Router → served from Cloudflare Pages (global edge)   │
└──────────────────────────────────┬────────────────────────────────────┘
                                   │ HTTPS
                                   ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    CLOUDFLARE EDGE (global PoPs)                      │
│                                                                       │
│  ┌─ Cloudflare platform features (dashboard-configured) ───────────┐  │
│  │   Rate limit · WAF · Cache rules · DDoS protection             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌─ Cloudflare Python Workers (open beta) ──────────────────────────┐ │
│  │   FastAPI app (Pyodide runtime, all async def)                  │ │
│  │   · /auth/*  · /api/coaches  · /api/clients  · /api/sessions    │ │
│  │   · /api/llm-jobs (called by external scheduler)                │ │
│  └────────┬─────────────────┬───────────────────┬───────────────────┘ │
└───────────┼─────────────────┼───────────────────┼─────────────────────┘
            │                 │                   │
            │ DB queries      │ S3 read/write     │ HTTPS (httpx async)
            ▼                 ▼                   ▼
   ┌────────────────┐  ┌────────────────┐  ┌──────────────────────────┐
   │ AWS RDS        │  │ AWS S3         │  │  OpenRouter (gateway)    │
   │ Postgres       │  │ Mumbai         │  │  ↓                       │
   │ Mumbai         │  │ ap-south-1     │  │  Llama 3.3 → Gemma 3 →   │
   │ ap-south-1     │  │                │  │  GPT-OSS → Nemotron      │
   │                │  │ Transcripts,   │  │  (pinned chain, free)    │
   │ users,         │  │ MOM exports,   │  │                          │
   │ clients,       │  │ content lib    │  │  DeepSeek R1 (escape     │
   │ sessions,      │  │ assets,        │  │  hatch, app-invoked)     │
   │ moms, briefs,  │  │ consent PDFs   │  │                          │
   │ snippets,      │  │                │  │                          │
   │ llm_calls,     │  │                │  │                          │
   │ consents...    │  │                │  │                          │
   └────────────────┘  └────────────────┘  └──────────────────────────┘

EXTERNAL SCHEDULER (GitHub Actions cron OR EasyCron)
   │
   └─→ HTTPS POST → Cloudflare Worker /jobs/* endpoints
       (workaround for workers-py #27 Cron Triggers broken)

OBSERVABILITY
   Sentry (errors) ← FastAPI + frontend
   Structured logs → Cloudflare Logs (200k/day free)
   llm_calls table → SQL-queryable cost & quality dashboard

ZOOM (HC's existing tool, unchanged)
   Zoom hosts session
   ↓
   Zoom AI Companion generates summary
   ↓
   Webhook → Worker /webhooks/zoom → store transcript ref in S3, summary in sessions table
```

---

## Component summary

| Component | Tech | Where | Notes |
|---|---|---|---|
| Frontend | Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui | Cloudflare Pages | Global edge distribution |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2 | Cloudflare Python Workers (primary) | All deps async; bundle size monitored |
| Backend fallback | Same FastAPI in Docker | DigitalOcean Bangalore Droplet | Activated on ADR-0001 hosting trigger via ADR-0002 decision tree |
| Database | Postgres | AWS RDS Mumbai (ap-south-1) | Connection pooling decision deferred (Hyperdrive / PgBouncer / Supavisor) |
| Object storage | S3 | AWS S3 Mumbai | Transcripts, MOM PDFs, content library assets, consent PDFs |
| LLM gateway | OpenRouter (HTTP, OpenAI-compatible) | Cloudflare Worker → Singapore (OpenRouter) → upstream providers | Pinned free-model chain via `models` array |
| Scheduler | External: GitHub Actions cron OR EasyCron | External | Hits Worker `/jobs/*` endpoints; works around `workers-py` #27 |
| Auth | Backend-issued JWT, Google OAuth | Cloudflare Worker | Owned implementation; explicit User-Agent on httpx (#68) |
| Observability | Sentry + Cloudflare Logs + `llm_calls` table | Mixed | Sentry for errors, CF Logs for structured app logs, RDS for LLM telemetry |
| Edge protection | Cloudflare platform features | Cloudflare dashboard | Rate limit, WAF, cache rules, DDoS — no code |

---

## Request flow examples

### Example 1: HC reviews MOM after a session

1. HC's browser: `GET /api/sessions/{id}/mom` (with JWT)
2. Cloudflare edge: WAF + rate limit check
3. Worker (FastAPI): JWT validation, tenant scope check (`hc_user_id` matches)
4. Worker: query RDS Mumbai for session + draft MOM
5. Worker: returns JSON to frontend
6. Frontend: renders MOM with edit affordances
7. HC edits, hits Send
8. Frontend: `POST /api/sessions/{id}/mom/send`
9. Worker: diffs original draft vs. final, writes diff as snippet (if material)
10. Worker: marks MOM as `sent`, queues email send job
11. Worker: writes `llm_calls` row for the original draft generation, response

### Example 2: Pre-session brief generation (scheduled job)

1. External scheduler: cron triggers HTTPS POST to `/jobs/generate-prep` daily at 6 AM IST
2. Worker: enumerates upcoming sessions in next 24h
3. For each: Worker fetches client history, recent check-ins, open action items, top-N snippets
4. Worker: assembles prompt, calls OpenRouter with `models` array
5. OpenRouter: tries Llama 3.3 70B first; on throttle/error, falls through chain
6. Worker: receives response, validates against Pydantic schema
7. On validation failure: re-prompt with stricter format hint (1 retry)
8. Worker: writes draft brief to RDS, writes `llm_calls` row with telemetry
9. Worker: notifies HC (email or in-app badge) that brief is ready

---

## Migration paths (per ADR-0002)

| Trigger fires | Response |
|---|---|
| Cold start regression on edge endpoints | Try runtime split (JS Worker + Python service) |
| Cold start regression on AI endpoints | Migrate to DO Bangalore |
| Beta outages > 2/30d | Migrate to DO Bangalore |
| Pyodide-incompatible package | Workaround if possible; else DO Bangalore |
| Subrequest/wall-time limits | Diagnose; split or DO |
| Cost > $20/mo (edge-flavored) | Runtime split |
| Cost > $20/mo (AI-flavored) | DO Bangalore |
| `workers-py` blocker matures | DO Bangalore (Linux cron available there) |

---

## What's NOT in this architecture

- **n8n**: removed. All automation is Python in the FastAPI app.
- **Anthropic SDK direct**: replaced with OpenRouter HTTP integration.
- **APScheduler**: incompatible with Workers (no threading). External scheduler instead.
- **Vercel**: replaced with Cloudflare Pages for provider consistency.
- **Supabase**: not used. AWS RDS Mumbai chosen for DPDP defensibility.
- **Redis at MVP**: no, not needed. Added when Celery introduced at scale.
- **In-app client login**: deferred (clients don't directly use the platform at MVP).

---

## References

- `decisions/0001-stack-selection.md`
- `decisions/0002-runtime-topology.md`
- `decisions/0003-llm-strategy.md`
- `decisions/0004-repo-structure.md`
- `diagrams/0002-data-model.md`
- Miro board: https://miro.com/app/board/uXjVIM847Lg=/

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-28 | Fresh description aligned with current ADRs. MERGE-REQUIRED — old repo version had n8n. |
