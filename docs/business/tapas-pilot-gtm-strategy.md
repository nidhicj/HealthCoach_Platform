# Tapas — Pilot Go-to-Market Strategy (Wave 1)

> **Purpose of this document**: an executable plan for taking Tapas to its first 3–6 real health coaches (HCs) — specific channels, specific scripts, specific numbers, specific decision gates. Not a checklist of phases to figure out later; each phase below is meant to be actioned as written or explicitly amended.
>
> **Written**: 2026-07-30, revised same day after feedback that v1 was headings without substance. Companion to `docs/business/tapas-product-overview.md` and `docs/business/tapas-security-review.md`.
>
> **On sourcing**: every external market claim below (competitor pricing, professional associations, channel data) is from a live web search done while writing this revision, with sources listed at the end of each section. Where I couldn't verify a number, I say so explicitly rather than inventing one — see the Kore App pricing caveat in §3.

---

## 1. Decisions locked in

| Decision | Choice |
|---|---|
| Pilot economics | Hybrid — free pilot period, explicit upfront path to paid |
| Pilot source | Mix of warm network + cold outreach, warm first |
| Sequencing vs. security blockers | 3 hard blockers close before any outreach begins |
| Cohort size (wave 1) | 3–6 HCs, outreach targeted to start in ~4–6 weeks |

---

## 2. Phase 0 — Technical/compliance readiness gate

Nothing in Phase 1 onward starts until this closes. From `tapas-security-review.md` §4:

1. Rate limiting on `/api/auth/*` (`backend/src/main.py`)
2. Fix dead `_not_empty_in_prod` validator (`backend/src/config.py:43-46`)
3. Real client-deletion endpoint triggering existing cascade FKs (`backend/src/api/clients.py`)
4. A documented, repeatable consent-capture step — see §8 for the actual clauses it needs to contain, not just "have one"
5. A minimal DSAR export path — needs an owner, doesn't need to be self-service for wave 1

**Concrete Phase 0 exit criterion**: all 5 items closed AND you can personally walk through, live, in front of a prospective HC if asked: "show me what happens if I ask to delete a client." If you can't demo that in under 2 minutes, Phase 0 isn't done regardless of what the code says.

---

## 3. Market pricing benchmark — what to actually charge

I priced this from live 2026 data, not assumption. All monthly, solo-practitioner tier unless noted:

| Platform | Entry tier | Solo-practitioner tier | Notes |
|---|---|---|---|
| Practice Better | Free (3 clients) | $35/mo (10 clients), $69/mo (300 clients) | 20% off annual; +$0.60/hr telehealth AI after 600 free min, 5¢/SMS |
| Healthie | $19.99/mo (10 clients) | ~$79/mo ("Practice Plus") | +2.9% transaction fee on in-platform payments |
| TrueCoach | $29.98/mo (5 clients) | $69.98/mo (20 clients) | +5% flat transaction fee on client billing (Jan 2026) |
| CoachAccountable | $20/mo floor | scales with active-client count, up to $4,000/mo at scale | active-client pricing model, not flat tiers |
| Kore App (India) | — | ₹1,499/mo found on their **gym-management** pricing page | **Caveat: I could not independently confirm this is the same price for their dietitian/nutritionist product line** — Kore App runs both verticals under one brand and I only found pricing attributed to the gym vertical. Treat as directional, not confirmed, until someone checks `koreapp.fit/dietitian-nutritionist-software` pricing directly. |

**India-specific anchor that matters more than any competitor's price**: a solo Indian dietitian/nutritionist charges roughly **₹500–₹2,000 per session** (Delhi/Hyderabad market data). For an HC running ~20 clients, even one session/month each is ₹10,000–₹40,000/month in revenue.

