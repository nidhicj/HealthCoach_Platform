# Phase 6B Frontend Design
**Date:** 2026-05-12  
**Phase:** PHASE-06B under `Unit_001_HcCoreCycle`  
**Scope:** Two frontend-only changes. Zero backend changes. Zero new npm dependencies.

---

## Item 2 — Dashboard Restructure

### What changes
`frontend/src/app/(app)/dashboard/page.tsx`

Remove the "Recent Clients" section entirely. The dashboard retains two sections:
1. **Today** — unchanged
2. **Pending Action Items** — restructured rows

### Pending Action Items row layout
Each item renders two lines:

```
Ravi Kumar  ·  12/05/2026        ← client full_name + created_at (DD/MM/YYYY, en-IN locale)
Protein tracking log              ← description
```

**Data sources — already in scope, no new fetches:**
- `clientMap: Map<string, ClientOut>` — built from the existing `listClients` call
- `item.created_at` — present on `ActionItemOut`
- `item.description` — present on `ActionItemOut`
- `item.client_id` — key for `clientMap` lookup

### Definition of done
- "Recent Clients" section and all its state (`clients`, `setClients`) removed
- `listClients` call **stays** — `clientMap` is still used in the Today section to show `{client.full_name}` next to each session. Remove only the `clients` state variable (`const [clients, setClients]`) and the `setClients(c.items.slice(0, 5))` line inside `.then()`
- Each pending action item row shows: `{full_name} · {created_at formatted}` on line 1, `{description}` on line 2
- Overdue items retain the red date treatment already in the codebase

---

## Item 6 — Action Items Kanban

### What changes
`frontend/src/app/(app)/action-items/page.tsx`

Replace the current three-section vertical list (Open / In Progress / Missed) with a single client×status table.

### Table structure

| Client | Open | In Progress | Done |
|--------|------|-------------|------|
| Ravi Kumar | item cards… | item cards… | item cards… |
| Sunita Rao | item cards… | item cards… | — |

- **Rows:** one per client (derived by grouping fetched items by `client_id`)
- **Columns:** Open · In Progress · Done (3 columns, fixed)
- **Missed/overdue items** live in the Open column — shown with a red card border + "Overdue" label. No 4th column.
- **Empty cells** render a muted `—`

### Item card anatomy
Each card inside a cell:
```
┌─────────────────────────────┐
│ Protein tracking log        │  ← description
│ 08 May 2026          Overdue│  ← created_at + overdue badge (if applicable)
│ Move to In Progress →       │  ← forward action (Open and In Progress only)
│ ← Back to Open              │  ← backward action (In Progress and Done only)
└─────────────────────────────┘
```

**Click-to-move actions by column:**

| Column | Forward button | Backward button |
|--------|---------------|-----------------|
| Open | "Move to In Progress →" | — |
| In Progress | "Mark Done →" | "← Back to Open" |
| Done | — | "← Reopen" |

Each button calls `patchActionItem(item.id, { status: targetStatus })` and updates local state optimistically.

### Data fetching
Fetch all non-completed and completed items in parallel:
```ts
Promise.all([
  listActionItems({ status: "open",        limit: 100 }),
  listActionItems({ status: "in_progress", limit: 100 }),
  listActionItems({ status: "missed",      limit: 100 }),
  listActionItems({ status: "completed",   limit: 100 }),
  listClients({ limit: 100 }),   // ← needed for client display names + row grouping
])
```

`missed` items are fetched and merged into the `open` bucket for display (they render with overdue treatment). Client names come from the clients fetch.

### Grouping logic
```
clientRows = clients.map(client => ({
  client,
  open:        allItems.filter(i => i.client_id === client.id && (i.status === "open" || i.status === "missed")),
  in_progress: allItems.filter(i => i.client_id === client.id && i.status === "in_progress"),
  done:        allItems.filter(i => i.client_id === client.id && i.status === "completed"),
}))
// Omit rows where the client has zero items across all columns
.filter(row => row.open.length + row.in_progress.length + row.done.length > 0)
```

### Status transition map
```ts
const MOVE_FORWARD: Record<string, string> = {
  open:        "in_progress",
  in_progress: "completed",
  missed:      "in_progress",   // missed items can be moved forward too
}
const MOVE_BACK: Record<string, string> = {
  in_progress: "open",
  completed:   "in_progress",
}
```

### Optimistic update pattern
On click: update local state immediately, then fire the PATCH. On error: revert to previous status. Same pattern already used in `clients/[clientId]/page.tsx`.

### Overdue detection
Re-use the existing `isOverdue(dateStr)` helper already in the file.

### Definition of done
- Page renders a table with one row per client that has ≥1 action item (any status)
- Items group correctly into Open / In Progress / Done columns
- Missed items appear in Open column with red border + "Overdue" label
- All click-to-move buttons call the correct PATCH and update state optimistically
- Empty cells show `—`
- Page is responsive: table scrolls horizontally on narrow screens (`overflow-x-auto`)
- No new npm dependencies added

---

## What is NOT in P6B

- Diet chart feature → **P6C** (separate phase, needs backend endpoints + AI integration first)
- Any backend changes
- Any new npm packages
- Error boundaries / Sentry (P7 scope per HANDOVER-P6)
- M000 UX redirect (P7 scope)
