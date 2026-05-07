# PHASE-NN: [Title]

> Use for PHASE-NN files inside a `Unit_NNN_PascalCaseName/` directory.
> PHASE files are phase-scoped implementation records: written before each phase begins (as the build plan for that phase) and updated as the phase ships.
> For durable feature specs that may span multiple build phases, use `template-spec.md` (SPEC-NNNN files) instead.
> Naming: `PHASE-NN-kebab-case-title.md` — two-digit number, numbering resets per unit.

**Unit**: Unit_NNN_PascalCaseName
**Status**: Draft | In Progress | Complete | Complete | Verified
**Verification date**: YYYY-MM-DD — link to `docs/VERIFICATION.md` section (fill in after verification)
**Implements**: [SPEC-NNNN section refs — e.g., "SPEC-0001 §3 Acceptance criteria #1–4"; or "Pre-condition only — no SPEC sections directly implemented"]
**ADRs implemented**: [list with links — e.g., "ADR-0001 (stack), ADR-0005 (auth)"; or "None — infrastructure phase"]

---

## 0. Per-requisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific I haven't provided. Ready?

## 1. Scope

What this phase accomplishes, in 2–4 sentences. Drawn from `docs/build-plan.md` and the corresponding SESSION_LOG entry. State what is NOT in scope (in one sentence if obvious, or link to SPEC non-goals section).

## 2. Deliverables shipped

Concrete list of what was built. File-by-file or module-by-module where helpful. Drawn from SESSION_LOG entries. When listing API endpoints, include method + path. When listing models, include key fields.

Be specific enough that a future developer can tell at a glance whether a given file or endpoint is part of this phase or a later one.

- File / module / endpoint — what it does

## 3. Decisions made during this phase

Each decision that emerged DURING the phase — not pre-decided in an ADR, but resolved while building. Drawn from "Decided" sections of SESSION_LOG. If a decision later became or amended an ADR, link it.

Format: **Decision label** — explanation and rationale.

If no phase-level decisions were made (all decisions were pre-decided in ADRs), write: "All decisions pre-decided in ADRs listed in the header."

## 4. Bugs fixed mid-phase

Drawn from "Bugs fixed mid-session" sections of SESSION_LOG. Useful for future debugging — the same class of bug recurs.

Format: **Short label** — what the bug was, what caused it, how it was fixed.

If no bugs, write: "None recorded."

## 5. Source docs consulted

What this phase referenced. Drawn from the corresponding starter prompt's "Mandatory preparation" section if available, otherwise from the SESSION_LOG.

- `docs/decisions/ADR-NNNN.md` — why it was consulted
- `docs/specs/Unit_NNN_PascalCaseName/SPEC-NNNN-...md` — which sections
- `docs/diagrams/NNNN-....md` — what was read

## 6. Verification

- **Verification date**: YYYY-MM-DD
- **Verification record**: `docs/VERIFICATION.md` § [section title]
- **Test count at end of phase**: NNN passing (delta from prior phase: +NN)
- **Key checks**: (summary of manual verification steps that passed; reference VERIFICATION.md for full detail)

## 7. Lessons learned

What went well. What surprised. What we'd do differently. Be honest — this section is what the next similar phase reads first.

- **What worked**: explain why
- **What surprised**: explain the surprise
- **What to do differently**: actionable, not vague

## 8. Carry-over to subsequent phases

What this phase set up that later phases depend on. Patterns established. Conventions locked in. Be specific: name the files, functions, or conventions that downstream phases inherit.

- `path/to/file.py` — why it matters downstream
- Convention: what was established and where it applies
