# User Flow — Tapas (Coach-facing MVP)

> Source of truth for the coach user flow across all built screens.
> Reflects the state after PHASE-10 (Roster Board, Client Detail restructure, MOM generation, public landing page).

---

## Diagram

```mermaid
flowchart TD
    %% ── Public ───────────────────────────────────────────────────────────────
    subgraph publicZone ["Public"]
        landing([Tapas Landing])
        signIn[Sign in with Google]
        callback{{Auth callback}}
    end

    %% ── Auth gate ────────────────────────────────────────────────────────────
    authCheck{Authenticated?}

    %% ── Authenticated app ────────────────────────────────────────────────────
    subgraph appZone ["Authenticated app"]
        dashboard[Roster Board]
        actionItems[Action Items]
        settings[Settings]

        subgraph clientZone ["Client management"]
            newClient[New client form]
            clientDetail[Client detail]
            generateChart[Generate chart]
            chartEditor[Diet chart editor]
        end

        subgraph sessionZone ["Session workflow"]
            newSession[New session]
            sessionPage[Session page]
            momTab[MOM tab]
            draftMom[Generate MOM draft]
            sendMom[Send to client]
        end

        subgraph settingsZone ["Settings"]
            dietTemplates[Diet chart templates]
            sessionSettings[Session settings]
        end
    end

    %% ── Edges ────────────────────────────────────────────────────────────────
    landing --> authCheck
    authCheck -->|"Not signed in"| signIn
    authCheck -->|"Session valid"| dashboard
    signIn --> callback
    callback --> dashboard

    dashboard --> newClient
    dashboard --> clientDetail
    dashboard --> actionItems
    dashboard -.-> settings

    newClient --> clientDetail
    clientDetail --> newSession
    clientDetail --> generateChart
    generateChart -.-> clientDetail
    clientDetail -.-> chartEditor
    chartEditor -.-> clientDetail

    newSession --> sessionPage
    sessionPage --> momTab
    momTab --> draftMom
    draftMom --> sendMom
    sendMom -.-> clientDetail

    settings --> dietTemplates
    settings --> sessionSettings

    %% ── Colours (semantic) ───────────────────────────────────────────────────
    style publicZone    fill:#C6FAF6,stroke:#5AD8CC
    style appZone       fill:#F5F5F5,stroke:#B3B3B3
    style clientZone    fill:#DCCCFF,stroke:#874FFF
    style sessionZone   fill:#FFECBD,stroke:#FFC943
    style settingsZone  fill:#D9D9D9,stroke:#B3B3B3
    style dashboard     fill:#C2E5FF,stroke:#3DADFF
    style landing       fill:#C2E5FF,stroke:#3DADFF
    style sendMom       fill:#CDF4D3,stroke:#66D575
```

---

## Walkthrough

**Entry**
A visitor hits `/` (Tapas Landing). The page silently tries a token refresh — if the cookie is valid, they land directly on the Roster Board. If not, they see the marketing page and click "Get started" → `/sign-in` → Google OAuth → `/auth/callback` → Roster Board.

**Daily loop**
The Roster Board (`/dashboard`) is the hub. The coach sees their active client grid, today's session pills, and any milestone/flag signal. From here every branch fans out.

**Client flow**

- `+ New client` → form → on save lands on Client detail
- Clicking a client card → Client detail directly

**Client detail**
The main working screen. From here the coach can:

- Start a new session → Session page
- Generate a diet chart inline (template picker, skeleton → reveal)
- Open the full diet chart editor (`/clients/[id]/diet-chart`)
- Review open action items and supplements

**Session workflow (the core loop)**
New session → Session page → MOM tab → Generate draft (skeleton → fade-in reveal) → edit → Send. After send, the dotted edge returns to Client detail — the coach picks the next client.

**Settings**
Accessible via the nav (dotted edge from dashboard = not the primary path). Diet chart templates is where coaches manage their reusable chart formats — the source for the inline Generate flow.

---

## Decisions embedded

- `flowchart TD` chosen over `LR` — the auth gate + app hierarchy reads top-to-bottom naturally
- Dotted edges (`-.->`) = optional or return paths; solid edges = primary forward flow
- `sendMom` is green — it's the meaningful completion event in the session loop
- `settings` kept as a connector node outside `settingsZone` — it maps to the real nav link

---

## Changelog

| Date       | Change          | Why                                           | Downstream effects |
| ---------- | --------------- | --------------------------------------------- | ------------------ |
| 2026-06-30 | Initial diagram | PHASE-10 shipped — first complete coach flow | None yet           |

```
```
