# ADR-0002: Runtime Topology — Diagnostic-Driven Fallback Playbook

**Status**: Accepted
**Date**: 2026-04-28
**Decision driver**: SoJo (solo founder)
**Supersedes**: n/a
**Relates to**: ADR-0001 (Stack Selection) — this ADR refines, does not replace
**Triggered by**: External architect input proposing JS Worker + Python service runtime split (2026-04-27)

---

## Context

ADR-0001 settled the stack: FastAPI on Cloudflare Python Workers (primary), DigitalOcean Bangalore as named fallback, AWS RDS/S3 Mumbai for data, OpenRouter for LLM gateway. ADR-0001 named **six hosting-layer migration triggers** and a **single fallback response**: when any trigger fires, migrate the backend to DO Bangalore.

On 2026-04-27, an external senior architect proposed a different topology: a **JS/TS Worker at the edge** for auth, rate limiting, API gateway, caching, security, and edge delivery, paired with a **Python backend** for AI pipelines, RAG, recommendations, and LLM workflows. The architect's framing — *"where should each runtime live?"* rather than *"which language wins?"* — is sound senior thinking and is recorded here.

This ADR does **not** reopen ADR-0001's stack choice. It answers a related but distinct question: **when an ADR-0001 hosting trigger fires, is the right response always "go to DO Bangalore" — or is there an intermediate response (split runtimes) that's cheaper and faster for some failure modes?**

The decision below is: yes, there is. ADR-0002 encodes which trigger demands which response.

### Forces at play

- **Latency.** JS/V8 cold starts are ~5ms. Python via Pyodide is materially slower (snapshots help, but worst case is hundreds of ms for big bundles). For latency-sensitive edge concerns — auth check, rate limit, cache lookup — that gap can matter. For AI work already gated by a 1–5s LLM call, runtime cold start is invisible.
- **Cost mix.** Cloudflare Workers Paid is $5/month minimum; the $20/month trigger in ADR-0001 implies real usage above the free tier. *What* is consuming that budget determines whether splitting helps. Edge-flavored work on JS Worker is dramatically cheaper than the same work on Python Worker. AI-flavored work doesn't get cheaper from a runtime change; it gets cheaper from going to DO.
- **Solo-builder cognitive load.** Two runtimes = two language ecosystems, two CI configs, two debug surfaces, and a service-to-service auth boundary. Negligible cost for a 10-person team; non-trivial chunk of the week for one person building solo.
- **Cloudflare platform features ≠ Workers code.** Rate limiting, WAF, caching, DDoS protection are configured at the Cloudflare dashboard. We get most "edge concerns" benefits without writing a JS Worker at all. This is captured as an immediate one-time setup task, not a runtime split.
- **No second engineer planned.** SoJo is the team. No "split for team specialization" rationale applies to this product.

---

## Decision

**Single Python runtime stays default per ADR-0001.** Cloudflare's *platform features* (dashboard-configured rate limit, WAF, cache rules, DDoS) provide the "edge layer" without code.

