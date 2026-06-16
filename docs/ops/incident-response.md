# Incident Response

> **Status**: Template. `DECIDE` and `FILL IN` markers below are deliberate gaps. Resolve as decisions are made.

> **Maturity**: MVP-stage. Solo on-call. Severity definitions and runbooks lean and pragmatic.

---

## Severity definitions

> **DECIDE**: are these definitions right for your scale? At 1 HC + ~5 clients, "users affected" thresholds are tiny. Adjust as scale grows. The shape is more important than the exact numbers.

| Level | Definition | Example | Response timeframe |
|---|---|---|---|
| **SEV-1** | Pilot HC cannot use the platform at all OR client data is exposed/lost | Worker entirely down; database fully unreachable; auth completely broken; data leak suspected | Drop everything; respond within minutes |
| **SEV-2** | Pilot HC partially impacted OR a critical workflow broken | MOM generation always fails; brief generation always fails; sign-in works for some not others | Within hours |
| **SEV-3** | Workaround exists; user-visible degradation | Slow page loads; one specific endpoint flaky; intermittent LLM validation failures | Same day |
| **SEV-4** | Internal-only impact; no user impact yet | Sentry alert on a corner-case error; one Cloudflare Workers Logs warning surge; cost approaching ADR-0001 trigger | Next working day |

---

## On-call

> **FILL IN**: at MVP, on-call is SoJo. As team grows, this becomes a rotation.

- **Primary**: SoJo
- **Secondary**: n/a at MVP
- **Hours**: **DECIDE**. Default at MVP: best-effort, no formal SLA. Pilot HC understands the platform is pre-launch.

When a SEV-1 hits and SoJo is unreachable: pilot HC has a documented manual workaround for the day (running the cycle without the platform; per `specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` non-goals, sessions happen on Zoom — platform is HC-supporting, not HC-blocking).

---

## Detection sources

| Source | What it surfaces | Where to look |
|---|---|---|
| Sentry | Code-level errors, unhandled exceptions | Sentry dashboard; alerts to **DECIDE**: email? Slack? Phone push? |
| Cloudflare Workers Logs | Operational issues, structured logs | Cloudflare dashboard → Workers → Logs |
| Cloudflare uptime / status page | Platform-level outages | https://www.cloudflarestatus.com |
| AWS Health Dashboard | RDS / S3 outages | AWS console |
| OpenRouter status | LLM gateway issues | https://status.openrouter.ai (verify URL) |
| `llm_calls` table queries | LLM quality / cost issues | Per `decisions/0006-observability.md` dashboard queries |
| HC pilot feedback channel | Anything user-visible the platform missed | **DECIDE**: where the channel lives (WhatsApp? Email? Dedicated Slack?) |

---

## Sentry alert rules

Three rules per ADR-0006 §7. Configure in: **Sentry → your project → Alerts → Create Alert Rule**.

### Rule 1 — New error fingerprint
- **Trigger**: first occurrence of any new issue fingerprint in the `production` environment
- **Action**: email SoJo immediately
- **Sentry UI**: Alert type = Issue → "A new issue is created" → filter: `environment:production`

### Rule 2 — Error rate spike (same fingerprint)
- **Trigger**: same issue fires > 5 times in 1 hour
- **Action**: email SoJo (escalation signal — something is actively broken)
- **Sentry UI**: Alert type = Issue → "The issue is seen more than 5 times in 1 hour"

