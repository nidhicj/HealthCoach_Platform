# Skill: Write a Phase Plan

## When to use this skill

Use at the **start of every phase**, before writing any implementation code. Also use **retroactively** if a phase shipped without a written plan — the PHASE file is still required; it just becomes a retrospective record rather than a prospective plan.

A PHASE file documents a single build phase within a Unit. Phases are time-bound slices of implementation. They are not feature specs.

## When NOT to use this skill

- **Cross-cutting concerns** — decisions that shape the whole product (stack, auth, observability) belong in ADRs (`docs/decisions/`), not PHASE files.
- **Durable feature descriptions** — if the thing you're documenting spans multiple phases or is "what the product does" rather than "what this build sprint did," use `template-spec.md` (SPEC-NNNN files) instead.
- **Out-of-scope context** — PHASE files do not contain future plans or design speculation. Scope is exactly what this phase built, decided, and verified.

## SPEC vs PHASE — which to write?

| Question | SPEC-NNNN | PHASE-NN |
|---|---|---|
| What does this feature do (for users)? | ✅ | ❌ |
| What did we build in this sprint? | ❌ | ✅ |
| May it span multiple build phases? | ✅ | ❌ (one phase only) |
| Does it describe actor flows and acceptance criteria? | ✅ | ❌ |
| Does it record bugs fixed, lessons learned? | ❌ | ✅ |
| Does it link to a VERIFICATION.md section? | ❌ | ✅ |

When in doubt: if you're writing before any code exists, start with a SPEC. Once you have a spec and are about to build, write a PHASE plan for this build sprint.

See `skill-write-spec.md` for the SPEC-NNNN workflow.

## The 8-section structure

Every PHASE file uses `docs/specs/template-phase-plan.md` exactly. The sections are:

1. **Scope** — 2–4 sentences on what the phase accomplished. Not bullet points.
2. **Deliverables shipped** — concrete file-by-file list. Include endpoints, model fields, migrations.
3. **Decisions made during this phase** — things resolved while building, not pre-decided in ADRs.
4. **Bugs fixed mid-phase** — class of bug, cause, fix. Valuable for debugging pattern recognition.
5. **Source docs consulted** — mandatory prep docs from the starter prompt; what was actually read.
6. **Verification** — date, VERIFICATION.md link, test count, key check results.
7. **Lessons learned** — honest, specific, actionable. Not vague retrospectives.
8. **Carry-over to subsequent phases** — what downstream phases inherit from this one.

## Where PHASE files live

Always inside a Unit directory:

```
docs/specs/Unit_NNN_PascalCaseName/PHASE-NN-kebab-case-title.md
```

- `PHASE-` uppercase, two-digit zero-padded number (`00`, `01`, ...)
- Numbering resets per unit (each unit's first phase is `PHASE-00`)
- kebab-case title matching the phase's topic
- Example: `docs/specs/Unit_001_HcCoreCycle/PHASE-03-domain-crud.md`

## Done criteria

A PHASE file is complete when:

- [ ] All 8 sections are present and non-empty
- [ ] Every claim in §2 (Deliverables) can be traced to a SESSION_LOG entry or a git commit in this session
- [ ] Every claim in §3 (Decisions) can be traced to SESSION_LOG "Decided" sections or ADRs
- [ ] §4 (Bugs) and §7 (Lessons) contain specific, concrete entries — not "No issues" unless verified accurate
- [ ] §6 (Verification) links to the correct `docs/VERIFICATION.md` section and includes the test count
- [ ] The header `**Implements**` field correctly references the SPEC sections this phase builds
- [ ] The header `**ADRs implemented**` field lists all ADRs applied in this phase
- [ ] No fabricated content — if something isn't recorded in SESSION_LOG or ADRs, write "Not recorded — see SESSION_LOG" rather than guessing

## Common mistakes

- **Drifting into feature-spec content** — the PHASE file is about THIS BUILD, not about the feature in general. Describe what was shipped, not what the feature does for users (that's SPEC-NNNN territory).
- **Thin lessons learned** — "everything went well" is not a lesson. Name the specific decision, the specific bug, the specific pattern that matters for the next phase.
- **Missing the carry-over section** — this is the section the NEXT phase reads first. Be specific about what it inherits: function names, file paths, conventions, known gotchas.
- **Writing it after the session ends from memory** — PHASE files should be drafted during the session using SESSION_LOG as the primary source. Retroactive PHASE files (like PHASE-00 through PHASE-03) source strictly from SESSION_LOG and ADRs; do not reconstruct from memory alone.
- **Forgetting to update STATUS** — move from "Draft" → "In Progress" → "Complete" → "Verified" as the phase progresses.