**When an ADR-0001 hosting trigger fires, follow the diagnostic decision tree below.** Some triggers route directly to DO Bangalore (ADR-0001's named fallback). Others first try the runtime split. The split is therefore an **intermediate fallback** for specific failure modes, with DO Bangalore as the **escape hatch** when the split doesn't help or isn't viable.

The runtime split is *not* adopted preemptively. It is adopted reactively, on a named trigger, with a diagnosis confirming it's the right intervention.

---

## Diagnostic decision tree

When any ADR-0001 hosting trigger fires, walk this tree before opening a migration ADR.

### ADR-0001 Trigger #1 — Cold-start regression (p95 > 3s, 7-day window)

**Diagnose**: which endpoints are slow? Are they edge-flavored (auth check, rate limit, simple cache lookup) or AI-flavored (LLM call, complex business logic)?

- **Edge-flavored slow** → **try split first.** Move auth + rate limit + cache lookup endpoints to a JS/TS Worker (~5ms cold start). Python service handles AI + business logic. If this fixes p95, no DO migration needed.
- **AI-flavored slow** → **DO Bangalore directly.** Splitting doesn't help; the Python work itself is what's slow.
- **Both slow** → **DO Bangalore directly.** Split would only fix half; complexity isn't worth it.

### ADR-0001 Trigger #2 — Beta-driven outages (>2 platform-attributable in 30 days)

**Diagnose**: not really diagnosable. Platform reliability is platform reliability. Splitting onto two Cloudflare runtimes doubles the surface area exposed to platform issues, doesn't reduce it.

→ **DO Bangalore directly.** Split doesn't help here.

### ADR-0001 Trigger #3 — Required Python package not Pyodide-compatible

**Diagnose**: which package, where is it used? Is it on a request hot path or in a batch job?

- **Workaround exists** (alternative pure-Python package, JavaScript equivalent for that specific endpoint) → **try workaround first.** A specific endpoint hitting a Pyodide-incompatible dep can sometimes be split off to a JS Worker. Document the asymmetry; track scope creep.
- **No workaround for core functionality** → **DO Bangalore directly.** The Python ecosystem requirement was the whole point of choosing Python.

### ADR-0001 Trigger #4 — Subrequest or wall-time limit hit

**Diagnose**: which endpoints? Are they bounded by Cloudflare's 50/1000 subrequest cap or 30s wall-time?

- **A few specific endpoints exceed limits** → **try split first** if those endpoints can be moved off Cloudflare (e.g., to a small Python service on DO for just those routes, with the rest staying on Workers). This is not the JS+Python split — it's a hybrid Cloudflare+DO split. Sometimes correct, sometimes overkill.
- **Many endpoints exceed limits** → **DO Bangalore directly.** Workers is not the right shape for this workload.

### ADR-0001 Trigger #5 — Cost crossover (Cloudflare Workers paid usage > $20/month)

**Diagnose**: which line item drove cost? Cloudflare's metrics page shows requests vs. CPU-ms vs. bundle/storage. Cross-reference with `ops/cloudflare-cost-reference.md`.

- **Edge-flavored requests/CPU dominate** (high request count on simple endpoints — auth, rate limit, health checks) → **split runtimes.** Move those to JS Worker (free tier or much cheaper). Python service stays on Workers Paid for AI work, or moves to DO if AI work is also expensive.
- **AI-flavored CPU dominates** (long FastAPI requests handling LLM calls and business logic) → **DO Bangalore directly.** Splitting doesn't reduce this cost; only moving compute to a flat-rate VPS does.
- **Bundle size forced Paid plan but usage is otherwise low** → **try bundle reduction first** (move static config to KV/R2, drop unused deps). If unfixable, consider split (smaller Python bundle for AI, JS for edge) or accept Paid plan as the cost of the architecture.

### ADR-0001 Trigger #6 — `workers-py` blocker matures into hard requirement

**Diagnose**: which blocker, which feature?

- **#27 Cron Triggers needed for production** and external scheduler workaround is failing → **DO Bangalore directly** (Linux cron / Celery Beat works there). Split doesn't help.
- **#68 httpx UA / OAuth issues become un-workaroundable** → **DO Bangalore directly.** Same reason.
- **A new `workers-py` blocker emerges** → diagnose case by case using the same edge-vs-AI logic above.

---

## Rationale

1. **The architect's framing is correct; the timing is conditional.** "Where should each runtime live?" is a sound question. The answer at our scale is: one runtime is fine *until specific evidence says otherwise*. ADR-0002 names what that evidence looks like.
2. **The dominant latency budget is the LLM call (1–5s), not runtime cold start.** Optimizing the invisible part while the visible part dominates is wrong-priority engineering. Runtime split helps only when cold start becomes user-visible — which is exactly what trigger #1 measures.
3. **Cloudflare platform features capture most "edge layer" intent for free.** Dashboard-configured rate limit, WAF, cache, DDoS protection — these solve the architect's stated edge concerns without a JS Worker. We adopt these immediately as a one-time setup (see Open follow-ups), independently of this ADR's split decision.
4. **Splitting runtimes addresses some triggers and not others.** ADR-0001's previous structure ("any trigger → DO") was too coarse. The diagnostic tree above is the refinement: split helps for cost-mix and cold-start-on-edge problems; it doesn't help for platform reliability, deep Pyodide blockers, or AI-workload weight.
5. **Solo builder + day job = complexity is the dominant variable cost.** Adopting the split preemptively burns hours/week that come directly out of product velocity. Adopting it reactively, with the trigger and diagnosis in writing, is the correct tradeoff.

---

## Consequences

### What this enables

- **All of ADR-0001's enables remain intact.** Single Python codebase, single deploy pipeline, one debug surface as default.
- **Cloudflare platform features as the de-facto edge layer.** Rate limit, WAF, cache rules, DDoS — configured at dashboard, no code.
- **Trigger-driven evolution.** When a hosting trigger fires, future-SoJo doesn't relitigate the architect's framing. The decision tree above is the playbook.
- **Future migration ADR has a clear parent and a clear diagnosis.** Whichever response we take (split or DO), it's traceable to a specific signal.

### What this costs

- **If a trigger fires and the tree says "split," the split itself is 1–2 weeks of work.** Mostly: designing the JS Worker → Python service auth boundary (signed JWT in headers, Python re-validates or trusts via service binding), splitting deploy pipelines, doubling observability config.
- **The "two runtimes" pattern is not in muscle memory.** We'll be designing the boundary while we need it. Mitigation: rough sketch in this ADR's Appendix below; expanded if/when we adopt.
- **Cloudflare platform features must be enabled separately.** Not automatic. See Open follow-ups.

---

## Step sequence — how this ADR plays out over time

1. **Today (2026-04-28)**: ADR-0002 Accepted. Single Python runtime continues. Cloudflare platform features (rate limit, WAF, cache rules) get enabled at dashboard level — one-time setup task tracked in Open follow-ups.
2. **Ongoing**: ADR-0001's six hosting triggers are observable from existing telemetry. No new monitoring needed.
3. **If a trigger fires**: open a new ADR (e.g., ADR-00XX: "Adopt Runtime Split" or "Migrate to DO Bangalore"). Cite (a) which trigger fired, (b) what the evidence was, (c) which branch of this ADR's decision tree it routes to. Then execute.
4. **If no trigger fires for 12 months**: leave this ADR Accepted. Re-read at the 12-month mark if anything else has materially changed.
5. **If ADR-0001 is itself superseded** (e.g., we move off Cloudflare entirely): ADR-0002 is partially mooted. Supersede with an updated ADR for the new platform context.

---

## Appendix — auth boundary sketch (for future use)

If/when the split is adopted, the JS Worker → Python service auth handoff:

- **JS Worker** validates incoming JWT (Google OAuth flow stays the same, JWT signing key shared)
- **JS Worker** forwards request with user identity in signed headers (e.g., `X-User-Id`, `X-Session-Id`, signed with HMAC over a shared secret)
- **Python service** verifies the HMAC (cheap) and trusts the headers
- **Python service** is not directly reachable from the public internet (Cloudflare Service Binding or origin-restricted)

This is a sketch. Full design happens in the migration ADR if/when needed.

---

## Open follow-ups

- **One-time task** (claude.ai → Claude Code): enable Cloudflare's rate limiting, WAF, and basic cache rules at the dashboard level for the production Worker. Track in `SESSION_LOG.md`.
- **Watch-list**: add the six ADR-0001 hosting triggers to monthly review checklist (`ops/cloudflare-cost-reference.md` §8 already covers usage; outages and Pyodide errors need their own log).
- **Cost reference**: `ops/cloudflare-cost-reference.md` is the source of truth for what triggers cost-related signals.

---

## References

- `decisions/0001-stack-selection.md` — the parent decision this ADR refines
- `ops/cloudflare-cost-reference.md` — cost-side trigger evidence
- External architect input, 2026-04-27 (informal; conversation log in this Project)
- Cloudflare Workers runtime model (Pyodide vs V8): https://developers.cloudflare.com/workers/languages/python/how-python-workers-work/

---

## Changelog

| Date       | Change                        | Reason                                                                                                                     |
| ---------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| 2026-04-28 | Initial draft and Acceptance. | External architect input proposed runtime split; this ADR encodes when it's the right response vs. ADR-0001's DO fallback. |