### Rule 3 — LLM validation failure (pilot-critical)
- **Trigger**: any event tagged `kind=llm_validation_failed` during pilot, even once
- **Action**: email SoJo; treat as same-day review obligation
- **Sentry UI**: Alert type = Metric → Event type = Errors → filter: `kind:llm_validation_failed` → threshold: count > 0 in 24 h
- **Why**: the free-model chain is brittle (ADR-0001 risk #8); every validation failure during pilot must be reviewed to catch prompt regressions before the HC notices

**Verification step (do at P9 deployment)**: after configuring the rules, trigger Rule 1 deliberately — force an unhandled exception in the production Worker, confirm email arrives within 5 minutes and contains no PII.

---

## SEV-1 procedure

> **FILL IN** with actual contact methods/URLs as configured.

1. **Acknowledge** (within 5 min): note the time, post to incident channel (**DECIDE**: where), record in `SESSION_LOG.md`.
2. **Triage** (within 15 min): identify the failing component(s). Use:
   - Cloudflare Workers status
   - `/health` endpoint
   - Sentry first-occurrence breadcrumbs
   - DB connection check from local laptop with prod credentials
3. **Mitigate** (within 1 hour): goal = restore service to "users not blocked." Options:
   - Rollback to previous Worker deployment (per `deployment.md`)
   - Restart Worker (Cloudflare dashboard)
   - If DB is the issue: see `backup-restore.md`
   - Fail open vs fail closed: **DECIDE**. At MVP, prefer "show maintenance message" over "limp along with broken data."
4. **Communicate** (continuously): keep pilot HC informed. **DECIDE**: communication channel + frequency.
5. **Resolve**: confirm via a positive smoke test (`scripts/smoke-test.py`) that core flows work.
6. **Post-mortem** (within 7 days): write up in `docs/post-mortems/YYYY-MM-DD-<incident>.md`. Cover: timeline, root cause, mitigation steps taken, what worked, what didn't, follow-ups.

---

## Common scenarios — runbooks

### Worker returning 500 on most endpoints

Likely causes:
- DB connection broken (RDS issue, security group change, secret rotation gone wrong)
- Pyodide runtime issue after a Cloudflare platform update (ADR-0001 trigger #2 territory)
- Secret missing or invalid

Steps:
1. Check `/health` endpoint. If 500: backend code or DB issue. If 200: DB-bound endpoints specifically failing.
2. Check Cloudflare Workers Logs for stack traces.
3. If DB issue: try connecting from local with prod `DATABASE_URL`. If that fails: AWS RDS or networking. If that works: Cloudflare → AWS path issue.
4. If Pyodide issue: check Cloudflare community / status; rollback to last known-good deployment.

### LLM generation always failing

Likely causes:
- OpenRouter outage
- All free-tier models in the chain deprecated (ADR-0001 trigger #9)
- API key invalid or rate-limited
- Validation failure rate > 100% (model output drift)

Steps:
1. Check `llm_calls` recent rows: what's the `final_status`? `model_served` field?
2. If `failed_provider`: OpenRouter or upstream issue. Wait or escalate to OpenRouter support.
3. If `failed_validation`: model output drifted from prompt expectations. Test prompt manually via OpenRouter playground. May need prompt re-tune.
4. If 401 / 429 errors: API key or rate limit. Check OpenRouter dashboard.

### Auth broken (no one can sign in)

Likely causes:
- Google OAuth credentials revoked / changed
- JWT signing key rotated wrongly
- Cloudflare secret `GOOGLE_OAUTH_CLIENT_SECRET` corrupted

Steps:
1. Test sign-in flow yourself.
2. Check Cloudflare Workers Logs for OAuth callback errors.
3. Verify Google Cloud Console: OAuth credentials status, redirect URIs.
4. If JWT issuance fails: signing key issue; rotate to known-good per `secrets-management.md`.

### DB connection pool exhaustion

Likely causes:
- Workers spinning up many concurrent invocations, each opening DB connection (per ADR-0001 open follow-up: connection pooling not yet introduced)
- Long-running queries holding connections
- A slow LLM call inside a DB transaction

Steps:
1. Check RDS dashboard: active connections vs limit.
2. Identify long-running queries: `SELECT * FROM pg_stat_activity ORDER BY query_start;`
3. Kill specific bad queries: `SELECT pg_terminate_backend(pid);`
4. Mitigation: introduce Hyperdrive / PgBouncer / Supavisor (per ADR-0001 open follow-up).

### Secret compromised (suspected)

Per `secrets-management.md` "Suspected compromise procedure". Treat as SEV-1 if customer data may have been accessed.

### DPDP-relevant incident (data exposure or loss)

> **DECIDE**: under what conditions an incident becomes a DPDP notification trigger. The Rules finalize 13 Nov 2025; specific notification thresholds depend on `compliance-india.md` interpretation. **FILL IN** as `compliance-india.md` matures.

Steps:
1. Treat as SEV-1.
2. Quarantine: stop further exposure (revoke compromised access, disable affected endpoints).
3. Determine scope: which clients' data, which fields, time window.
4. Document timeline and findings.
5. **FILL IN**: notification procedure to affected clients and (if required) Data Protection Board. Defer specifics to `compliance-india.md` once DPDP enforcement timeline kicks in.

---

## Incident note template

When an incident is opened, paste this into `SESSION_LOG.md` (or wherever you log incidents):

```
## Incident YYYY-MM-DD-<short-name>

**Severity**: SEV-1 | SEV-2 | SEV-3 | SEV-4
**Detected at**: HH:MM IST
**Detected by**: [source]
**Resolved at**: HH:MM IST (TBD if ongoing)
**Impact**: [one sentence]

### Timeline
- HH:MM — [what happened or what was done]

### Root cause
[after resolution]

### Mitigation
[what brought it back online]

### Follow-ups
- [ ] [action item]
```

---

## Post-mortem template

> **DECIDE**: post-mortems folder location (suggestion: `docs/post-mortems/`).

```
# Post-mortem: <incident name> (YYYY-MM-DD)

## Summary
[2–3 sentences: what happened, who was affected, how long]

## Timeline
[events in chronological order with timestamps]

## Root cause
[the actual underlying reason; not the symptom]

## What went well
[what worked during the response]

## What went badly
[gaps, mistakes, slow points]

## Action items
- [ ] [actionable item]

## Lessons learned
[things to remember for next time]
```

---

## Things to revisit

- **Formal on-call rotation** when team > 1
- **Status page for clients** when scale warrants
- **Automated alerting via PagerDuty or similar** when manual monitoring becomes a bottleneck
- **Chaos engineering / game days** when reliability ambition is higher than "best-effort pilot"

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-04-28 | Initial template. | Incident response posture needs to exist before pilot launch. |
