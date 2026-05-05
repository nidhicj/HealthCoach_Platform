# Skill: Write a Feature Spec

## Spec vs Phase Plan — which to write?

Before starting: determine whether you need a SPEC (SPEC-NNNN) or a PHASE plan (PHASE-NN). They are different documents for different purposes.

| Question | SPEC-NNNN | PHASE-NN |
|---|---|---|
| What does this feature do for users? | ✅ Write a SPEC | ❌ |
| What did we build in this sprint? | ❌ | ✅ Write a PHASE plan |
| May it span multiple build phases? | ✅ | ❌ (one phase only) |
| Describes actor flows, acceptance criteria? | ✅ | ❌ |
| Records bugs fixed, lessons learned? | ❌ | ✅ |
| Links to VERIFICATION.md sections? | ❌ | ✅ |

**If you are about to write implementation code**, write the SPEC first (this skill), then write the PHASE plan (`skill-write-phase-plan.md`) for the build sprint.

**If the spec already exists and you are starting a build sprint**, go directly to `skill-write-phase-plan.md`.

## When to use this skill

Use when:
- A new feature or capability needs to be specified before any code is written (anthem rule 9: discuss before coding)
- An existing spec needs updating to reflect post-implementation decisions
- Cross-referencing between a PHASE file and the SPEC it implements

## Where SPEC files live

Always inside a Unit directory:

```
docs/specs/Unit_NNN_PascalCaseName/SPEC-NNNN-kebab-case-title.md
```

- `SPEC-` uppercase, four-digit zero-padded number (`0001`, `0002`, ...)
- Numbering resets per unit (each unit's first SPEC is `SPEC-0001`)
- Example: `docs/specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md`

When referencing a spec in other documents, always use the full path from repo root:
`Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md §3`

## The spec structure (from `docs/specs/0000-template_SPEC.md`)

Every SPEC file uses the template exactly. Key sections:

1. **Header** — Status, Date, Owner, Relates-to, and "Implemented by phases" (updated as phases complete)
2. **Goal** — one paragraph, product-level language
3. **Non-goals** — explicit out-of-scope list; bulletproofs against scope creep
4. **Actors and roles** — cross-reference `domain/actors.md`
5. **Domain terms** — cross-reference `domain/glossary.md`; add new terms to glossary too
6. **User stories** — concrete usage from each actor's perspective
7. **Flow** — step-by-step walkthrough; Mermaid sequence diagram for non-trivial flows
8. **Data** — which entities are read/written; cross-reference `diagrams/0002-data-model.md`
9. **API surface** — endpoints introduced or modified
10. **LLM involvement** — if applicable; task type, prompt, schema, snippet tags
11. **Coach-reviewed gate** — if AI content reaches clients; document the review/edit/send transition
12. **Edge cases and failure modes** — table of unusual paths
13. **Acceptance criteria** — verifiable checkboxes; same shape as `build-plan.md` criteria
14. **Open questions** — decisions needed before implementation; each has an owner and a "by when"
15. **Out of scope** — future enhancements
16. **Changelog** — date, change, reason

## Done criteria

A SPEC is ready for implementation (and SoJo's confirmation) when:

- [ ] All 16 sections present, none empty or placeholder
- [ ] Non-goals explicitly list anything a reader might assume is in scope
- [ ] Acceptance criteria are verifiable (can be ticked yes/no without ambiguity)
- [ ] Open questions section is either empty or every question has an owner and a deadline
- [ ] "Implemented by phases" field lists which PHASE-NN files will build it (add as phases are planned)
- [ ] No implementation details in the Goal section — product-level language only
- [ ] Domain terms cross-referenced to `domain/glossary.md`

## Common mistakes

- **Writing too much implementation detail** — a SPEC describes what the feature does for users, not how it's coded. Implementation decisions go in ADRs (cross-cutting) or PHASE plans (per-sprint).
- **Skipping non-goals** — every spec that lacks a non-goals section accumulates invisible scope creep. Be ruthless here.
- **Acceptance criteria that say "it works"** — each criterion must be a verifiable action: what command you run, what you observe. "It works" is not a criterion.
- **Not updating "Implemented by phases"** — this field is the link between durable spec and concrete build history. Update it as each PHASE file is created.
