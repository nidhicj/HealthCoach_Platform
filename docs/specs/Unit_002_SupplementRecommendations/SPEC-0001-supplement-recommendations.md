# SPEC-0001: Supplement Recommendations

**Status**: Accepted
**Date**: 2026-06-25
**Owner**: SoJo
**Relates to**: `domain/glossary.md`, `domain/actors.md`, `docs/specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md`
**Implemented by phases**: _(to be filled as phases ship)_

---

## Goal

Give the HC a permanent, client-scoped log of supplement recommendations. When an HC recommends a supplement to a client — specifying the name, dosage, duration, and optional reason — that recommendation is recorded and visible on the client detail page indefinitely. The HC can review the full history at a glance, edit past entries for corrections, and remove entries that were added in error.

This is an internal HC tool. No supplement data is surfaced to the client at MVP.

---

## Non-goals

- **Medications** — this feature covers wellness supplements only (vitamins, minerals, protein, adaptogens, etc.). Prescription or OTC medications are explicitly out of scope.
- **Client-facing view** — clients cannot see their supplement log at MVP.
- **Session linking** — supplement entries are standalone. No `session_id` association.
- **Automated reminders** — no push or check-in prompts tied to supplements at MVP.
- **Brand catalog / sponsorships** — the supplement name is free text at MVP backed by a mock dropdown. A proper brand-linked catalog and sponsorship/ad integration is a future phase (see §Out of scope).
- **Client page layout redesign** — the supplements section is inserted into the existing client detail layout. A broader rearrangement of the client page is a separate spec.
- **LLM involvement** — no AI generation or analysis of supplement recommendations at MVP.

---

## Actors and roles

| Actor | Role | What they can do |
|---|---|---|
| Health Coach (HC) | Primary user | Add, edit, soft-delete supplement recommendations for their own clients |
| Client | Not in scope at MVP | Cannot read or interact with supplement data |

All routes are scoped to the HC's JWT `hc_user_id`. A recommendation belonging to HC-A is a 404 (never 403) for HC-B.

---

## Domain terms

| Term | Definition |
|---|---|
| Supplement recommendation | A logged entry by an HC recording that they recommended a specific supplement to a client, including dosage, duration, date, and optional notes |
| Supplement catalog | The platform-managed list of supplement names available in the dropdown. Mock/hardcoded at MVP; a seeded DB table in a future phase |
| Dosage | Free-text description of the quantity and frequency, e.g. "2000 IU daily", "1 scoop post-workout" |
| Duration (days) | Integer number of days for which the supplement was recommended |
| Recommended at | The date the HC made the recommendation; defaults to today, HC-editable |

---

## User stories

- As an HC, I want to log a supplement recommendation for a client so that I have a record of what I've advised and when.
- As an HC, I want to see the full history of supplement recommendations for a client so that I can review my past advice before a session.
- As an HC, I want to edit a recommendation I've already logged so that I can correct mistakes without losing the record.
- As an HC, I want to remove a recommendation I entered in error so that my client's log stays accurate.
- As an HC, I want to select a supplement from a pre-populated list so that entry is fast and consistent, with the option to type a custom name if what I need isn't listed.

---

## Flow

### Adding a supplement recommendation

1. HC opens the client detail page.
2. HC locates the "Supplement Recommendations" section in the left main column (between Closed action items and Sessions).
3. HC clicks **"+ Add"**.
4. An inline form expands below the section header with fields: Name (combobox), Dosage, Duration (days), Date (pre-filled today), Notes (optional).
5. HC types in the Name field — the dropdown filters the mock catalog in real time.
6. If the supplement isn't in the list, HC confirms their typed text as a custom entry.
7. HC fills remaining fields and clicks **Save**.
8. The new entry appears at the top of the list (newest first). The inline form collapses.

### Editing a recommendation

1. HC clicks **Edit** on an existing entry row.
2. An inline form pre-filled with that entry's data expands in place.
3. HC makes changes and clicks **Save** → PATCH is sent, entry updates in place.
4. Or HC clicks **Cancel** → form collapses, no change.

### Removing a recommendation

