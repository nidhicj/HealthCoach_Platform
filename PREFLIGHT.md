# PREFLIGHT.md — The checklist Claude runs before non-trivial responses

This file exists so the preflight block in CLAUDE.md §3 has worked examples. When Claude is unsure what a good preflight looks like for a given request, Claude re-reads this file.

---

## Why preflight exists

The 9 non-negotiables in CLAUDE.md are abstract. Preflight is the **concrete action** that makes them observable. Without preflight:
- Rule 4 (use best skills/MCPs) is invisible — SoJo can't tell if Claude actually checked.
- Rule 5 (ask first) is easy to skip — Claude might just guess and answer.
- Rule 6 (no assumptions) is unenforceable — assumptions are invisible unless surfaced.
- Rule 7 (context missing) depends on Claude noticing what's missing, which is what preflight does.
- Rule 9 (discuss before coding) is the final line of preflight — the "what I'm about to do" section.

The preflight block is the receipt that proves the anthem was followed.

---

## When preflight is required

**Always** for:
- Any request that would produce code longer than ~10 lines
- Any request that touches auth, data model, LLM prompts, compliance, deployment, or secrets
- Any request where Claude is unsure what's being asked
- Any request that would create or modify files
- The first substantive response in a new session

**Compressed** (3-line version) for:
- Quick follow-ups within an ongoing task where full preflight ran in the last ~5 turns
- SoJo explicitly says "just do it" or "quick one" — but the anthem-check line still appears

**Skipped** for:
- Greetings, acknowledgments, yes/no confirmations
- Pure clarifying questions from Claude (no action proposed)

---

## The full preflight block

```
## Preflight

**Anthem check**: rules [N, M, ...] are the ones most at risk for this task.
Brief: [1 sentence on how this task tempts violation and how I'm guarding against it.]

**Skills / docs I'll consult**:
- `.claude/skills/<name>.md` — [why]
- `/docs/specs/<file>.md` — [why]
- `/docs/decisions/<adr>.md` — [why]
- `/docs/domain/glossary.md` — [if domain terms involved]

**MCPs / plugins I'll use**:
- <mcp-name> — [why]
- (or) "None needed for this task."
- (or) "Would have used <X> if configured — flagging as a gap."

**External docs I'll cite** (only official sources per rule 2):
- <library/standard> — [URL] — [specific question I'm verifying]
- (or) "None needed — answer is within this repo's own context."

**What I'm about to do**:
- [bullet 1]
- [bullet 2]
- [bullet 3]
(Or for non-action responses: "Answer only — no files touched.")

**Definition of done for this response**:
- [what has to be true for this response to count as complete]

**Context missing** (if any — else omit this section):
- [unknown 1] — [why it matters] — [how to answer]
- [unknown 2] — ...
```

---

## Examples

### Example 1 — Full preflight (stack question)

**SoJo asks**: "How should I structure the coach onboarding flow?"

```
## Preflight

**Anthem check**: rules 1 (not lazy), 6 (no assumptions), 8 (industrial standards), 9 (discuss before coding) are most at risk. This is an important architectural question and the temptation is to jump to a specific implementation before clarifying onboarding goals.

**Skills / docs I'll consult**:
- `/docs/domain/glossary.md` — confirm what "onboarding" means in this product (coach profile? KYC? Stripe? sample session?)
- `/docs/domain/actors.md` — onboarding flow differs for coach vs future client
- `/docs/decisions/0001-stack-selection.md` — cannot write framework-specific code until Accepted

**MCPs / plugins I'll use**:
- None needed — this is a design discussion, not a lookup.

**External docs I'll cite**:
- DPDP Act 2023 — consent section — I'll reference consent capture obligations
- Official DPDP text or MeitY guidance if I quote specifics

**What I'm about to do**:
- Lay out the onboarding flow as a sequence of steps (not code)
- Identify which steps involve personal data and trigger consent capture
- Identify which steps depend on stack decisions (so we know what's blocked)
- Propose a spec to write up in `/docs/specs/0001-onboarding.md`

**Definition of done for this response**:
- SoJo has a 6–10 step onboarding sequence to react to
- Clear list of what needs ADR-0001 resolved first
- Clear list of consent/compliance touchpoints

**Context missing**:
- Do coaches pay for the platform (subscription) or is it free during beta? — affects whether billing integration is part of onboarding.
- Are coaches verified in any way (credentials check, LinkedIn, references)? — affects trust/safety design.
- Does the platform need KYC for Indian compliance (RBI if we ever touch payments via the app)? — affects whether Aadhaar/PAN appears anywhere.
```

### Example 2 — Compressed preflight (quick fix)

**SoJo asks**: "Fix the typo in the glossary — it should be 'recap' not 'receap'."

```
## Preflight
Anthem rules 10 (scope), 13 (verify). Just fixing the typo; reading the file first to confirm exact line, no other edits.
```

### Example 3 — Preflight that stops the task

**SoJo asks**: "Write the auth middleware."

```
## Preflight

**Anthem check**: rules 6 (no assumptions), 8 (industrial standards), 9 (discuss before coding). This request is blocked.

**Skills / docs I'll consult**:
- `/docs/decisions/0001-stack-selection.md` — stack is not decided, so I don't know which framework's middleware pattern to use.

**What I'm about to do**:
- Nothing yet. I'm stopping here because writing auth middleware requires stack + auth provider decisions. See "context missing."

**Context missing**:
- Stack not chosen — ADR-0001 is not Accepted. Auth middleware in Next.js (middleware.ts) is fundamentally different from FastAPI (Depends) or NestJS (Guards).
- Auth provider not chosen. Options include Clerk, WorkOS, Supabase Auth, self-hosted (e.g., Lucia / Auth.js). Each has different middleware patterns.
- Multi-actor handling — how do we distinguish coach vs (future) client in tokens? JWT claims? Separate tables with a polymorphic `actor` field?

Recommended next step: resolve ADR-0001 and draft ADR-0002 (auth-strategy) before any middleware code exists.
```

---

## What a bad preflight looks like (avoid)

```
## Preflight
I'll answer your question now.
```

This is empty. It fails rules 4, 6, 7, 9 simultaneously. If Claude finds itself writing a preflight that short, either (a) the task really is trivial and preflight should be skipped entirely, or (b) Claude is being lazy and should do the real checklist.

---

## SoJo's prerogatives

- SoJo can say "skip preflight for this turn" — Claude complies but still runs rules 2, 3, 11, 12 (no hallucination, retract on error, destructive gating, secrets) which are never suspended.
- SoJo can say "tighten your preflights" — Claude compresses to the 3-line version going forward.
- SoJo can say "your preflights are missing X" — Claude adds X to every subsequent preflight.
