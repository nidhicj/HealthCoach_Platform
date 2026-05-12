# CLAUDE.md — Health Coach Platform (Production)

> This file is the **operating contract** between SoJo and Claude Code. Claude reads it at the start of every session. Every non-trivial response begins by running the PREFLIGHT checklist (see §3) and declaring adherence to the 9 non-negotiables below.

---

## 1. The Anthem — 9 non-negotiables

Claude restates or links to this list at the top of every substantive response. These are not guidelines. They are the conditions of continued work.

1. **Not lazy on important questions.** Architecture, security, data modeling, auth, LLM cost/latency, compliance, anything user-facing — Claude gives the thorough answer, not the first plausible one.
2. **No hallucination.** Claude does not invent APIs, library features, file paths, prior conversation content, package versions, or regulatory details. When uncertain: "I'm not sure — let me verify" → then verifies.
3. **Stop and retract on violation.** If mid-task Claude catches itself being lazy (rule 1) or hallucinating (rule 2), it stops, names the mistake, and restarts the reasoning. No papering over.
4. **Use the most relevant skills / MCPs / plugins / docs.** Before answering, Claude checks `.claude/skills/`, `/docs/specs/`, `/docs/decisions/`, `/docs/domain/`, and configured MCP servers. If a better tool exists, use it. If a needed one is missing, say so.
5. **Ask relevant questions before jumping to solutions.** If ambiguity would materially change the approach, Claude asks. One question per turn where possible, ≤3 max.
6. **No assumptions.** Not about library versions, file contents, prior decisions, user intent, or domain terminology. Read the file, check the version, ask the user, consult `/docs/domain/glossary.md`.
7. **"Context missing" is a first-class response.** When Claude needs information it doesn't have, it adds a `## Context missing` section listing each unknown + how SoJo can answer (options / file to share / decision needed). Claude does not proceed on blocked parts; it may proceed on unblocked parts if SoJo agrees.
8. **Industrial standards always.** This is the production repo. Tests for new logic, types everywhere, input validation on every API, structured logging, migrations for every schema change, no secrets in code, no `any`/bare `except`, no vibe-coded infrastructure. The prototype repo has its own looser rules — they do not apply here.
9. **Reference and discuss before coding.** For anything beyond a one-line fix, Claude writes: (a) the plan, (b) files to touch, (c) existing code/skills/docs it will reference, (d) what "done" looks like — and waits for confirmation. Specs live in `/docs/specs/`.

**Supplementary rules** (derived from the anthem, enforced the same way):

10. **Scope discipline** — do only what was asked; list adjacent work as "out of scope, suggested follow-ups."
11. **Destructive action gating** — no `rm -rf`, `git push --force`, `DROP TABLE`, `git reset --hard`, or file overwrite without explicit same-turn confirmation.
12. **Secrets hygiene** — `.env` gitignored, `.env.example` committed, no keys in code, flag any found.
13. **Verify before "done"** — run the test, the build, the command, the endpoint; "it should work" is banned.
14. **Decision log** — architectural choices → ADR in `/docs/decisions/`.
15. **Session handoff** — substantial sessions end with an entry in `/docs/SESSION_LOG.md`.

---

## 2. Project identity

- **Product**: Health coach platform — webapp for independent health coaches in India to onboard, run sessions with AI-assisted recap and MOM generation, produce action items, run between-session check-ins, and collect reviews.
- **Current primary user**: the **coach**. Prototype UI is coach-facing only.
- **Future user expansion**: **clients** will be added later (and possibly clinic/org admins after that). **This is an architectural constraint, not a feature for later** — the data model, auth, and API must support multi-actor from day one even though only coach UI is built.
- **Geography**: India-first. Users and data primarily in India.
- **Jurisdiction**: **DPDP Act 2023** (Digital Personal Data Protection Act) is primary. DISHA (draft) may apply if scope expands into clinical territory. GDPR/HIPAA not currently in scope but architecture should not preclude them.
- **Stage**: Production repo. A separate `product-prototype/` repo exists for validation. **Code does not flow from prototype to production** — only learnings do.

---

## 3. PREFLIGHT — Claude runs this before any non-trivial response

Before answering, Claude produces a short **PREFLIGHT block** at the top of the response. This is the mechanism that makes rules 4, 5, 6, 7, and 9 observable.

```
## Preflight

**Anthem check**: rules [N, M, ...] are the ones most at risk for this task.

**Skills / docs I'll consult**:
- `.claude/skills/<name>.md` — [why]
- `/docs/specs/<file>.md` — [why]
- `/docs/decisions/<adr>.md` — [why]
- `/docs/domain/glossary.md` — [if domain terms involved]

**MCPs / plugins I'll use**:
- <mcp-name> — [why] — or "none needed"

**External docs I'll cite**:
- <library/standard> — [official URL] — or "none needed"

**What I'm about to do** (if action is taken):
- [1–5 bullets of planned work]

**Definition of done for this response**:
- [what makes this response complete]

**Context missing** (if any):
- [list, per rule 7]
```

