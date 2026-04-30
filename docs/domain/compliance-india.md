# India Compliance — DPDP & Operational Posture

> **MERGE-REQUIRED**: existing `compliance-india.md` in repo from prior sessions. This draft incorporates the 13-Nov-2025 DPDP Rules finalization and the pragmatic-prototype-scope stance per ADR-0001. Reconcile when committing.

> **NOT LEGAL ADVICE.** This is the operator's working summary. Any production-facing compliance posture (privacy policy text, consent UX, breach notification procedures) requires lawyer review before launch.

---

## Status as of 2026-04-28

**DPDP Act 2023 Rules**: finalized 13 November 2025. Staggered enforcement.

| Component | Status |
|---|---|
| Foundational provisions (definitions, fiduciary duties basics) | In force from notification |
| Consent Manager registration regime | 12-month phase-in (~Nov 2026) |
| Remaining provisions (DPO requirements, full grievance redressal, advanced consent flows) | 18-month phase-in (~May 2027) |
| Cross-border data transfer | Negative-list approach — transfers permitted by default; specific countries may be blacklisted by future government notification. As of this date, no blacklist has been published. |

**Practical implication for our timeline**: Pilot launch (target: 2026 Q3 with 1 HC + ~5 clients) falls during the 12-month phase-in window. Full DPDP UX is not legally required by pilot date, but architectural hooks must be in place so we can comply within the 18-month enforcement window.

---

## Prototype scope — what's IN, what's DEFERRED

This is the explicit pragmatic-vs-literal stance from ADR-0001. We do NOT block prototype development on full DPDP compliance UX. We DO ensure architectural hooks exist so adding compliance UX later is a feature, not a rewrite.

### IN for prototype (architectural hooks — non-negotiable)

| Hook | Implementation | Why it can't be deferred |
|---|---|---|
| Consent table | `consents` table per `diagrams/0002-data-model.md`. Tracks per-client, per-purpose consent with timestamps and source. | Adding consent retroactively to an in-flight system requires re-establishing consent for every existing record. Painful and arguably non-compliant. |
| India-region data residency | AWS RDS Mumbai (ap-south-1) and S3 Mumbai. | Migrating regions is multi-day work + brief downtime. |
| Real deletion capability | `ON DELETE CASCADE` on every client-scoped FK. Single-transaction purge. Test suite asserting no orphan rows. | "Soft delete" is incompatible with DPDP erasure rights. Retrofitting hard delete to a soft-delete system is risky and error-prone. |
| `client_id` traceability on snippets | `hc_style_snippets.client_id` FK with cascade. Snippets containing client context are purged on revocation. | Per ADR-0003 §7. Easy to forget when adding new tables; hard to retrofit. |
| Purpose-of-processing log | Each `consents` row has a `purpose` field (enum: `coaching`, `analytics`, `model_training` (always false at MVP), etc.). | Future audit requires evidence of consent scope. |

### DEFERRED past prototype (UX features — to be added before any non-pilot HC)

| Feature | When | Notes |
|---|---|---|
| Consent UX (signup flow consent screens, granular consent toggles) | Before second HC onboarded | Pilot HC consents via signed PDF, captured operationally. Not scalable but defensible at N=1. |
| Data Subject Access Request (DSAR) endpoints | Before second HC onboarded | At pilot, manual export by operator on request. |
| Grievance redressal contact + UX | Before public marketing | Email-based suffices initially. |
| Data Protection Officer (DPO) appointment | Required at "Significant Data Fiduciary" threshold (TBD by gov; not yet published) | We are far below this scale. Re-evaluate at 1000+ clients or before regulator inquiry. |
| Consent Manager integration | When Consent Manager regime is active (~Nov 2026) AND we have multiple HCs | Optional even when active; depends on scale. |
| Breach notification procedure | Before any non-pilot client | Internal runbook + 72-hour notification target. Lawyer-reviewed. |

---

## Cross-border data transfer

The 13-Nov-2025 Rules adopted a **negative-list** approach: transfers to other countries are permitted unless that country is on a blacklist published by the government. **No blacklist exists as of this date.**

**Practical implications**:

1. **OpenRouter LLM calls**: route through OpenRouter (Singapore-based per their public docs, but routes to upstream providers including US-based Anthropic, OpenAI, Meta, Google) — permitted under negative-list. Mitigations applied:
   - OpenRouter account-level "no training" setting verified before any client data flows
   - Per-call retention controls applied where supported
   - Snippets and PII minimized in prompts (use IDs, summaries, not raw transcripts where avoidable)
2. **Google OAuth**: identity verification routes through Google US — permitted.
3. **Sentry / error monitoring**: if Sentry self-hosted in EU/US is used, this is cross-border. Permitted, but disclose in privacy policy.

