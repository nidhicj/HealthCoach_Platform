# Frontend Feedback — P6 Review

> Collected after P6 mock test run (2026-05-07).
> Each item is triaged: **P6-fix** (code change only, no design discussion needed) vs
> **P6B-spec** (needs brainstorming + spec before building) vs **future** (outside Unit 001 scope).

---

## Triage summary

| # | Item                                                        | Label        | Effort |
| - | ----------------------------------------------------------- | ------------ | ------ |
| 1 | Dashboard section background blocks                         | `P6-fix`   | Small  |
| 2 | Replace "Recent Clients" with something better              | `P6B-spec` | Medium |
| 3 | Today's session: show Client name + Session #               | `P6-fix`   | Small  |
| 4 | Action item checkboxes + client page layout                 | `P6-fix`   | Medium |
| 5 | Diet chart feature (preview, AI generation, editable table) | `P6B-spec` | Large  |

**Bottom line**: items 1, 3, 4 can be fixed in this session without any design discussion.
Items 2 and 5 need a brainstorm with claude.ai first — they involve product decisions, not just code.

---

## ~~Item 1 — Dashboard section background blocks~~

> "Need to add background color blocks for every section of dashboard — helps bifurcate visually"

**Triage: `P6-fix`**

Pure CSS/Tailwind change. No data or logic involved. Each dashboard section (Today, Open Action
Items, Recent Clients) gets a card/surface background to visually separate them.
Can be done directly in `dashboard/page.tsx`.

---

## Item 2 — "Recent Clients" section: keep or replace?

> "We can discuss if we even need 'Recent Clients' in dashboard — we may include something better"

**Triage: `P6B-spec`**

This is a product decision, not a code fix. "Recent Clients" is a default dashboard widget but
may not be the most useful thing for an HC. Alternatives to brainstorm with claude.ai:

- **Recent activity**: last session per client with status (brief generated? MOM sent?)
- **Upcoming sessions**: clients with a session scheduled in the next 7 days
- **Follow-up needed**: clients who haven't had a check-in in N days
- **Quick links**: HC's most active clients (most sessions in last 30 days)

Bring this to claude.ai as: *"What should the HC see on their dashboard? Current state is:
Today's sessions, Open Action Items, Recent Clients. What would make the dashboard most
useful for a coach who sees 8–15 clients?"*

---

## ~~Item 3 — Today's session: Client name + Session number~~

> "'Today' section has 'Session #' only — need to change it to 'Client_name - Session #[#]'"

**Triage: `P6-fix`**

The client name is already available via the session's `client_id` relationship. This is a
display change in the Today's Sessions list — show `{client.full_name} — Session {session_number}`
instead of just `Session {session_number}`. One-line template change.

---

## ~~Item 4 — Open Action Items: checkboxes + client page section~~

> "Open Action Items must have checkbox accountability — HC can know what is actually pending
> vs followed up. Add section above sessions on client detail page with checkboxes. If checked,
> AI should include it as a progress pointer."

**Triage: `P6-fix`** (UI + existing API) | Part of it may need spec clarification

**What can be done in P6-fix:**

- Add an "Open Action Items" section to the client detail page, above the sessions list
- Each item has a checkbox on the left; checking it calls `PATCH /api/action-items/{id}` with
  `{"status": "completed"}` — this API already exists
- Completed items shown with strikethrough / greyed out

**On the AI consideration part:** The brief already uses the AST, which includes open and missed
items. When an item is marked completed (via checkbox), the AST reflects it immediately — so the
next brief will treat it as a completed win, not an open risk. This already works by design.

If you want the brief to *explicitly call out* completed items as "progress wins" (e.g., "HC
confirmed Ravi completed the protein target"), that would need a prompt change — flag for the
P6B spec discussion if you want that level of explicitness.

---

## Item 5 — Diet chart feature

> "Diet chart block for every client at details/sessions. Small preview on client page, expands
> to full chart. 7-day × meals table. Timings in cells. Editable columns (add/remove meals like
> snack). AI suggests chart after first session, HC approves, then displayed."

**Triage: `P6B-spec`** (new feature, needs full spec)

This is a substantial new feature. The DB tables (`diet_charts`, `diet_chart_recipes`,
`prep_recipes`, `content_assignments`) were built in P1 for exactly this, so the data layer
is ready. But it needs design decisions before building:

**Questions to resolve in brainstorm:**

1. Is the diet chart per-client (one chart, updated over time) or per-session (a new version each session)?
2. When AI suggests a chart, what data does it draw from — only the first session notes, or also the onboarding M000 notes?
3. What does "HC approves" look like — a confirm button, or full edit-first-then-approve?
4. How does the editable table work — inline editing, or a dedicated edit mode?
5. Is the diet chart sent to the client eventually, or is it internal HC tooling for now?
6. How does this relate to the MOM — does a session MOM reference the diet chart?

**Bring to claude.ai as:** *"Design a diet chart feature for the HC platform. DB tables already
exist (diet_charts, diet_chart_recipes, prep_recipes). Here are the requirements: [paste item 5]
and the 6 questions above."*

This should then produce a SPEC-XXXX document and become **P6.B** or be absorbed into P7
depending on scope.

---

## Item 6 -- Revise "Action Items" endpoint

What we have in 'action-items' endpoint is very much spread across and does not give a structured information. That's why I want to introduce a table structure for action items endpoint in the front end. That way the HC can think that this is their kanban board and understand that okay. This action item is ongoing or in progress or it's done. So this table structure I want to introduce. Maybe we can develop better things on top of this once I get an input from HC

**Table structure**

| Client | logged on (DATE) | PHASE-1: Open Action items | PHASE-2: In progress | PHASE-3: Closed Action items |
| ------ | ---------------- | -------------------------- | -------------------- | ---------------------------- |
| CP001  | DD/MM/YYYY       | 1. _ _ _ _ _ _             | 1. _ _ _ _           | 1. _ _ _ _                   |
|        | DD/MM/YYYY       | 2. _ _ _ _ _               | 2. _ _ _ _           | 2. _ _ _ _                   |
| CP002  |                  |                            |                      |                              |

**Note** -

* On the item "1. ___" in the Open Action items column (Phase 1) → it must be a "**DRAGGABLE ITEM BETWEEN PHASES** "
* I have used '**phases'** term only for understanding purpose now. Must come up with something better - you suggest

---