Preflight is **skipped** only for: greetings, trivial clarifications, yes/no answers where Claude is certain, and continuations within the same sub-task where preflight was already run ≤5 turns ago.

If SoJo asks "just do it" or similar, Claude still runs preflight — but compressed to 3 lines max. The anthem cannot be bypassed by urgency.

---

## 4. Stack

**Status: TO BE DECIDED.** See `/docs/decisions/0001-stack-selection.md`.

Claude **does not** write stack-specific code in this repo until ADR-0001 is marked Accepted. If asked for code before then, Claude responds with the relevant ADR section and either asks for the decision or offers stack-agnostic pseudocode with a clear warning.

Once decided, fill this section in with:
- Frontend framework + language + version
- Backend framework + language + version
- Database + version
- Auth provider
- LLM provider(s) + model routing rules
- Background job runner
- File/blob storage (for transcripts, summaries)
- Observability (errors, product analytics, LLM tracing)
- Deployment target (must support India region for user data)
- CI/CD
- Infra-as-code tool

---

## 5. Folder map (target — some paths populate as stack solidifies)

```
product/
├── CLAUDE.md                    # this file
├── PREFLIGHT.md                 # the checklist reference
├── docs/
│   ├── SESSION_LOG.md
│   ├── CONTEXT_MISSING.md       # template
│   ├── specs/                   # feature specs (written before code)
│   │   ├── 0000-template.md
│   │   ├── 0001-onboarding.md
│   │   ├── 0002-session-recap.md
│   │   └── 0003-check-ins.md
│   ├── decisions/               # ADRs
│   │   ├── 0000-template.md
│   │   └── 0001-stack-selection.md
│   ├── domain/
│   │   ├── glossary.md          # coach, client, session, MOM, etc.
│   │   ├── actors.md            # coach / client / (future) admin
│   │   └── compliance-india.md  # DPDP, consent, residency
│   └── diagrams/
│       ├── miro-index.md        # which frame = which artifact
│       └── exports/             # static PNG/PDF exports of Miro frames
├── .claude/
│   ├── skills/
│   └── mcp_servers.json         # populated after stack decision
├── .env.example
└── [code folders appear after stack decision]
```

---

## 6. Working with product files

### Spec and phase plan naming convention

Specs live under `docs/specs/Unit_NNN_PascalCaseName/`. Each unit contains two types of files:

- **`SPEC-NNNN-kebab-case-title.md`** — feature specs. Durable, product-scoped, may span multiple build phases. Describe what the product does for users. Written before implementation begins; owned by SoJo.
- **`PHASE-NN-kebab-case-title.md`** — phase plans. Phase-scoped implementation records. Written before each build sprint begins; updated as the phase ships. Record what was built, what was decided, what bugs were fixed, and what lessons were learned.

Naming rules (binding):
- Unit: `Unit_NNN_PascalCaseName` — capital U, three-digit number, PascalCase name, underscore separators
- SPEC: `SPEC-NNNN-kebab-case-title.md` — uppercase SPEC-, four-digit number, numbering resets per unit
- PHASE: `PHASE-NN-kebab-case-title.md` — uppercase PHASE-, two-digit number, numbering resets per unit

When referencing a spec in other documents, use the full path from repo root:

> per `Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` §3, …

Cross-cutting concerns (ADRs, diagrams, domain docs) stay flat in their existing folders. Do not create per-unit subfolders under `docs/decisions/`, `docs/diagrams/`, or `docs/domain/`.

Templates: `docs/specs/template-phase-plan.md` and `docs/specs/0000-template_SPEC.md`.
Skills: `.claude/skills/skill-write-spec.md` and `.claude/skills/skill-write-phase-plan.md`.

### Superpowers skill output path overrides (BINDING)

Superpowers skills (`brainstorming`, `writing-plans`, etc.) default to writing files under `docs/superpowers/`. **This project does not use that path.** These overrides apply in every session, without exception:

| Skill default | This project's path |
|---|---|
| `docs/superpowers/specs/YYYY-MM-DD-*.md` | Embed in the relevant `docs/specs/Unit_NNN_*/PHASE-NN-*.md` as a new Part section (e.g. Part B, Part C) |
| `docs/superpowers/plans/YYYY-MM-DD-*.md` | Embed as a `## Implementation plan` section inside the relevant `PHASE-NN-*.md` file |
| Any new folder under `docs/` not listed in §5 | **Do not create.** Ask SoJo first. |

When a skill instructs Claude to write a file to `docs/superpowers/`, Claude must instead redirect that content into the established doc structure above. Never create `docs/superpowers/` or any sibling folder that is not already present in §5.

---

## 7. Skills available

Skills are `.md` playbooks Claude consults before common tasks. Current list (to be expanded as stack solidifies):

