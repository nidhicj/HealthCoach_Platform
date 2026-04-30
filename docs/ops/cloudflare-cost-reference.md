# Cloudflare Cost Reference

> **Status**: Reference doc (filled in). Contains verified facts about Cloudflare Workers limits and pricing as of 2026-04-28. Re-verify when a meaningful interval passes (suggestion: every 6 months) — Cloudflare's pricing and limits do change.

> **Purpose**: bookmarkable reference for evaluating ADR-0001 cost trigger (#5: monthly Cloudflare Workers paid usage > $20). When billing approaches the trigger, this doc tells you what to look at and where the real costs come from.

---

## Cloudflare Workers — Free tier limits

Verified from Cloudflare docs as of 2026-04-28.

| Resource | Free tier limit |
|---|---|
| Requests | 100,000 / day |
| CPU time per request | 10 ms (sustained) |
| Memory | 128 MB |
| Worker bundle size | 3 MiB compressed |
| Subrequests per request | 50 |
| Wall-time per request | 30 seconds CPU |
| Workers Logs events | 200,000 / day |
| Number of Workers | 100 per account |

For pilot scale (1 HC + ~5 clients), Free tier covers everything by orders of magnitude. The limits that matter most as we approach paid:
1. **Bundle size** (3 MiB) — most likely first paid trigger. FastAPI + SQLAlchemy + Pydantic + httpx + asyncpg + boto3 estimated 3–8 MiB compressed. Actual is unknown until first `pywrangler deploy`.
2. **Requests/day** — far above expected pilot volume; not a near-term concern.

---

## Cloudflare Workers — Paid tier (Standard)

| Item | Cost |
|---|---|
| Minimum monthly subscription | $5/month |
| Requests included | 10,000,000 / month |
| CPU-ms included | 30,000,000 / month |
| Worker bundle size | 10 MiB compressed |
| Workers Logs events | 20,000,000 / month included |
| Per million additional requests | $0.30 |
| Per million additional CPU-ms | $0.02 |

Going from Free to Standard is a big jump in headroom — the included quotas are enormous relative to pilot scale. The $5/month minimum is the baseline cost.

---

## Cloudflare Pages

Free tier:
- 500 builds/month
- Unlimited requests
- Unlimited bandwidth
- 100 custom domains

For pilot scale, Free tier is fine indefinitely.

---

## Other Cloudflare products considered

| Product | Used? | Cost notes |
|---|---|---|
| R2 (object storage) | No (using AWS S3 Mumbai for India residency) | Free egress; first 10 GB storage free |
| D1 (SQLite at edge) | No (using AWS RDS Mumbai per ADR-0001) | Free tier exists; revisit per ADR-0001 open follow-up |
| Hyperdrive (DB connection pooling) | Likely yes, eventually | Free at low usage; per ADR-0001 open follow-up |
| KV (key-value store) | Possibly for sessions/caches if added later | Free tier available |
| Durable Objects | Not at MVP | Charged separately |

---

## What drives Cloudflare cost (in expected order of impact)

For this product, at this scale:

1. **Bundle size** going past 3 MiB compressed → forces upgrade to Paid ($5/mo minimum).
2. **Workers Logs events** going past 200k/day → forces upgrade or log scrubbing.
3. **CPU time** if any endpoint runs > 10ms sustained on Free → forces upgrade.
4. **Subrequests per request** if any endpoint makes > 50 outbound calls → architecture change needed.

Past the upgrade threshold, the cost ramp is gentle until volumes get much larger than pilot scale.

---

## Verifying current usage

### Bundle size
```bash
cd backend
uv run pywrangler deploy --dry-run
# Output includes the actual compressed size
```

### Request volume
Cloudflare dashboard → Workers → your Worker → Metrics → Requests.

### CPU time
Same dashboard → Metrics → CPU time. Look for p95 / p99.

### Logs volume
Cloudflare dashboard → Workers → Logs → usage.

### Cost projection
Cloudflare dashboard → Billing → Usage. Shows current month projection.

---

## Monthly review checklist

> Suggested cadence: monthly during pilot. Quick check, not deep dive.

- [ ] Bundle size — current vs Free tier limit (3 MiB)
- [ ] Daily request volume — current peak vs Free tier limit (100k)
- [ ] CPU time p95 — vs limit (10 ms sustained)
- [ ] Logs daily count — vs limit (200k)
- [ ] Monthly cost projection — vs ADR-0001 trigger #5 ($20)
- [ ] Any alerts or warnings on the Cloudflare dashboard

If the projection is approaching $20/month at sustained pilot scale, that's a real signal — not noise. Per ADR-0002, diagnose what's driving it before responding.

---

## Verification log

> Update this section when the data above is re-verified against Cloudflare's current pricing/limits.

| Date | Verified by | Source URLs | Notes |
|---|---|---|---|
| 2026-04-28 | SoJo + Claude (initial) | https://developers.cloudflare.com/workers/platform/limits/ ; https://www.cloudflare.com/plans/developer-platform/ | Initial creation; specs above reflect Free + Standard tier as of this date |

---

## Update log

| Date | Change | Reason |
|---|---|---|
| 2026-04-28 | Initial creation. | ADR-0001 trigger #5 evaluation needs a reference for limits and costs. |
