# Tapas — Ideal-State Product Vision & Gap Map

> **Purpose**: describe the product at full maturity — venture-scale, marketplace-moat end state — map today's build against it, and name the security/trust vulnerabilities that this specific vision introduces before they're discovered in production instead of in design.
>
> **Written**: 2026-07-30. Companion to `docs/business/tapas-product-overview.md`, `docs/business/tapas-security-review.md`, and `docs/business/tapas-pilot-gtm-strategy.md`. Strategic direction (venture-scale ambition, marketplace/network-effect moat, staged subscription→take-rate monetization) confirmed the same day — see session context.

---

## 1. The ideal-state product, in six pillars

**Pillar A — Core practice management.** Today's HC-facing loop (Unit_001/002), matured and hardened for real scale, not just pilot scale: AI-drafted session prep, MOM, action items, check-ins, style-snippet personalization, all behind the coach-reviewed gate.

**Pillar B — Full client engagement.** Today's client-facing surfaces (Unit_004), completed: check-ins/messaging, meal logging, in-app payments — a genuine WhatsApp replacement, not a partial one.

**Pillar C — Discovery/marketplace layer.** Clients find and select coaches *through* Tapas, not the other way around. HC public profiles, a matching/discovery mechanism, and the take-rate billing that monetizes it. This is the layer that converts Tapas from a tool coaches rent into infrastructure coaches (and clients) can't easily leave — the confirmed moat.

**Pillar D — Multi-practitioner care-team model.** Several HCs collaboratively serving one client (your newer idea, not yet in any spec) — Tapas as the coordination layer between practitioners around a shared client, deepening the network effect beyond single coach-client discovery.

**Pillar E — Trust & platform infrastructure.** Real deletion, consent, DSAR, audit, monetization (Unit_006, today mostly one-line-scoped) *plus a capability that doesn't exist in any spec today: HC credential verification* — see §3.

**Pillar F — Adjacent expansion (later horizon).** Other wellness-practitioner verticals, other geographies. Deliberately not a near-term pillar — see `tapas-venture-strategy.md` §6 for the general (not deep) treatment of what this would require.

---

## 2. Maturity map — current state vs. ideal state

Scale: **0** Not started · **1** Conceptual/specced only · **2** Partial build · **3** Shipped, pilot-scale · **4** Mature, hardened at scale

| Pillar | Current maturity | State |
|---|---|---|
| A — Core practice management | **3** | Shipped and stable for pilot scale (Unit_001/002). Not yet hardened for real scale — rate limiting, session-ceiling, and the other gaps in `tapas-security-review.md` §2.1 are still open. |
| B — Client engagement | **2** | Partial. F1 (action items email), F6 (calendar), F8 (diet chart + versioning) shipped. F2 remainder (check-ins lifecycle, messaging), F3 (meal logging), F4 (payments) specced but unbuilt. |
| C — Discovery/marketplace | **0** | Not started. Exists only as an unresolved idea from Unit_003 planning (the "BumbleBFF" swipe-discovery concept) — no spec, no schema, no ADR. |
| D — Multi-practitioner care teams | **0** | Not started, and structurally blocked by the current design: `docs/decisions/0005-auth-strategy.md` makes "every Client belongs to exactly one HC" a foundational, tested invariant. This pillar requires *replacing* that invariant, not extending it. |
| E — Trust & platform infrastructure | **1** | Unit_006 PHASE-01 is ready for an implementation plan; PHASE-02 through PHASE-07 are one-line-scoped only. HC credential verification (§3) doesn't exist as a concept anywhere in the current spec set. |
| F — Adjacent expansion | **0** | Not started; explicitly a later horizon, not a current gap to close. |

**Read**: the product is furthest along exactly where it started (B2B practice-management tool for a single coach). Every pillar that constitutes the *actual moat* you chose (C, D) is at zero — not behind schedule, simply not yet begun, because the current architecture was correctly built for the tool business, not the marketplace business, and hasn't needed to be anything else yet.

---

## 3. Security & trust vulnerabilities the ideal-state vision introduces

`tapas-security-review.md` audited the code and specs that exist today. This section is different in kind: it identifies vulnerabilities that **don't exist yet because the features that would create them don't exist yet** — but that the ideal-state vision, once pursued, will introduce as certainly as the current codebase introduced its own findings. Each needs to be designed against *before* the relevant pillar is built, the same way Phase 0 of the pilot GTM plan treats today's hard blockers as preconditions, not parallel work.

### 3.1 — [Critical] No health-coach identity/credential verification exists at all