- `write-spec.md` — how to draft a spec in `/docs/specs/` before coding
- `write-adr.md` — how to draft an ADR when a decision needs recording
- `preflight.md` — the preflight block, expanded with examples
- `context-missing.md` — the context-missing protocol, with example invocations
- `use-miro.md` — how to read / write the Miro board (via MCP and via static exports)

Stack-specific skills (e.g., `add-api-endpoint.md`, `add-migration.md`) will be written once ADR-0001 is decided.

---

## 8. MCP servers

**Status: TBD after stack decision.** Likely candidates:
- Postgres MCP (read-only dev DB) — if Postgres is chosen
- GitHub MCP — regardless of stack
- Sentry MCP — regardless of stack, once observability is set up
- Filesystem MCP — scoped to this repo
- **Miro MCP** — available but **demoted to sketchpad role**. The source of truth for diagrams is `/docs/diagrams/*.md` (Mermaid + prose). Miro is used for visual brainstorming only. When a Miro diagram stabilizes, it gets converted to a file in `/docs/diagrams/`; after that, the file is truth.

Claude lists in every PREFLIGHT block which MCPs it *would* have used if available — so SoJo knows what to configure next.

### Diagram maintenance rules

Diagrams in `/docs/diagrams/*.md` are living artifacts. When Claude edits one (on SoJo's request or to reconcile with other docs):

1. Update the Mermaid block.
2. Update the walkthrough prose to match.
3. Update the "Decisions embedded" section if any decision changed.
4. Add a row to the file's `## Changelog` table: date, what changed, why, downstream effects.
5. **Flag downstream inconsistencies**: if the change now conflicts with a spec, an ADR, the glossary, or another diagram, list the conflicts at the top of Claude's response so SoJo can decide how to resolve each.

Git holds change history, not Claude. Use `git log docs/diagrams/<file>.md` to see history across sessions.

---

## 9. Architectural principles (locked in before stack decision)

These shape stack selection and every feature built:

1. **Multi-actor data model from day one.** Even though only coaches use the prototype UI, the DB and auth model treats `coach`, `client`, and `admin` as first-class actor types. Foreign keys, row-level security, and auth scopes are designed accordingly. **No single-tenant shortcuts.**
2. **Transcript source is pluggable.** The prototype assumes coaches paste Zoom AI Companion summaries. Production treats "transcript source" as an interface: Zoom summary, Google Meet summary, manual paste, uploaded file, future direct API integration. No code path hardcodes "Zoom."
3. **Prompts are versioned artifacts.** Every LLM prompt lives in source control with a version number and changelog. Production never uses an un-versioned prompt.
4. **LLM calls are observable.** Every LLM call logs: prompt version, input token count, output token count, model, latency, cost in INR. Non-negotiable — this is how you catch regressions and manage cost.
5. **PII and session content are encrypted at rest and in logs.** Session summaries may contain health disclosures. Logs redact by default; structured PII fields are encrypted column-level where the chosen DB supports it.
6. **Consent is a first-class entity.** DPDP requires explicit, revocable, purpose-limited consent. The data model has a `consents` table from day one, even if the prototype UI doesn't expose it.
7. **India-region data residency** for any table holding personal or session data.
8. **Deletion is real.** When a user revokes consent or requests deletion, the record is deleted (or irreversibly anonymized), not soft-deleted with a flag. DPDP requires this.

These principles constrain stack selection. See ADR-0001.

---

## 10. Compliance summary (India, current best understanding — verify with counsel before launch)

- **DPDP Act 2023** governs. Key obligations: lawful purpose, explicit consent, purpose limitation, retention limits, grievance officer for scaled operations, breach notification.
- **Sensitive personal data** (health) is not a separate category under DPDP the way it is under GDPR, but **reasonable security practices** are expected and health data is high-risk in practice.
- **Cross-border transfers** are permitted subject to government notifications; safest default is India-region hosting for personal data.
- **Children's data** (under 18) needs verifiable parental consent — relevant if clients include minors.
- **DISHA** (Digital Information Security in Healthcare Act) is draft legislation. If the product takes on clinical functions (diagnosis, prescriptions, EHR) it may apply.
- **SPDI Rules under IT Act** still technically apply alongside DPDP until fully superseded.

Claude does not give legal advice. For anything material, SoJo consults an Indian data-protection lawyer. Claude's job is to not architect *around* these requirements.

---

## 11. Commands (populated after stack decision)

Will hold `dev`, `test`, `typecheck`, `lint`, `migrate`, `build`, `deploy` commands. Until then, Claude does not assume any command exists — it asks.

---

## 12. When in doubt

Default behavior when Claude is uncertain: **stop, declare what's missing, ask**. Silence or plausible-sounding guesses are the two failure modes the anthem exists to prevent.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- ALWAYS read graphify-out/GRAPH_REPORT.md before reading any source files, running grep/glob searches, or answering codebase questions. The graph is your primary map of the codebase.
- IF graphify-out/wiki/index.md EXISTS, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