**Risk to monitor**: government publishes a blacklist that includes the US (low probability near-term, non-zero long-term geopolitically). If this happens:
- Anthropic / OpenAI / OpenRouter access via US becomes restricted
- Mitigation: route LLM calls via Bedrock Mumbai (already validated as available in ADR-0001 verification) — same Anthropic models, India-region inference
- Architectural impact: minimal (model-ID change in OpenRouter or fallback to Bedrock SDK)

This is captured here so the response is pre-thought, not improvised under deadline.

---

## Consent — what we ask for, when, why

### MVP consent scope (per pilot HC, in writing)

The pilot HC's clients consent at M000 (first session) to:

1. **Service provision** — necessary processing for delivering coaching: store contact info, sessions, MOMs, action items, content library access.
2. **AI-assisted content generation** — explicit consent that AI is involved in drafting MOMs and briefs (HC always reviews before sending). Names the LLM provider category, not specific models.
3. **Cross-border processing** — explicit consent that LLM calls may be processed by upstream providers in jurisdictions outside India, under purpose limitation (no training on the data).
4. **Snippet capture** — explicit consent that HC's edits to AI drafts may be stored as style references for future drafts (i.e., the snippet library, with the disclosure that snippets may contain client conversation context).
5. **Erasure right** — client may request deletion at any time; we will execute within 30 days; deletion is hard delete (not soft).

### What we do NOT ask consent for at MVP

- Marketing communications — none sent at MVP
- Third-party data sharing — none happens at MVP
- Profiling for advertising — none happens; not the product

### Consent capture mechanism (MVP)

PDF, signed digitally or wet-signed, scanned to S3 Mumbai. `consents` table records the existence and scope of the signed agreement. Not scalable beyond pilot; flagged for replacement before second HC.

---

## Data inventory — what we collect, where it lives

| Data type | Source | Storage | Retention |
|---|---|---|---|
| HC account info (email, name) | Google OAuth | RDS Mumbai (`users` table) | Indefinite during account; deleted on HC offboarding |
| HC profile (specialty, photo, etc.) | HC self-input | RDS Mumbai (`users` + `hc_profiles`) | Same as above |
| Client info (name, contact, demographics) | HC entry at M000 | RDS Mumbai (`clients` table) | Until consent revoked or HC-initiated deletion |
| Session transcripts (Zoom-imported) | Zoom webhook (post-session) | S3 Mumbai + reference in `sessions` table | 90 days, then archived; auto-purge configurable per HC |
| MOM, briefs, action items | LLM-generated, HC-edited | RDS Mumbai (`moms`, `briefs`, `action_items`) | Indefinite during course; purged on revocation |
| Snippet library | Captured from HC edits | RDS Mumbai (`hc_style_snippets`) | Until revocation; purged on client deletion |
| LLM call telemetry | Backend instrumentation | RDS Mumbai (`llm_calls`) | Indefinite (no client PII; only IDs) |
| Consent records | Operational (PDF) | S3 Mumbai + `consents` table | Indefinite (legal record) |
| Audit log (operator actions) | Backend instrumentation | RDS Mumbai (`audit_log`) | Indefinite (legal record) |
| Logs / errors | Sentry + structured logs | Sentry (verify region setting) + Cloudflare Logs | 30 days |

---

## Open questions / research needed

- **Sentry data residency**: verify Sentry org is configured in EU/US-Cloud — determine which is acceptable disclosure-wise. Self-hosted Sentry in Mumbai is overkill at MVP scale.
- **Consent Manager integration timeline**: monitor for first registered Consent Managers (~Nov 2026). When ecosystem matures, decide whether to integrate or self-manage consent UI.
- **DPDP "Significant Data Fiduciary" criteria**: not yet published at finalization date. Monitor for notification.
- **Children's data**: clients are adults at MVP (HC's discretion to enforce). If children's coaching becomes a use case, parental consent regime under DPDP §9 applies — separate ADR.

---

## References

- DPDP Act 2023 (full text via MeitY): [search and verify current URL]
- DPDP Rules 2025 finalization (IAPP coverage, Nov 2025): https://iapp.org/news/a/with-rules-finalized-india-s-dpdpa-takes-force
- `decisions/0001-stack-selection.md` — pragmatic DPDP stance
- `decisions/0003-llm-strategy.md` §7 — snippet privacy enforcement
- `legal/privacy-policy.md` — public-facing version (NEEDS LAWYER REVIEW)

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-28 | Fresh draft incorporating 13-Nov-2025 Rules finalization, negative-list cross-border regime, and prototype-scope pragmatic stance. MERGE-REQUIRED with existing repo file. |