Today, onboarding is Google OAuth only (`auth/router.py`): it authenticates *identity* (this person owns this Google account) but never authorizes *qualification* (this person is actually a trained or certified health coach). This is currently contained because SoJo personally selects every pilot HC by hand — the product performs no vetting, and none is needed, because the relationship layer does the vetting instead.

**That containment disappears completely in the marketplace model.** A client who discovers a coach through Tapas' own discovery surface is trusting *Tapas' selection*, not SoJo's personal judgment. An unverified account offering health/nutrition guidance under an implied platform endorsement is a platform liability, not just a rogue user renting software.

**Why this is harder than it looks**: India has no single unified licensing/registration body for "health coach" the way medicine has NMC registration. A real dietitian may hold IDA membership, a university degree in nutrition/dietetics, or an internationally recognized wellness-coaching certification (ISSA, ACE, NASM, Precision Nutrition, etc.) — there is no one government database to check a license number against. A credentialing pipeline has to accept multiple credential types and verify each against its actual issuing body, with manual review for the long tail of legitimate-but-non-standard credentials — it cannot be a single automated lookup.

**What's needed before Pillar C ships**:
- A credential-submission step in onboarding (document upload: degree, certification, or professional-body membership)
- A verification workflow — manual review queue is sufficient at launch; it does not need automation on day one, but it does need to exist and be enforced before any client-facing discovery goes live
- A "verified" status that gates *visibility in discovery specifically* — unverified accounts can still use the practice-management tools privately (today's model is unaffected), but never appear in client-facing search. This decouples "can use the software" from "can be found through the marketplace," so credentialing doesn't have to block Pillar A/B usage, only Pillar C.
- Re-verification/expiry and a revocation path — certifications lapse, and fraud is sometimes discovered after the fact, not at signup

**Resolves via**: this is a hard precondition for Pillar C, not a parallel workstream — the same logic as the pilot GTM's Phase 0.

### 3.2 — [Critical] The access-control model doesn't support multi-practitioner care teams, and this is the single largest new attack surface in the whole vision

Today's tenant isolation is deliberately simple: every Client belongs to exactly one HC, enforced at the query layer, verified by 10+ cross-tenant integration tests (`docs/decisions/0005-auth-strategy.md`). This is precisely *why* it's secure — one simple invariant is easy to verify and hard to get wrong, and the security review found no findings against it.

The care-team model breaks that invariant at the root. It requires a genuine many-to-many HC-client relationship with **per-practitioner, per-data-category scoped permissions** — not every HC collaborating on a shared client should see everything by default (e.g., a nutritionist on a shared case has no inherent reason to see a different practitioner's private session notes on the same client, even though both are legitimately treating that client).

This is flagged as the single largest new vulnerability class in this document because it directly touches the one property the current system is most confidently correct about. Getting it wrong doesn't create a narrow bug — it creates a structural cross-tenant-style leak inside what looks, on the surface, like normal in-team collaboration. **This needs its own from-scratch authorization design** (capability-based or consent-scoped grants per HC × client × data-category) before any care-team feature is built — not an incremental patch onto the existing `current_tenant()` dependency.

### 3.3 — [High] Consent-scope creep: using health data to power matching/discovery is a new purpose requiring new consent

DPDP's purpose-limitation principle means consent collected for "my coach manages my sessions" does not automatically extend to "Tapas uses my health profile to recommend coaches to me, or to rank me/my coach in a discovery algorithm." Any signal derived from sensitive health data for matching purposes needs its own explicit, separately scoped consent — and the signal itself should be minimized (broad interest categories like "PCOD support," not raw clinical detail feeding a ranking model).

This intersects directly with a concern already on record in project memory from the original marketplace discussion: HC public profiles and any client-visible outcome claims need content moderation against false or unsubstantiated medical-effect advertising (Drugs and Magic Remedies Act, Consumer Protection Act) before anything is client-facing — not an afterthought once profiles exist.

### 3.4 — [High] Marketplace trust & safety: fake profiles, review manipulation, off-platform circumvention

Once a client-facing discovery surface exists, expect three distinct problems, not one:
- **Sybil/fake HC accounts** — mitigated primarily by §3.1's credentialing gate, but also needs basic anomaly detection on bulk account creation, since credentialing alone doesn't stop volume abuse of the signup flow itself
- **Review/ranking manipulation** — once any rating or ranking mechanism exists, it needs to be restricted to verified-transaction reviews only (a client who actually had a session), never open/anonymous reviews
- **Off-platform circumvention** — coaches and clients who meet through Tapas' discovery layer moving the relationship to WhatsApp to avoid any take-rate fee. This is as much a business-model risk as a security one, and it can't be solved technically (two people who've exchanged names can always leave). It has to be solved by making the on-platform experience genuinely better than leaving — the AI-assisted drafting, calendar integration, and payment convenience already being built are the actual retention mechanism, not an enforcement rule.

### 3.5 — [Medium] Take-rate billing introduces a new financial-fraud surface at marketplace scale

Once real commission money moves through the platform, expect attribution disputes (an HC claiming a client arrived organically to avoid the fee) and a materially larger target for payment fraud than today's model, where Tapas never touches client money at all (HCs self-onboard their own Razorpay account, Unit_004 F4). This compounds the already-flagged predictive finding in `tapas-security-review.md` §3 about Razorpay webhook signature verification and replay/idempotency — at marketplace scale, that work needs to be done rigorously once, before commission revenue depends on it, not retrofitted under pressure.

### 3.6 — [Medium] Coach-reviewed-gate integrity under volume and incentive pressure

The coach-reviewed gate (nothing AI-drafted reaches a client until the HC edits and sends it) is currently verified as a data-model invariant (`moms.status`: draft → reviewed → sent) for a small number of engaged pilot HCs who have every reason to review carefully. At marketplace scale — more volume, and once Stage 2 take-rate monetization creates a real incentive to move faster to capture more commission-eligible clients — there's a genuine risk the gate becomes a rubber-stamp: the architecture still enforces "an HC clicked send," but not "an HC meaningfully reviewed it." This isn't classic infosec, but it's a real trust-integrity risk specific to what makes Tapas different in the first place. Worth tracking as an actual metric as usage scales (e.g., time between draft and send, edit-distance between AI draft and sent version), not just as a launch-time architectural checkbox that's assumed to hold forever.

### 3.7 — Prioritized summary

| Priority | Item | Gates |
|---|---|---|
| Critical | No HC credential verification pipeline exists | Pillar C (discovery/marketplace) cannot ship without this |
| Critical | No access-control model for multi-practitioner care teams | Pillar D cannot be built without a from-scratch authorization redesign |
| High | No consent-scope mechanism for health-data-driven matching | Pillar C — required before any client health data feeds a recommendation/ranking signal |
| High | No content-moderation layer for HC profiles / client-visible claims | Pillar C — required before profiles are client-facing |
| Medium | No marketplace trust & safety mechanisms (review integrity, off-platform retention strategy) | Pillar C, ongoing after launch |
| Medium | Take-rate billing fraud surface not yet designed for | Stage 2 monetization (see `tapas-venture-strategy.md` §4) |
| Medium | Coach-reviewed-gate integrity has no monitoring at scale | Cross-cutting, becomes relevant as volume grows regardless of pillar |

**Not legal advice.** Several of these (credentialing, content moderation, consent-scope) sit close to real regulatory exposure — DPDP purpose limitation, Drugs and Magic Remedies Act, Consumer Protection Act. Treat this section as an engineering/product design brief, and get counsel review before Pillar C or D design work locks in specifics, consistent with `CLAUDE.md` §10.

---

## 4. What has to get built, by pillar

| Pillar | Major initiative required | Depends on |
|---|---|---|
| A | Hardening pass: rate limiting, session ceilings, the rest of `tapas-security-review.md` §2.1 | Nothing — can proceed independently, already largely scoped via the pilot GTM's Phase 0 |
| B | Complete F2 remainder, F3, F4 | Nothing new — already specced, just unbuilt |
| C | Discovery/marketplace surface: public HC profiles, matching mechanism, take-rate billing | §3.1 (credentialing) and §3.3/§3.4 (consent + content moderation) as hard preconditions |
| D | Multi-practitioner care-team data model and authorization redesign | §3.2 — cannot be scoped safely until the new access-control model is designed |
| E | Unit_006 PHASE-02 through PHASE-07, plus a new credentialing phase not currently in any spec | Independent, but credentialing phase blocks Pillar C |
| F | Not scoped — later horizon | Everything else; see `tapas-venture-strategy.md` §6 for the general treatment |

---

## 5. Why this build order, not another

Pillar A and B come first because they're the only pillars that can honestly earn subscription revenue today — this is exactly the sequencing logic behind the pilot GTM's Phase 0 and the staged monetization model in `tapas-venture-strategy.md`. Pillar E's credentialing work has to land *before* Pillar C, not alongside it, because Pillar C without §3.1 solved isn't a smaller or safer version of the marketplace — it's the same platform-liability exposure, just live. Pillar D is sequenced last among the "real" pillars specifically because §3.2 is the largest structural risk in this entire document: building the care-team feature before the authorization model is properly designed doesn't save time, it creates a cross-tenant-style vulnerability inside a feature that will look, to everyone testing it, like it's working correctly.
