# SPEC-NNNN: [Feature Name]

> Use for SPEC-NNNN files inside a `Unit_NNN_PascalCaseName/` directory.
> SPEC files are **durable, feature-scoped specs** that describe what the product does for users. They may span multiple build phases.
> For phase-scoped implementation records (what was built in a specific sprint), use `template-phase-plan.md` (PHASE-NN files) instead.
> Naming: `SPEC-NNNN-kebab-case-title.md` — four-digit number, numbering resets per unit.

**Status**: Draft | Proposed | Accepted | Implemented | Deprecated
**Date**: YYYY-MM-DD
**Owner**: [name]
**Relates to**: [ADRs, other specs, domain docs]
**Implemented by phases**: [list of PHASE-NN files that build this spec — updated as phases complete; e.g., "PHASE-03-domain-crud.md, PHASE-04-llm-service.md"]

---

## Goal

[What is this feature trying to achieve? One paragraph. Use product-level language, not implementation language.]

---

## Non-goals

[What is explicitly out of scope. Bulletproofs the spec against scope creep.]

- [Non-goal 1]
- [Non-goal 2]

---

## Actors and roles

[Who interacts with this feature, with what permissions. Cross-reference `domain/actors.md`.]

| Actor | Role | What they can do |
|---|---|---|
| [Actor] | [Role] | [Capabilities] |

---

## Domain terms

[Any terms specific to this feature. Cross-reference `domain/glossary.md`. If a new term is introduced here, also add it to the glossary.]

| Term | Definition |
|---|---|
| [Term] | [Definition] |

---

## User stories

[Concrete usage from each actor's perspective.]

- As an HC, I want to ___ so that ___.
- As a client, I want to ___ so that ___.

---

## Flow

[Step-by-step walkthrough of the feature in normal use. Include actor → system → response. Add a Mermaid sequence diagram for non-trivial flows.]

1. [Step]
2. [Step]
3. [Step]

---

## Data

[Which entities are read/written. Cross-reference `diagrams/0002-data-model.md`. If new fields are introduced, document them and propose the migration.]

| Entity | Read | Write | New fields? |
|---|---|---|---|
| [Entity] | [Y/N] | [Y/N] | [List or N/A] |

---

## API surface

[Endpoints introduced or modified. Method, path, auth requirements, request/response shape.]

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | /api/... | HC | ... |
| POST | /api/... | HC | ... |

---

## LLM involvement (if any)

[If this feature uses the LLM service: which task type, which prompt, which Pydantic schema. Cross-reference `decisions/0003-llm-strategy.md`.]

- Task type: ...
- Prompt file: `prompts/...`
- Schema: `prompts/schemas/...`
- Snippet relevance tags: ...

---

## Coach-reviewed gate (if applicable)

[Does any AI-generated content reach the client? If yes, document the review/edit/send transition.]

---

## Edge cases and failure modes

| Case | Behavior |
|---|---|
| [Case 1] | [What happens] |
| [Case 2] | [What happens] |

---

## Acceptance criteria

[Verifiable checks. Same shape as `build-plan.md` acceptance criteria. Each is a checkbox the implementer ticks.]

- [ ] [Criterion 1]
- [ ] [Criterion 2]

---

## Open questions

[Things that need a decision before this can be implemented. Each must have an "owner: who decides" and a "by when".]

- [Question] — owner: [name] — by: [date]

---

## Out of scope (for this spec, may be future)

- [Future enhancement 1]
- [Future enhancement 2]

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| YYYY-MM-DD | Initial draft. | [Why now] |
