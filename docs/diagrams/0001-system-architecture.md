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
│               CLOUDFLARE EDGE (frontend only — global PoPs)           │
│                                                                       │
│  ┌─ Cloudflare platform features (dashboard-configured) ───────────┐  │
│  │   Rate limit · WAF · Cache rules · DDoS protection             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌─ Cloudflare Pages ───────────────────────────────────────────────┐ │
│  │   Next.js 15 static/SSR build                                   │ │
│  └────────────────────────────┬──────────────────────────────────────┘ │
└───────────────────────────────┼───────────────────────────────────────┘
                                │ HTTPS API calls
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│               GCP Cloud Run — asia-south1 (Mumbai)                    │
│                                                                       │
│  FastAPI app (Python 3.12, standard CPython — no Pyodide)             │
│  · /auth/*  · /api/clients  · /api/sessions  · /api/jobs/*           │
│  Scales to zero; free tier at MVP; same Docker image as local dev     │
└────────┬──────────────────────┬───────────────────┬───────────────────┘
         │                      │                   │
         │ DB queries            │ R2 read/write     │ HTTPS (httpx async)
         ▼                      ▼                   ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│ Supabase         │  │ Cloudflare R2    │  │  OpenRouter (gateway)    │
│ Postgres         │  │ (global CDN,     │  │  ↓                       │
│ ap-south-1       │  │ zero egress)     │  │  Llama 3.3 → Gemma 3 →   │
│ Mumbai (free)    │  │                  │  │  GPT-OSS → Nemotron      │
│                  │  │ Session notes,   │  │  (pinned chain, free)    │
│ users, clients,  │  │ MOM exports,     │  │                          │
│ sessions, moms,  │  │ client file lib, │  │  DeepSeek R1 (escape     │
│ briefs, snippets,│  │ consent PDFs     │  │  hatch, app-invoked)     │
│ llm_calls,       │  │                  │  │                          │
│ consents...      │  │                  │  │                          │
└──────────────────┘  └──────────────────┘  └──────────────────────────┘

EXTERNAL SCHEDULER (GitHub Actions cron — every 4 days: Supabase keep-alive)
                     (GitHub Actions cron — daily: snippet retirement, scheduled tasks)
   │
   └─→ HTTPS POST → Cloud Run /api/jobs/* endpoints (X-Scheduler-Token auth)

OBSERVABILITY
   Sentry (errors) ← FastAPI + frontend
   GCP Cloud Logging → structured JSON logs from Cloud Run
   llm_calls table → SQL-queryable cost & quality dashboard (Supabase SQL editor)

ZOOM (HC's existing tool, unchanged)
   Zoom hosts session
   ↓
   Zoom AI Companion generates summary
   ↓
   HC uploads summary file via client file library → stored in R2, fed to LLM
```

---

## Component summary

| Component | Tech | Where | Notes |
|---|---|---|---|
| Frontend | Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui | Cloudflare Pages | Global edge distribution |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2 | GCP Cloud Run `asia-south1` (Mumbai) — primary | Containerised Docker; scales to zero; full Python ecosystem |
| Backend fallback | Same FastAPI Docker image | DigitalOcean Bangalore Droplet | Activated on ADR-0001 Cloud Run hosting triggers |
| Database | Postgres (managed) | Supabase free tier, `ap-south-1` (Mumbai) | 500 MB free; keep-alive via GH Actions cron; upgrade path: Supabase Pro $25/mo |
| Object storage | S3-compatible | Cloudflare R2 (global, zero egress) | Session notes mirror, client file library, consent PDFs. No India-region pin at MVP. |
| LLM gateway | OpenRouter (HTTP, OpenAI-compatible) | Cloud Run → OpenRouter → upstream providers | Pinned free-model chain via `models` array |
| Scheduler | GitHub Actions cron | External | Hits Cloud Run `/api/jobs/*` endpoints; also runs Supabase keep-alive |
| Auth | Backend-issued JWT, Google OAuth | Cloud Run | Owned implementation; standard httpx (no platform-specific workarounds needed) |
| Observability | Sentry + GCP Cloud Logging + `llm_calls` table | Mixed | Sentry for errors, Cloud Logging for structured app logs, Supabase for LLM telemetry |
| Edge protection (frontend) | Cloudflare platform features | Cloudflare dashboard | Rate limit, WAF, cache rules, DDoS — for Cloudflare Pages layer |

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
| Cloud Run cold start p95 > 3s (sustained) | Add `min-instances: 1` on Cloud Run (~$10/mo extra) |
| Cloud Run monthly cost > $25 | Migrate backend to DO Bangalore flat-rate droplet |
| GCP Cloud Run outages > 2/30d | Migrate backend to DO Bangalore |
| Supabase DB approaching 450 MB | Upgrade to Supabase Pro ($25/mo) |
| Supabase MAU approaching 45 K | Upgrade to Supabase Pro ($25/mo) |
| Free-model LLM quality fails (per ADR-0001 triggers 7–10) | Switch model IDs to paid Claude via OpenRouter |

---

## What's NOT in this architecture

- **n8n**: removed. All automation is Python in the FastAPI app.
- **Anthropic SDK direct**: replaced with OpenRouter HTTP integration.
- **APScheduler**: not used. External scheduler (GitHub Actions) keeps background-job concerns outside the web process.
- **Vercel**: replaced with Cloudflare Pages for provider consistency.
- **Cloudflare Python Workers**: eliminated Jun 2026 — FastAPI not supported. Replaced by Cloud Run.
- **AWS RDS Mumbai**: replaced by Supabase free tier (same India region, zero provisioning cost at MVP).
- **AWS S3 Mumbai**: replaced by Cloudflare R2 (zero egress cost) — see ADR-0001 changelog 2026-05-05.
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
| 2026-06-19 | Hosting updated: CF Python Workers → GCP Cloud Run `asia-south1`. DB updated: AWS RDS Mumbai → Supabase free tier (Mumbai). Object storage was already R2 (May 2026). Migration paths table rewritten for Cloud Run triggers. Component table updated. "What's NOT here" updated. ASCII diagram redrawn. |
| 2026-04-28 | Fresh description aligned with current ADRs. MERGE-REQUIRED — old repo version had n8n. |
