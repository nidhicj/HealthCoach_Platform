# Tapas — Business Strategy for the Ideal-State Product

> **Purpose**: the commercial strategy behind the ideal-state vision in `tapas-ideal-state-vision.md` — why it wins, how it makes money, how it grows, and what it would take to sell outside India. This is a different horizon than `tapas-pilot-gtm-strategy.md`, which is tactical execution for the next 4–6 weeks; this document is the destination that plan is a first step toward.
>
> **Written**: 2026-07-30. Strategic direction confirmed in-session: venture-scale ambition, marketplace/network-effect moat, staged subscription→take-rate monetization.

---

## 1. The thesis

Tapas becomes the coordination layer independent health coaches and their clients can't operate outside of — not because it's the best note-taking tool, but because it's where coaches are *found* and where multi-practitioner care actually gets organized. A pure practice-management competitor (Practice Better, Healthie, Kore App) can copy any single feature in a quarter. None of them can copy a two-sided network without solving the same cold-start problem Tapas will already have solved by the time they notice it's worth copying.

---

## 2. Market sizing, staged

- **Immediate SAM**: solo, independent health coaches/dietitians/nutritionists in India running their own 1:1 client roster — the exact profile the pilot GTM targets, reachable today through professional bodies (IDA: ~13,000 members, 23 chapters) and direct outreach.
- **Expanding TAM (supply side)**: adjacent independent wellness practitioners who share the same administrative-overhead problem — fitness trainers, therapists/counselors, physiotherapists running solo practices. Not a near-term build target (Pillar F, later horizon), but the same moat logic extends to any 1:1, WhatsApp-dependent practitioner category.
- **Demand-side TAM (once Pillar C exists)**: everyone currently searching for a health coach through word-of-mouth, Instagram, or generic directories — a market Tapas doesn't currently participate in at all, because there's no client-facing discovery surface yet.

This is intentionally staged, not a single number, because the demand-side TAM only becomes real once Pillar C is built — quoting it as current addressable market today would be the kind of overclaiming the pilot GTM strategy was built specifically to avoid.

---

## 3. Competitive positioning at the ideal-state level

Today's tactical positioning (see `tapas-product-overview.md` §4) is feature-level: the coach-reviewed AI gate and the (unbuilt) macro-formula engine versus specific competitor gaps. That's the right positioning *for a pilot conversation with one coach*. It's the wrong positioning for the venture-scale story.

At the ideal-state level, the category reframe is: **Tapas isn't a better practice-management tool, it's the infrastructure layer neither a pure-SaaS incumbent nor a pure-marketplace newcomer can replicate quickly.** A SaaS incumbent (Practice Better, Healthie) would need to solve the two-sided cold-start problem from a standing start, with an installed base that has no reason to expect a marketplace from them. A marketplace-first newcomer would need to solve the practice-management depth Tapas already has a multi-year head start on by the time it matters. The moat isn't any single feature — it's that the two halves (deep practice tooling + real discovery liquidity) are much harder to build together than either alone, and Tapas is sequencing toward both from tooling that already works.

---

## 4. Monetization architecture — staged

**Stage 1 (now → pilot → early growth): subscription only**, exactly as priced in `tapas-pilot-gtm-strategy.md` §3 (₹999/month founding rate, ₹2,499 standard). This funds the business and drives the supply-side growth (coaches and their existing clients living inside Tapas) that Pillar C will eventually need as inventory.

**Stage 2 trigger condition**: Stage 2 does not begin on a calendar date — it begins once there's real client-side density inside Tapas (a meaningful number of clients actively using their `/me` portal, not just invited-and-dormant) such that a discovery layer would have genuine inventory to match against. Launching Pillar C before this condition is met means launching a marketplace with no supply worth discovering — the classic mistake of building the demand side before the supply side is real.

**Stage 2: take-rate layered on top, not replacing Stage 1.** Once Pillar C exists (subject to the §3.1/§3.2 preconditions in `tapas-ideal-state-vision.md`), a commission or lead-fee applies only to clients acquired *through the discovery surface specifically* — existing subscribers and their existing clients are unaffected and never double-charged. This also solves the attribution problem cleanly: only discovery-sourced clients are technically distinguishable as commission-eligible.

---

## 5. Growth sequencing