1. Inside the edit form, HC clicks **Remove**.
2. A confirmation prompt appears inline: "Remove this entry?".
3. HC confirms → DELETE is called → `archived_at` is set → entry disappears from the list.

### Empty state

- No entries yet → "No supplements logged yet." (muted italic, consistent with other empty states on the page).

---

## Data

### New table: `supplement_recommendations`

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | UUID | PK, gen_random_uuid() | |
| `hc_user_id` | UUID | FK → users.id, NOT NULL | Tenant scope |
| `client_id` | UUID | FK → clients.id, NOT NULL | Owning client |
| `name` | TEXT | NOT NULL | Supplement name — catalog entry or custom free text |
| `dosage` | TEXT | nullable | e.g. "2000 IU daily" |
| `duration_days` | INTEGER | nullable | Number of days recommended |
| `recommended_at` | TIMESTAMPTZ | NOT NULL, default now() | HC-editable date |
| `notes` | TEXT | nullable | Optional reason / context |
| `created_at` | TIMESTAMPTZ | NOT NULL, default now() | Immutable |
| `archived_at` | TIMESTAMPTZ | nullable | NULL = active; set on soft-delete |

**Index:** `(hc_user_id, client_id)` — the only query shape at MVP is "all recommendations for this client, owned by this HC."

**Tenant safety:** every query filters by both `client_id` and `hc_user_id`. Client 404s for cross-tenant requests follow the platform convention (never 403).

**Hard delete:** not exposed via API. Real deletion happens only through the DPDP consent/deletion flow (platform-wide, not feature-specific).

### Entities read (existing)

| Entity | Read | Write | New fields |
|---|---|---|---|
| `clients` | Y — ownership check | N | None |
| `supplement_recommendations` | Y | Y | New table — migration required |

---

## API surface

