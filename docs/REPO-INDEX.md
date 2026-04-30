# PROJECT-INDEX.md

> Master index for the Health Coach Platform. **Read this first** when entering the repo or returning after time away. Tells you what each file owns and where to find authoritative answers.

> When two files conflict: this index records which one is authoritative. Update this index whenever a file's role changes.

---

## Operating contract (root)

| File | Owns | Read when |
|---|---|---|
| `README.md` | Repo overview, quickstart, links | First contact with the repo |
| `CLAUDE.md` | Operating contract for Claude Code (full anthem) | Every Claude Code session |
| `PREFLIGHT.md` | Preflight reference with worked examples | Reference during Claude work |
| `PROJECT-CUSTOM-INSTRUCTIONS.md` | Claude.ai project's custom instructions | Reference; mirror of project settings |
| `SESSION_LOG.md` | Session-to-session handoff record | End of every substantive session; start of next |
| `docs/PROJECT-INDEX.md` | This file | When you don't know where something lives |

---

## Architecture decisions (`docs/decisions/`)

ADRs are the architectural commitments. New decisions add a new ADR; existing decisions change via supersession, not silent edit.

| File | Owns | Status |
|---|---|---|
| `0000-template.md` | ADR template — copy this for new ADRs | n/a |
| `0001-stack-selection.md` | Stack: FastAPI + Cloudflare Workers + AWS Mumbai + OpenRouter; snippet library; model chain | Accepted |
| `0002-runtime-topology.md` | When to split runtimes vs migrate to DO Bangalore (diagnostic playbook) | Accepted |
| `0003-llm-strategy.md` | LLM service mechanics: validation, retry, telemetry, snippet capture/selection | Proposed (flip to Accepted before code) |
| `0004-repo-structure.md` | Folder layout, naming, env-driven config | Accepted |
| `0005-auth-strategy.md` | Google OAuth, JWT, refresh rotation, tenant scoping | Accepted |
| `0006-observability.md` | Sentry + structured logs + `llm_calls`; signal-to-trigger map | Accepted |

---

## Feature specs (`docs/specs/`)

Specs describe *what to build*. They reference ADRs for *how* and domain docs for *what things mean*.

| File | Owns | Status |
|---|---|---|
| `0000-template.md` | Spec template — copy this for new features | n/a |
| `0001-hc-core-cycle.md` | The central product loop: M000, M00N, MOM, brief, AST, action items, triage flags, coach-reviewed gate | Accepted |

---

## Domain (`docs/domain/`)

Canonical definitions. When code, prompts, or UI use a term, it MUST match the domain doc.

| File | Owns | Authority |
|---|---|---|
| `glossary.md` | All HC cycle terms (HC, MOM, AST, snippet, etc.) | Highest — UI/code/specs all defer here |
| `actors.md` | Who does what; HC vs Client vs Junior HC vs Operator | High |
| `compliance-india.md` | DPDP posture, data residency, prototype scope | High; legal review pending |

---

## Diagrams (`docs/diagrams/`)

Visual references — system topology and data shape. Code defers to these.

| File | Owns |
|---|---|
| `0001-system-architecture.md` | Component diagram: client → CF Pages/Workers → AWS Mumbai → OpenRouter |
| `0002-data-model.md` | ERD with full DDL, cascade rules, migration order |

---

## Operations (`docs/ops/`)

Operational runbooks. **Templates at MVP** — fill in DECIDE/FILL IN markers as you make decisions.

| File | Owns | Maturity |
|---|---|---|
| `cloudflare-cost-reference.md` | Workers limits, pricing, dashboard navigation | Reference (filled in) |
| `secrets-management.md` | Secret inventory, storage, rotation | Template — decisions pending |
| `deployment.md` | How to deploy backend, frontend, migrations | Template — decisions pending |
| `backup-restore.md` | Backup approach, RPO/RTO targets, restore procedures | Template — decisions pending |
| `incident-response.md` | SEV levels, on-call, common playbooks | Template — decisions pending |

---

## Standards (`docs/standards/`)

Engineering conventions. Apply across all phases.

| File | Owns |
|---|---|
| `CONTRIBUTING.md` | Branching, commits, PR checklist, when to write what |
| `testing-strategy.md` | Test layers (unit, integration, llm-evals), CI gating |

---

## Legal (`docs/legal/`)

**Empty at MVP.** Privacy policy and Terms of Service drafted post-pilot, with a lawyer.

---

## Build plan

| File | Owns |
|---|---|
| `docs/build-plan.md` | Phase-by-phase milestones (P0–P9), acceptance criteria, traceability matrix, fishbone diagram |

---

## Resolution rules

When something is ambiguous:

1. **Code conflicts with ADR** → ADR wins. Fix the code, or amend the ADR (and document why).
2. **ADR conflicts with ADR** → newer ADR wins if it explicitly supersedes. If not, flag and resolve via amendment.
3. **Spec conflicts with ADR** → ADR wins on architecture; spec wins on product behavior.
4. **Glossary conflicts with anything** → glossary wins on terminology. Update the other thing.
5. **This index conflicts with reality** → reality wins; update this index immediately.

---

## Maintenance

Update this index when:
- A new ADR / spec / runbook / standard is added.
- A file's status changes (Proposed → Accepted, etc.).
- A file is superseded or moved.
- The "Owns" column would change.

Don't update for: minor edits, prose tweaks, or content changes that don't change scope.
