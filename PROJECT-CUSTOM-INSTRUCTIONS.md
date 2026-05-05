# Project Custom Instructions — Health Coach Platform

> This file mirrors the Claude Project's custom instructions. When updated here, copy the content into the Claude Project's "Custom instructions" field (claude.ai → project → edit instructions). The repo copy is the source of truth; the uploaded copy is the active instructions.

---

## Who you are working with

SoJo — solo founder, dedicated full-time to building this platform. Strong product and systems thinking. Wants thorough, honest answers — not hedged or padded ones. Prefers decisions to be recorded in ADRs or PHASE files so they survive across sessions.

---

## The product

A SaaS platform for independent health coaches in India. Coaches onboard clients, run AI-assisted sessions (MOM drafts, pre-session briefs, action item tracking), and conduct between-session check-ins. AI assists — it never speaks directly to clients. This is a production repo; a separate `product-prototype/` repo exists for validation work.

---

## How to work in this repo

- **Read `CLAUDE.md` (root) first, every session.** It is the operating contract. The 12 non-negotiables and the PREFLIGHT block are mandatory.
- **Run a PREFLIGHT block before every non-trivial response.** See `PREFLIGHT.md` for format and examples.
- **Specs live under `docs/specs/Unit_NNN_PascalCaseName/`.** Each unit contains:
  - `SPEC-NNNN-kebab-case-title.md` — durable, feature-scoped specs. May span multiple build phases. Describe what the product does for users.
  - `PHASE-NN-kebab-case-title.md` — phase-scoped implementation records. One per build sprint. Record what was built, what was decided, what bugs were fixed.
  - When referencing a spec, use the full path: `Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md §3`
- **Cross-cutting docs stay flat.** ADRs (`docs/decisions/`), diagrams (`docs/diagrams/`), domain docs (`docs/domain/`) do NOT get per-unit subfolders.
- **Spec before code.** Anthem rule 9. Write the SPEC, get SoJo's confirmation, then write the PHASE plan, then write code. Never the reverse.
- **No assumptions about library versions, file contents, or prior decisions.** Read the file. Check the version. Ask SoJo. Consult `docs/domain/glossary.md` for terminology.

---

## Compliance context

India-first. DPDP Act 2023 is primary. Health data is sensitive in practice. Real deletion (not soft-delete) is required. India-region hosting for personal data. Claude does not give legal advice — it flags compliance touchpoints and lets SoJo make the call.

---

## What's in Project knowledge

These files are uploaded here for context across sessions. The canonical versions are in the repo — if a file here conflicts with the repo version, the repo wins.

| File | Purpose |
|---|---|
| `CLAUDE.md` | Operating contract and non-negotiables |
| `PREFLIGHT.md` | Preflight block format and examples |
| `CONTRIBUTING.md` | Commit conventions, branching |
| `docs/REPO-INDEX.md` | What lives where in the repo |
| `docs/build-plan.md` | Phase-by-phase milestones and acceptance criteria |
| `docs/SESSION_LOG.md` | Running log of what each session shipped |
| `docs/VERIFICATION.md` | Manual verification checklists per phase |
| `docs/domain/glossary.md` | Canonical domain terminology |
| `docs/domain/actors.md` | HC, Client, Admin role definitions |
| `docs/domain/compliance-india.md` | DPDP and DISHA posture |
| `docs/diagrams/0002-data-model.md` | ERD for all 16 tables |
| `docs/decisions/0001-stack-selection.md` | Stack ADR |
| `docs/decisions/0002-runtime-topology.md` | Runtime topology ADR |
| `docs/decisions/0003-llm-strategy.md` | LLM strategy ADR |
| `docs/decisions/0004-repo-structure.md` | Repo structure ADR |
| `docs/decisions/0005-auth-strategy.md` | Auth strategy ADR |
| `docs/decisions/0006-observability.md` | Observability ADR |
| `docs/specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` | HC core cycle feature spec |
| `docs/specs/Unit_001_HcCoreCycle/SPEC-0002-llm-service.md` | LLM service feature spec |
| `docs/specs/template-phase-plan.md` | Template for PHASE-NN files |
| `docs/specs/0000-template_SPEC.md` | Template for SPEC-NNNN files |
| `.claude/skills/skill-write-spec.md` | How to write a SPEC-NNNN file |
| `.claude/skills/skill-write-phase-plan.md` | How to write a PHASE-NN file |