1. **Supply-side first** — get coaches and their existing clients living inside Tapas. This is precisely what `tapas-pilot-gtm-strategy.md` already targets; nothing changes here.
2. **Demand-side ignition** — once Stage 2's trigger condition is met, launch Pillar C to a subset of verified coaches first (opt-in, not platform-wide on day one), validate the discovery mechanic and the credentialing/moderation pipeline at small scale before opening broadly.
3. **Adjacent expansion (later horizon)** — other practitioner verticals, other geographies — only after the marketplace moat is proven in its first category and market. See §6 for the general treatment of what geography specifically would require.

---

## 6. Expansion outside India — general considerations only

India remains the confirmed core market; this section is intentionally kept high-level, not a deep compliance analysis, per explicit scope for this document.

**EU**: GDPR would govern instead of (or alongside) DPDP. In general terms this would mean EU data residency or an approved international-transfer mechanism, a Data Protection Officer once processing reaches a certain scale, more granular consent standards, and health data treated as "special category data" with a materially higher bar than DPDP currently sets. Directionally, Tapas' existing deletion-first, consent-table-from-day-one architecture (`CLAUDE.md` §9) points the right way rather than needing to be retrofitted — but DPDP compliance should not be assumed to imply GDPR compliance without its own review.

**US**: HIPAA applies specifically to healthcare providers/plans/clearinghouses and their business associates — whether Tapas would be in scope at all depends on how clinical the platform becomes, the same wellness-vs-clinical line already flagged in `CLAUDE.md` §10 regarding DISHA. A pure coaching/wellness tool may sit outside HIPAA entirely. Separately, payment rails would need to change (Razorpay is India-specific; a US/EU launch needs Stripe or equivalent) — a real but well-understood integration, not a novel problem. The competitive landscape is also materially different: Practice Better, Healthie, TrueCoach, and CoachAccountable are all established US-native incumbents, so the India-specific whitespace (the Kore App-shaped gap) doesn't transfer as an advantage.

**Bottom line**: nothing here is a near-term concern, and no architecture decision needs to change today because of it. This exists so the current build doesn't quietly get designed into an India-only corner over the next few phases, given the architecture already deliberately keeps this door open. Not legal advice — a real compliance review is a distinct, later project if either market becomes an actual near-term target.

---

## 7. Capital strategy implications

Venture-scale ambition with a marketplace thesis implies an eventual fundraise conversation, and that conversation needs actual proof points, not a pitch deck built on the vision alone:

- Active-HC count and week-over-week engagement (already tracked via the pilot GTM's §7 KPIs — this data starts accumulating from wave 1)
- Client-side portal activation rate — the leading indicator that Pillar C would have real inventory once built
- A working, credentialed-only discovery surface at small scale (§5 step 2) with at least a handful of real take-rate transactions — proof the Stage 2 model actually functions, not just that it's designed
- A clean account of the §3.2 access-control redesign (`tapas-ideal-state-vision.md`) if care-team features are live by fundraise time — investors evaluating a marketplace thesis in a health-data category will ask about this specifically, and "we haven't designed it yet" is a materially worse answer than "here's the model and here's how it's tested"

---

## 8. Risks specific to the marketplace moat

| Risk | Mitigation |
|---|---|
| Regulatory exposure on the discovery/matching surface (Drugs and Magic Remedies Act, Consumer Protection Act, DPDP purpose limitation) | Credentialing + content moderation + consent-scope work in `tapas-ideal-state-vision.md` §3.1/§3.3, treated as hard preconditions, not launch-day nice-to-haves |
| Cold-start: a marketplace with no demand-side liquidity is worthless, one with no verified supply is worse | Staged sequencing (§5) — supply-side proven first, opt-in small-scale discovery launch before broad rollout |
| Cultural resistance to commission models in a trust-sensitive health category | Take-rate applies only to discovery-sourced clients, never to the existing subscription relationship — framed explicitly as "we only earn more when we bring you something new," not a tax on the practice they already have |
| Off-platform circumvention undermining Stage 2 revenue | Retention through genuine on-platform value (AI drafting, calendar, payments), not technical enforcement — see `tapas-ideal-state-vision.md` §3.4 |
| Access-control failure in the care-team model creating a health-data leak | Treated as the single largest technical risk in this whole strategy (`tapas-ideal-state-vision.md` §3.2) — sequenced last among the real pillars specifically because of this |