All routes require HC JWT (`require_role('hc')`). All are tenant-scoped via `current_tenant()`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/clients/{client_id}/supplements` | HC | Create a new recommendation |
| `GET` | `/api/clients/{client_id}/supplements` | HC | List all active (non-archived) recommendations, newest first |
| `PATCH` | `/api/clients/{client_id}/supplements/{id}` | HC | Edit any field on an existing recommendation |
| `DELETE` | `/api/clients/{client_id}/supplements/{id}` | HC | Soft-delete (sets `archived_at`) |

### POST — request body

```json
{
  "name": "Vitamin D3",
  "dosage": "2000 IU daily",
  "duration_days": 30,
  "recommended_at": "2026-06-25T00:00:00Z",
  "notes": "for gut health, based on blood report"
}
```

`name` is required. All other fields are optional. `recommended_at` defaults to server `now()` if omitted.

### GET — response

```json
[
  {
    "id": "...",
    "name": "Vitamin D3",
    "dosage": "2000 IU daily",
    "duration_days": 30,
    "recommended_at": "2026-06-25T00:00:00Z",
    "notes": "for gut health, based on blood report",
    "created_at": "2026-06-25T10:30:00Z"
  }
]
```

No pagination at MVP — returns all active entries. If volume becomes a concern, a cursor-based page is added in a follow-up.

### PATCH — request body

All fields optional — only provided fields are updated.

```json
{
  "name": "Vitamin D3",
  "dosage": "4000 IU daily",
  "duration_days": 60,
  "recommended_at": "2026-06-25T00:00:00Z",
  "notes": "increased dose after retest"
}
```

### DELETE — response

`204 No Content`. Sets `archived_at`; does not physically remove the row.

---

## LLM involvement

None at MVP.

---

## Coach-reviewed gate

Not applicable — no AI-generated content in this feature.

---

## Frontend

### Placement

Left main column of the client detail page (`/clients/[clientId]/page.tsx`), inserted between the "Closed action items" section and the "Sessions" section.

### Section card

Styled consistently with existing sections: `rounded-2xl border border-border bg-muted p-6`.

Header row: label "SUPPLEMENT RECOMMENDATIONS" (uppercase tracking-widest, `text-primary`) + **"+ Add"** button right-aligned.

### List row layout

```
Vitamin D3
2000 IU daily  ·  30 days  ·  25 Jun 2026
for gut health, based on blood report                    [Edit]
```

- Name: `font-sans text-sm text-foreground`
- Secondary line (dosage · duration · date): `font-sans text-xs text-muted-foreground`
- Notes (if present): `font-sans text-xs italic text-muted-foreground`
- Edit link: `font-sans text-xs text-primary`

### Inline form fields

| Field | Input type | Validation |
|---|---|---|
| Name | Combobox (searchable dropdown + free text) | Required |
| Dosage | Text input | Optional |
| Duration (days) | Number input, integer, min 1 | Optional |
| Date recommended | Date picker, defaults to today | Required |
| Notes | Textarea | Optional |

### Mock supplement catalog (hardcoded at MVP)

Vitamin D3, Vitamin B12, Vitamin C, Omega-3 / Fish Oil, Magnesium, Iron, Zinc, Calcium, Ashwagandha, Curcumin / Turmeric, Probiotics, Whey Protein, Plant Protein, Multivitamin, Collagen, Biotin, CoQ10, Melatonin.

HC can type any name not in this list and confirm it as a custom entry.

### States

| State | Behaviour |
|---|---|
| Loading | Two `Skeleton` rows (consistent with other sections) |
| Empty | "No supplements logged yet." — `font-sans text-sm italic text-muted-foreground` |
| Error | "Could not load supplements." — `text-destructive` |

---

## Edge cases and failure modes

| Case | Behaviour |
|---|---|
| Cross-tenant GET/PATCH/DELETE | Client ownership check fails → 404 (never 403) |
| POST with `name` missing | 422 Unprocessable Entity |
| PATCH on an archived entry | 404 — archived entries are not found by standard queries |
| DELETE already-archived entry | 404 |
| `duration_days` < 1 | 422 |
| `recommended_at` in the future | Allowed — HC may pre-log a recommendation |
| Network error on save | Inline form stays open; error message shown beneath the form |
| Network error on delete | Confirmation resets; error message shown |

---

## Acceptance criteria

- [ ] `supplement_recommendations` table created via Alembic migration; indexes in place
- [ ] `POST /api/clients/{client_id}/supplements` creates a row scoped to the HC's tenant; returns 201
- [ ] `GET /api/clients/{client_id}/supplements` returns all non-archived rows newest-first; cross-tenant returns 404
- [ ] `PATCH /api/clients/{client_id}/supplements/{id}` updates only supplied fields; cross-tenant returns 404
- [ ] `DELETE /api/clients/{client_id}/supplements/{id}` sets `archived_at`; returns 204; cross-tenant returns 404
- [ ] `POST` with no `name` returns 422
- [ ] `PATCH` / `DELETE` on an archived entry returns 404
- [ ] Client detail page loads supplement recommendations alongside existing data (parallel fetch)
- [ ] Supplement section renders in left column between Closed action items and Sessions
- [ ] "+ Add" expands inline form; Save calls POST; new entry appears at top without full page reload
- [ ] Edit expands inline form pre-filled; Save calls PATCH; entry updates in place
- [ ] Remove inside edit form soft-deletes; entry disappears from list
- [ ] Name combobox filters mock catalog on keystroke; custom text entry accepted when no match
- [ ] Loading, empty, and error states all render correctly
- [ ] All integration tests pass; no existing tests broken

---

## Open questions

None — all decisions resolved during spec brainstorming on 2026-06-25.

---

## Out of scope (future phases)

- **Brand-linked supplement catalog** — replace hardcoded list with a `supplement_catalog` DB table; link brands to catalog entries; enable brand sponsorship pages or inline ads on the client supplement log
- **Client-facing supplement view** — allow clients to see their own supplement history via the `/me` API
- **Active vs ended state** — surface a visual distinction between recommendations still within their `duration_days` window and those that have ended
- **Client page layout redesign** — rearrange all cards on the client detail page; supplements section placement will be revisited at that point
- **Supplement reminders** — push or check-in prompts triggered by supplement duration milestones

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-06-25 | Initial draft and acceptance. | Brainstorming session with SoJo — feature scoped, designed, and approved in one session |