**Recommendation**: price the founding-partner rate at **₹999/month**, locked for as long as they stay continuously subscribed, with a stated future standard rate of **₹2,499/month** for anyone who joins after wave 1. Rationale:
- ₹999 is under 3% of even the low end of a 20-client practice's monthly revenue — trivially easy ROI math to say out loud in a pitch ("less than the cost of two client sessions, for the whole month, for everyone")
- It undercuts every US competitor's converted price point by a wide margin, which matters less for competing with them directly (different market) and more for making the ask feel low-risk to a first-time SaaS buyer
- The ₹999 → ₹2,499 gap (locked-for-life vs. standard) is real, tangible founding-partner value — not just a label
- This is a recommendation, not a unilateral decision — you know your own unit economics (LLM cost per HC, infra cost) better than a market comparison does; sanity-check ₹999/HC/month against your actual per-HC LLM+infra cost before locking it in writing to anyone.

**Sources**: [Practice Better Pricing (Pabau)](https://pabau.com/blog/practice-better-pricing/), [Practice Better Pricing (FindEMR)](https://www.findemr.com/resources/practice-better-pricing-guide/), [Healthie Pricing (SelectHub)](https://www.selecthub.com/p/medical-practice-management-software/healthie/), [Healthie Pricing (ITQlick)](https://www.itqlick.com/healthie/pricing), [TrueCoach Pricing (G2)](https://www.g2.com/products/xplor-truecoach/pricing), [CoachAccountable Pricing (coachway.io)](https://coachway.io/articles/online-fitness-coaching-guide/), [Kore App gym pricing](https://koreapp.fit/pricing), [Dietitian fees India (ConsumerAffairs)](https://www.consumeraffairs.com/health/how-much-does-a-dietitian-cost.html), [Dietitian fees Delhi/Hyderabad (Lybrate)](https://www.lybrate.com/delhi/dietitian-nutritionist)

---

## 4. Channel-by-channel outreach plan (replaces "target selection criteria")

### Warm (2–3 of the cohort)
Your own network, direct ask. No script needed beyond §6's warm template — the relationship carries it.

### Cold (1–3 of the cohort), ranked by yield vs. stealth risk

| Rank | Channel | What it actually is | Why this rank |
|---|---|---|---|
| 1 | **IDA Mumbai Chapter** (or your local IDA chapter) | Indian Dietetic Association — 13,000 members nationally, 23 chapters, Mumbai chapter alone has 2,000 life members + 800 student members. Chapters run local scientific meetings/webinars. | Highest-trust cold channel available — professional body membership is itself a credibility filter. Attend a local chapter meeting in person or ask a warm contact who's a member for an intro, rather than cold-emailing the association. `idamumbaichapter.com` lists membership/events. |
| 2 | **Bharat Dietetic Association (BDA)** member directory | A second national professional body (`bdaorg.com`). | Same logic as IDA, second pool if IDA chapter is slow or your city's chapter is thin. |
| 3 | **Instagram DMs to small/mid-tier dietitian-creators** | Solo HCs with 5K–50K followers who post their own content (not agency-run) and — this is the filter that matters — **list a WhatsApp number in their bio or linktree for booking.** That bio line is a public, self-reported signal of exactly the WhatsApp-dependency pain Tapas solves. | High signal-to-noise once filtered correctly; avoid the >100K-follower tier (e.g. Rujuta Diwekar-scale accounts) — they typically run a team, not a solo practice, and don't match the buyer persona. |
| 4 (avoid as primary, use only passively) | Facebook group "Nutritionists in India" | Public group, real members. | **Do not post here.** It's public and searchable — exactly the visibility you're trying to avoid per the "stay dark" guardrail (§9). Use it only to identify individual members to DM privately, never to broadcast. |

**Concrete first move**: build a longlist of 10–15 candidates across warm contacts + IDA/BDA intros + Instagram bio-scan, score them with the rubric in §5, take the top 3–6.

**Sources**: [IDA About](https://idaindia.com/about-us/), [IDA Mumbai Chapter](https://idamumbaichapter.com/), [IDA Mumbai membership](http://idamumbaichapter.com/membership/), [Bharat Dietetic Association](https://bdaorg.com/members/become-a-member/), [Nutritionists in India FB group](https://www.facebook.com/groups/nutritionists.in.india/), [Indian dietitian Instagram creators](https://confluencr.com/top-10-indian-nutrition-influencers-on-instagram/)

---

## 5. Candidate scoring rubric

Score every candidate on your longlist before deciding who's in wave 1. Don't just pick whoever responds first.

| Criterion | 0 pts | 1 pt | 2 pts | 3 pts |
|---|---|---|---|---|
| Client count | <10 or >40 | 10–15 or 30–40 | — | 15–30 (matches product's ~20-client north star) |
| WhatsApp-dependency signal | No visible signal | Mentions WhatsApp informally | — | Bio/linktree explicitly routes booking through WhatsApp |
| Practice structure | Clinic-affiliated / team-based | — | — | Solo practice (hard gate — score 0 here excludes the candidate regardless of other points) |
| Relationship warmth | Cold, no prior contact | Weak tie (mutual connection) | Warm (you've spoken before) | Strong (existing relationship/friend) |
| Digital comfort | No visible SaaS/app usage | Uses Instagram/basic tools only | Uses ≥1 practice-management or scheduling tool already | — |
| Responded positively to a soft first touch | N/A — not yet contacted | Responded neutrally/slowly | Responded positive, no date set | Responded positive, agreed to a call |

**Rule**: practice structure = 0 is an automatic exclude, regardless of total score. Otherwise rank by total (max 14) and take your top 3–6, keeping at least 2 warm and at least 1 cold in the final cohort so you get feedback diversity, not just enthusiasm from people who already like you.

---

## 6. Message templates

### Warm outreach (DM/WhatsApp/email — adapt tone to the relationship)
> "Hey [name] — I've been building something for the last while: a platform that takes the admin grind out of running a coaching practice — session notes, action items, check-ins, diet chart versions, calendar booking, all in one place instead of scattered across WhatsApp and notes apps. It's built specifically for solo HCs running their own client roster, not a clinic tool. I'm inviting a small group of coaches — 3 to 6 — to try it free for the next 6-8 weeks as founding partners, which means: free access now, a locked-in low rate after (₹999/month vs. ₹2,499 for anyone who joins later), and direct input into what gets built next. I'd rather be upfront: some pieces (in-app client messaging, meal-photo logging, in-app payments) are still being built during this window — you'd be shaping the order we build them in, not getting a finished product. Would you be open to a 20-minute call to see if it's a fit?"

### Cold outreach (Instagram DM / IDA-intro follow-up)
> "Hi [name] — [context line: saw your profile via IDA Mumbai / a mutual contact / your content on X]. I'm building Tapas, a practice-management platform for solo dietitians/coaches in India — takes session notes, action items, check-ins and diet-chart delivery off WhatsApp and into one place, with AI drafting the admin work (which you always review before anything reaches a client). I'm looking for 3–6 founding-partner coaches to pilot it free for 6–8 weeks — happy to be direct that it's early: some features are still being built during that window, and you'd have real input into what comes next, plus a locked-in low rate after. If that sounds interesting, I'd love 15 minutes to show you what's actually built today (not a pitch deck — the real product) and see if it's a fit for how you run things."

### Re-engagement cadence (for any HC who's gone quiet mid-pilot)
- **Day 3 of silence**: short, no-pressure — "No rush at all, just checking you got set up okay — anything blocking you from the first session/client invite?"
- **Day 10**: specific and useful — "Noticed you haven't [logged a session / sent action items] yet — want to jump on a 10-min call and I'll walk you through it live?"
- **Day 21**: honest close-out offer — "Totally understand if the timing's not right — want to pause your pilot slot and free it up for someone else, or are you still keen to give it a real try?" This isn't passive-aggressive — it's a genuine decision point, and it protects your 3–6 wave-1 slots from being occupied by someone who's silently disengaged.

---

## 7. Structured feedback instrument & KPIs

### Feedback cadence
- **Week 2 pulse** (5 min, async, e.g. a 4-question Google Form): Did you complete your first session/MOM cycle? Anything confusing in onboarding? One thing you liked, one thing that annoyed you. Any blocker to inviting your first client?
- **Week 4 structured review** (20-min call): walk through their actual usage with them, screen-share if possible. Ask directly: which of the built features have you used, which haven't you touched and why, has anything broken, would you recommend this to another HC today (0–10)?
- **Week 6 conversion-intent check** (built into the week-6 or equivalent touchpoint): "Based on what you've seen, would you continue at ₹999/month after your free period?" — this is the actual go/no-go data point for Phase 8's paid conversion, asked explicitly, not inferred from vibes.
- **Week 8 close-out**: final NPS-style question + one open question — "What would need to be true for this to fully replace WhatsApp for you?"

### KPIs with numeric thresholds (decision rules, not vanity metrics)

| Metric | Target | If missed |
|---|---|---|
| Activation: HC completes onboarding + logs first real session within 7 days of pilot start | ≥80% of cohort (e.g. 3/4 or 5/6) | Pause adding new HCs; diagnose onboarding friction with the ones who stalled before continuing |
| Weekly engagement: HC logs into Tapas ≥3x/week by week 3 | ≥70% of active cohort | Flag as at-risk; trigger the day-10 re-engagement script early |
| Client-side adoption: invited clients who activate their `/me` portal login within 2 weeks of invite | ≥50% per HC | Investigate the invite flow with that specific HC — likely a messaging/framing issue on their end, not necessarily a product bug |
| Week-6 conversion intent: HCs answering "yes" to continuing at ₹999/month | ≥50% of cohort | Do not proceed to Wave 1b cold expansion at the current price/positioning — treat as a pricing or value-prop signal, not a sales-execution problem to push through |
| Week-4 NPS-style score (0–10 "would you recommend to another HC") | Average ≥8 | Don't yet ask this cohort for referrals into Wave 1b — a mediocre score used for referral-sourcing back-fires by putting a lukewarm endorsement in front of a cold prospect |

---

## 8. Pilot agreement / consent — what it actually needs to say

Phase 0 item 4 ("a documented consent step") isn't done just by having a PDF. At minimum, the agreement each pilot HC signs needs to cover:

1. **Purpose limitation**: what data is collected (session notes, which may contain client health disclosures, client PII, uploaded files) and why — practice management and AI-assisted drafting only, coach-reviewed before anything reaches a client
2. **Retention & deletion**: explicit reference to the 30-day erasure commitment already made in `compliance-india.md`, and confirmation the deletion endpoint (Phase 0 item 3) is live
3. **The HC's own obligation**: Tapas is a processor for the HC's client data — the HC remains the one who needs their own clients' consent to put their information into a third-party platform. State this explicitly so it isn't assumed away; this is a real DPDP-relevant gap if left implicit.
4. **Free-period terms**: exact dates, exact price after (₹999/month locked, per §3), and what happens if they choose not to continue (data export offer, deletion on request)
5. **No uptime/SLA guarantee during pilot**: standard, expected pilot-phase language — sets expectations if something breaks (see the incident-response trigger in §9)
6. **Feedback expectation**: that participating means honoring the week-2/4/6/8 checkpoints in §7 — this isn't optional for a founding partner, it's the actual value exchange for free + locked pricing

This doesn't need a lawyer-drafted contract for a 3–6 person pilot — a clear one-to-two-page document covering the 6 points above, sent for e-signature or explicit written agreement, is sufficient at this scale and is the "documented, repeatable" version Phase 0 item 4 calls for.

---

## 9. Scenario planning — with actual scripted responses

| Trigger | What you actually say/do |
|---|---|
| Warm HC loves it, converts to paid, refers others | "That's great to hear — would you be open to me mentioning your name (or you introducing me) to one other coach you think would get value from this?" Only ask this **after** their week-4 NPS is ≥8 (§7) — don't ask a lukewarm user for a referral. |
| HC says missing messaging/meal-logging blocks full WhatsApp replacement | "That's exactly the gap we're closing next — you're one of the reasons it's prioritized where it is. Can I check back with you specifically when [F2/F3] ships so you're one of the first to try it?" Converts the gap into a retention hook, not an apology. |
| HC surfaces a workflow gap outside current specs (e.g. runs cohort/group sessions) | "That's useful — Tapas is built around 1:1 coaching today, group support isn't on the current roadmap yet. I don't want to promise something I can't commit to, but I'll log this as real signal." Do not improvise a "sure, we can probably do that" — log it against product-overview §7 Q2 and move on. |
| Cold prospect asks "how's this different from Kore App?" | "Kore App's strength is the branded client app — we don't have that yet. What we do differently is a hard rule: nothing AI-drafted reaches your client until you've reviewed and edited it yourself — that's built into how the data works, not just a setting. If having your own branded app is the deciding factor for you today, this might not be the right fit yet — happy to stay in touch for when it is." Honest disqualification beats oversell. |
| Prospect asks a trust/security question ("can I delete a client's data?") | "Yes — [demo the actual deletion flow live, per the Phase 0 exit criterion in §2]." If you can't demo it in under 2 minutes, you're not actually done with Phase 0 — don't have this conversation until you can. |
| A pilot HC goes quiet mid-pilot | Follow the day-3/day-10/day-21 cadence in §6, verbatim. Don't invent a new message each time — consistency reads as process, not desperation. |
| A technical incident happens during the pilot | Send within 1 hour of detection, to every active pilot HC, not just the affected one: "We had an issue with [specific, plain-language description] between [time] and [time]. [What's affected / not affected]. [What we're doing about it]. We'll follow up by [specific time] with a full update." Draft this template now; don't compose it for the first time under pressure. |
| A competitor becomes aware of Tapas during outreach | No action needed if you've followed §10's guardrails — this is the expected, low-risk outcome of staying relationship-driven. If it happens anyway, don't change positioning reactively; that signals more concern than warranted. |

---

## 10. Explicit guardrails ("don't do this")

- Don't lead with "we have a complete product."
- Don't publish or market the macro-formula engine before it ships.
- Don't post in public channels (the Facebook group, public Instagram comments, LinkedIn posts) this wave — DMs and warm intros only.
- Don't promise anything from the product-overview §4.2 table-stakes gap list (branded app, push, group programs, recurring billing, self-booking), even if a prospect asks eagerly.
- Don't skip Phase 0 to hit the 4–6 week timeline once it starts to feel close.
- Don't ask a sub-8 NPS pilot HC for a referral (§9) — a lukewarm referral into Wave 1b does more damage than no referral.

---

## 11. Week-by-week timeline

| Week | What happens |
|---|---|
| 1–2 | Phase 0 items 1–3 (security fixes) in engineering |
| 2–3 | Phase 0 items 4–5 (consent doc per §8, minimal DSAR); build the 10–15 candidate longlist via §4 channels; score with §5 rubric |
| 3 | Finalize wave 1a shortlist (top 2–3 warm) |
| 4 | Wave 1a outreach begins, staggered starts (e.g. HC #1 day 1, HC #2 day 4, HC #3 day 7) using the §6 warm template |
| 4–5 | Onboarding + week-2 pulse checkpoint per HC (own clock, not a shared calendar date) |
| 6 | Week-4 structured review per HC; assess wave 1a proof points |
| 6 (gate) | Go/no-go: at least one HC with NPS ≥8 and a usable proof point → proceed to Wave 1b. Otherwise, diagnose before expanding. |
| 7–8 | Wave 1b cold outreach (IDA/BDA intro, Instagram DMs) using the §6 cold template, gated behind the week-6 proof point |
| Per-HC week 6 | Conversion-intent check (§7) |
| Per-HC week 8 | Free period ends; paid conversion conversation using the ₹999/month locked rate stated at signup (§8) |

---

## 12. Definition of done for this wave

- Phase 0's 5 items closed, and the deletion-flow demo (§2) actually works live
- Pricing decision made (recommendation: ₹999/month founding rate, sanity-checked against real per-HC infra/LLM cost)
- 10–15 candidate longlist scored via §5, top 3–6 selected with at least 2 warm / 1 cold represented
- Wave 1a outreach sent using §6 templates, staggered per §11
- Week-6 gate (§11) explicitly evaluated before Wave 1b begins — not skipped because momentum feels good
- This document updated when a real scenario diverges from §9's table, so it stays a working reference, not a one-time exercise
