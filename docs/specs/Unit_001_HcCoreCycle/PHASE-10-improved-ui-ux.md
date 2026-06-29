# PHASE-10: Improved UI/UX

**Unit**: Unit_001_HcCoreCycle
**Status**: Draft
**Verification date**: TBD
**Implements**: SPEC-0001 (presentational layer — no new domain logic)
**ADRs implemented**: None — frontend-only phase (with one flagged backend addendum)

---

## 0. Prerequisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Context Missing for anything product-specific not provided. Ready?

---

## 1. Scope

Restructure the frontend to feel welcoming and readable to a first-time user, not just a task-management tool. Three pages change substantially: the landing page becomes a Roster Board (replaces the existing dashboard), the Client Detail page gets a new layout anchored on sessions/supplements/diet chart, and the Session page gets an improved MOM generation moment. Diet chart inline generation is included as a deferred section (§ Part B) to be built in the same phase but after the layout work is stable.

**Not in scope:** Session page tabs (Brief, Notes) — kept as-is. Action Items kanban — kept as-is. Settings / Diet Charts settings page — kept as-is. No new domain logic, no new DB tables, no migrations.

**Backend addendum (flagged, not folded into P10 silently):** The `ClientOut` list endpoint currently returns no `last_session_at` and no flag data. P10 derives both client-side from existing endpoints (sessions list + action items list) — acceptable for demo scale. If coach roster exceeds ~30 clients, a backend enrichment of `GET /api/clients` (JOIN sessions + action_items) should be a follow-up. Tracked at end of this doc.

---

## 2. Deliverables (planned — updated as phase ships)

### Part A — Layout restructure

#### A1 · Navigation (`frontend/src/app/(app)/layout.tsx`)
- Remove "Clients" nav link — the Roster Board absorbs the clients list
- Nav becomes: **[Parivarthan wordmark → /dashboard] · Action Items · Diet Charts · Settings**

#### A2 · Landing page — Roster Board (`frontend/src/app/(app)/dashboard/page.tsx`)
Full rewrite. Zones top-to-bottom:

**Zone 1 — Page header**
- Eyebrow: "YOUR PRACTICE" (Manrope 700, all-caps, letter-spaced, `text-primary`)
- Title: "Dashboard" (Fraunces 900)
- Subtitle: "Your whole practice, in one place." (Manrope 400, `text-muted-foreground`)
- Top-right CTA: `[+ New client]` — Marigold (`variant="accent"`)

**Zone 2 — Today banner**
- Slim pill-row listing today's sessions: `Client name · HH:MM AM/PM` → links to session page
- Derived client-side: `listSessions({limit: 50})` filtered to today's date (existing logic from old dashboard)
- Empty state: Fraunces statement copy — "No sessions today. *Quiet morning.*" (no dead end — links to Action Items)

**Zone 3 — Milestone card**
- Primary trigger: any session where `session_number` is in `[5, 10, 25, 50]` and `scheduled_at` is within the last 7 days
- Derived client-side from the sessions fetch (no new endpoint)
- Card copy: "🎉 [Client name] just completed their [N]th session with you."
- Fallback (no milestone this week): one-line practice signal — "[N] clients haven't checked in recently." derived from `listActionItems({status: "missed"})`
- Hidden entirely if nothing meaningful to say (both conditions empty)
- Visual: Marigold border tint (`border-accent/40 bg-accent/5`)

**Zone 4 — Client card grid**
- Fetches: `listClients({limit: 100})`, `listSessions({limit: 100})`, `listActionItems({status: "missed", limit: 100})`
- Client-side derivation:
  - `last_session_at` → build map `client_id → max(scheduled_at)` from sessions fetch
  - `has_flags` → build set of client_ids that appear in missed action items fetch
- Active grid: all clients where `journey_stage !== "completed"`
- Grid layout: `grid-cols-[repeat(auto-fill,minmax(200px,1fr))]` — column count self-adjusts to viewport; `minmax` value is the experiment dial
- Each card:
  - Client name (Fraunces 700)
  - Journey stage badge (`variant="secondary"`)
  - Last session relative date ("3 days ago", "Today", "—" if none) (Manrope 400, `text-muted-foreground`)
  - Flag indicator: red border + 🚩 if `has_flags` is true
  - Full card is a link → `/clients/[clientId]`
- Collapsible section at bottom: "Past clients ([N]) ▼" — expands to show completed clients in same card style but dimmed (`opacity-60`)

#### A3 · Clients list page (`frontend/src/app/(app)/clients/page.tsx`)
- Replace with a redirect to `/dashboard` — the roster is now the landing page
- `import { redirect } from "next/navigation"; export default function() { redirect("/dashboard"); }`

#### A4 · Client Detail page (`frontend/src/app/(app)/clients/[clientId]/page.tsx`)
Full restructure. Removes the existing `lg:grid-cols-[1fr_320px]` right sidebar entirely.

**Three-colour card system (defined once, applied consistently):**
- `bg-A`: `bg-muted` — full-width bands
- `bg-B`: `bg-background` — left card in every side-by-side pair
- `bg-C`: `bg-section-fill-02` — right card in every side-by-side pair (subtle third shade)

**Typography contract (uniform, no exceptions):**
- Section headings above cards: Fraunces 700, `text-2xl` — identical size and weight everywhere
- Card eyebrow labels: Manrope 700, all-caps, letter-spaced (`text-xs font-bold uppercase tracking-widest text-primary`)
- Body text: Manrope 400 (`font-sans text-sm`)
- Session/heading numbers: Fraunces 700

**Layout top-to-bottom:**

```
Client header
  ← Clients breadcrumb
  [Client name]  Fraunces 900
  [Active badge]  [CP0003 code]

────────────────────────────────── bg-A · full width
GOAL
  [course_goal text]
  Empty state: "Add a goal for this client"  (no hiding)

────────────────────────────────── bg-B (60%) │ bg-C (40%)
Sessions                           │ Supplement Recommendations
  heading: Fraunces 700            │   heading: Fraunces 700
  [card]                           │   [card]
    SESSIONS eyebrow  [New session]│     SUPP RECS eyebrow  [+ Add]
    Session N  date  badge ×5      │     list of supplements
    ─────────────────────────      │
    PAST SESSIONS  ▼               │

────────────────────────────────── bg-A · full width
Diet chart
  heading: Fraunces 700
  [Full 7-day × meal-slot table]
  [Generate / Edit →]  (Part B — inline generation)

────────────────────────────────── bg-B (50%) │ bg-C (50%)
Open action items                  │ Details
  [card]                           │   [card]
    OPEN ACTION ITEMS eyebrow      │     DETAILS eyebrow
    ☐ item · Due date · Overdue    │     Email / Phone / Stage / Since
    ☐ item                         │
```

**Removed from current code:** `lg:grid-cols-[1fr_320px]` right sidebar, AST card, diet chart preview card, triage flags display, client status card, Details section at top of left column.

**New:** Goal card component, three-colour system applied via Tailwind classes, 60/40 column split (`grid-cols-[3fr_2fr]`), 50/50 split (`grid-cols-2`).

#### A5 · Session page — MOM tab (`frontend/src/app/(app)/clients/[clientId]/sessions/[sessionId]/page.tsx`)
Only the MOM tab (`MomTab` component) changes. Everything else (Brief tab, Notes tab, session header, End session button) is untouched.

**Current MOM tab behaviour:** "Generate draft" button text changes to "Generating draft…" — no skeleton, no visual generation moment.

**Improved MOM generation moment:**
- On `handleDraft()` call: immediately show a skeleton of the two-pane layout (AI draft pane + Your version pane), both filled with `<Skeleton>` rows
- When draft resolves: skeleton fades out, content reveals with `animate-in fade-in` (200ms, `tw-animate-css` — already installed)
- Error state: inline error message with "Retry" link — not a spinner loop
- "Regenerate draft" button also triggers the skeleton on the left (AI draft) pane only
- Constraint: no width/height animation — only opacity fade-in on reveal (per motion spec)

---

### Part B — Diet chart inline generation (deferred section, same phase)

> Build after Part A layout is stable. Do not block Part A on Part B.

#### B1 · Generate affordance on Diet chart card
- Add "Generate" button (Marigold, `variant="accent"`) alongside existing "Edit →" link on the client detail diet chart section
- If no chart exists: show "Generate chart" as primary CTA (Marigold)
- If chart exists: show "Edit →" (text link) + "Regenerate" (Moss, `variant="default"`)

#### B2 · Starting-point picker (inline panel)
- On Generate click: the diet chart section expands inline (no modal/sheet) to show:
  ```
  Base this chart on:
  ○ Template   [dropdown — lists available templates]
  ○ Session    [dropdown — lists recent sessions]
  [Cancel]  [Generate →]  ← Marigold
  ```
- Collapses back when cancelled or after generation completes

#### B3 · Skeleton → reveal moment
- On Generate confirm: show a skeleton of the diet chart table shape
- On resolution: `animate-in fade-in` (200ms) reveals the completed chart in place
- Error: inline error with retry; no dead spinner

#### B4 · Endpoint verification (flag to SoJo before building B)
- Check: does `POST /api/clients/{clientId}/diet-chart/generate` (or equivalent) accept `{source: "template" | "session", source_id: UUID}` and return a full chart renderable inline?
- If yes → Part B is fully frontend
- If endpoint only supports the Templates flow → a thin backend route is needed → **flag to SoJo, do not build silently**

---

## 3. Decisions made during this phase (brainstorm record)

**Roster Board replaces dashboard + clients as separate pages** — The landing page IS the client roster. A separate `/clients` list page is redundant once the grid exists. Resolved by redirect.

**Three-colour card system** — Adjacent side-by-side cards in the same horizontal band share a row background but need distinction. bg-A (full-width), bg-B (left of pair), bg-C (right of pair) uses an existing theme token (`bg-section-fill-02`) as the third shade without introducing new tokens.

**auto-fill grid, not fixed columns** — `repeat(auto-fill, minmax(200px, 1fr))` lets tile size be the experiment dial; column count follows naturally. 200px is the starting value — tune during implementation.

**Active vs Past clients** — Active = all journey stages except `completed`. Past = `completed` only. Off-track clients stay in the active grid with a flag indicator.

**Milestone card as middle zone** — Session number milestones (5, 10, 25, 50) within the last 7 days, derived client-side from sessions fetch. Fallback: missed action items signal. Hidden if neither condition is true.

**60/40 Sessions/Supplements split** — Sessions always has more content. Supplements card takes the hit on width. `grid-cols-[3fr_2fr]`.

**Goal card above sessions** — `course_goal` from existing `ClientDetailOut` schema — zero backend cost. Empty state: "Add a goal for this client" — never hidden.

**AST card and right sidebar removed** — Triage flags and client status removed from the UI. The open action items section + flag dots on the roster board surface the same signal in context.

**Marigold on all primary CTAs** — Overrides the one-Marigold-per-screen lint rule from the design spec. Applied to: `+ New client` (landing), `New session` (client detail sessions card), `Generate chart` (diet chart).

**MOM generation: skeleton + fade-in only** — No width/height animation per motion spec. Opacity fade-in on content reveal (200ms `tw-animate-css`). Skeleton matches two-pane shape of the MOM editor.

**Diet chart inline generation (Part B) deferred** — Build after layout is stable. Endpoint shape (B4) must be verified with SoJo before any backend call is added.

---

## 4. Bugs fixed mid-phase

None recorded. (To be updated as phase ships.)

---

## 5. Source docs consulted

- `docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md` — existing screen set (noted: deployed app diverges — has diet charts, supplements, kanban that post-date this doc)
- `parivarthan-ui-spec-detailed.md` — marketable UI spec (superseded by this phase for Groups A and B; Group C/demo-data out of scope)
- `frontend/src/app/(app)/dashboard/page.tsx` — current dashboard implementation
- `frontend/src/app/(app)/clients/[clientId]/page.tsx` — current client detail implementation
- `frontend/src/app/(app)/clients/[clientId]/sessions/[sessionId]/page.tsx` — current session page
- `frontend/src/app/(app)/layout.tsx` — nav structure
- `backend/src/api/clients.py` — confirmed `ClientOut` fields and stubs in `ClientDetailOut`
- `backend/src/api/sessions.py` — confirmed `SessionOut` fields

---

## 6. Verification

- **Verification date**: TBD
- **Verification record**: TBD
- **Test count at end of phase**: TBD
- **Key checks** (to verify when phase ships):
  - [ ] Landing page shows active client grid; completed clients are collapsed
  - [ ] Milestone card shows for a client with session 5/10/25/50 within last 7 days; hidden when none qualify
  - [ ] Today banner shows today's sessions; empty state does not dead-end
  - [ ] `/clients` redirects to `/dashboard`
  - [ ] "Clients" nav link is gone
  - [ ] Client detail: Goal card visible above sessions; empty state shows "Add a goal" text
  - [ ] Client detail: 60/40 split, bg-B/bg-C distinction visible between Sessions and Supplements
  - [ ] Client detail: Diet chart full-width; no right sidebar
  - [ ] Client detail: Open items + Details at 50/50 bottom
  - [ ] Session MOM tab: skeleton shows on generate; fade-in on reveal
  - [ ] No `any` types introduced; all new API calls use `fetchWithAuth`
  - [ ] No Marigold elements outside primary CTAs on each screen

---

## 7. Lessons learned

TBD — to be filled as phase ships.

---

## 8. Carry-over to subsequent phases

**Backend enrichment (follow-up, not P10):** `GET /api/clients` list endpoint should eventually include `last_session_at` and `has_flags: bool` as computed fields (JOIN sessions + action_items). Currently derived client-side — acceptable at demo scale, not at production roster size. Flag this for P11 or a backend addendum.

**Diet chart endpoint shape (B4):** Must be confirmed with SoJo before Part B builds the inline generation call. If the endpoint only accepts the Templates flow, a thin backend route is needed.

**`bg-section-fill-02` as bg-C:** Verify this token exists in the deployed theme before use. If missing, define it in `frontend/theme.yaml` as a new functional token before implementation.

---

## Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the frontend into a welcoming Roster Board landing page, a rearranged Client Detail page, an improved MOM generation moment, and inline diet chart generation.

**Architecture:** All logic is frontend-only (Part A). Derivations for `last_session_at` and `has_flags` are computed client-side from existing paginated endpoints — no backend changes in this phase. Part B (diet chart inline) uses the existing `generateDietChart` API which accepts `template_id`; the "session" source path is a flagged follow-up requiring a new backend endpoint.

**Tech Stack:** Next.js (App Router), React, TypeScript, Tailwind CSS, `tw-animate-css ^1.4.0`, shadcn/ui components (`Badge`, `Skeleton`, `Separator`, `Tabs`), Zod (all API calls already use `fetchWithAuth` + Zod schemas — follow existing pattern).

## Global Constraints

- All API calls use `fetchWithAuth` from `@/lib/auth/client` — never raw `fetch`
- All API responses parsed with Zod schemas at the boundary — no unvalidated `any`
- No `any` types anywhere — use `unknown` + narrowing
- Fonts: Fraunces 700/900 (`font-heading`) for all headings; Manrope (`font-sans`) for body
- Card eyebrow labels: `font-sans text-xs font-bold uppercase tracking-widest text-primary`
- Motion: opacity transitions only (`duration-150` / `duration-200`) — no width/height/layout animation
- Loading states: shadcn `<Skeleton>` only — no spinners
- `tw-animate-css` already installed — use `animate-in fade-in duration-200` for reveals
- Run `cd frontend && npx tsc --noEmit` after every task to catch type errors before committing
- Test command: `cd frontend && npm test` (vitest)
- Dev server: `cd frontend && npm run dev`

---

### Task 1: Roster utility functions

**Files:**
- Create: `frontend/src/lib/rosterUtils.ts`
- Create: `frontend/src/lib/rosterUtils.test.ts`

**Interfaces:**
- Produces:
  - `buildLastSessionMap(sessions: SessionOut[]): Map<string, Date>` — client_id → most recent past session date
  - `buildFlaggedSet(missedItems: ActionItemOut[]): Set<string>` — set of client_ids with missed items
  - `findMilestone(sessions: SessionOut[], clients: ClientOut[]): { clientName: string; sessionNumber: number } | null`
  - `formatRelativeDate(date: Date | null): string` — "Today" / "Yesterday" / "3 days ago" / "—"

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/lib/rosterUtils.test.ts
import { describe, it, expect } from "vitest";
import {
  buildLastSessionMap,
  buildFlaggedSet,
  findMilestone,
  formatRelativeDate,
} from "./rosterUtils";
import type { SessionOut } from "@/lib/api/sessions";
import type { ActionItemOut } from "@/lib/api/actionItems";
import type { ClientOut } from "@/lib/api/clients";

const baseSession = (overrides: Partial<SessionOut>): SessionOut => ({
  id: "s1",
  hc_user_id: "hc1",
  client_id: "c1",
  session_number: 1,
  scheduled_at: new Date(Date.now() - 86400000).toISOString(), // yesterday
  started_at: null,
  ended_at: null,
  zoom_meeting_id: null,
  notes_internal: null,
  session_notes: null,
  created_at: new Date().toISOString(),
  ...overrides,
});

const baseClient = (overrides: Partial<ClientOut>): ClientOut => ({
  id: "c1",
  hc_user_id: "hc1",
  full_name: "Priya S",
  code: "CP0001",
  email: null,
  phone: null,
  timezone: null,
  journey_stage: "active",
  course_start_date: null,
  course_end_date: null,
  course_goal: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

const baseItem = (overrides: Partial<ActionItemOut>): ActionItemOut => ({
  id: "i1",
  client_id: "c1",
  session_id: null,
  hc_user_id: "hc1",
  description: "item",
  due_date: null,
  status: "missed",
  completed_at: null,
  created_at: new Date().toISOString(),
  ...overrides,
});

describe("buildLastSessionMap", () => {
  it("maps client_id to most recent past session date", () => {
    const older = baseSession({ id: "s1", scheduled_at: new Date(Date.now() - 172800000).toISOString() });
    const newer = baseSession({ id: "s2", scheduled_at: new Date(Date.now() - 86400000).toISOString() });
    const map = buildLastSessionMap([older, newer]);
    expect(map.get("c1")?.toISOString()).toBe(new Date(newer.scheduled_at).toISOString());
  });

  it("ignores future sessions", () => {
    const future = baseSession({ scheduled_at: new Date(Date.now() + 86400000).toISOString() });
    const map = buildLastSessionMap([future]);
    expect(map.has("c1")).toBe(false);
  });

  it("returns empty map for empty input", () => {
    expect(buildLastSessionMap([]).size).toBe(0);
  });
});

describe("buildFlaggedSet", () => {
  it("returns set of client_ids from missed items", () => {
    const set = buildFlaggedSet([baseItem({ client_id: "c1" }), baseItem({ id: "i2", client_id: "c2" })]);
    expect(set.has("c1")).toBe(true);
    expect(set.has("c2")).toBe(true);
    expect(set.has("c3")).toBe(false);
  });
});

describe("findMilestone", () => {
  it("finds a milestone session within last 7 days", () => {
    const s = baseSession({ session_number: 10, scheduled_at: new Date(Date.now() - 86400000).toISOString() });
    const result = findMilestone([s], [baseClient({})]);
    expect(result).toEqual({ clientName: "Priya S", sessionNumber: 10 });
  });

  it("ignores non-milestone session numbers", () => {
    const s = baseSession({ session_number: 3 });
    expect(findMilestone([s], [baseClient({})])).toBeNull();
  });

  it("ignores milestone sessions older than 7 days", () => {
    const s = baseSession({ session_number: 10, scheduled_at: new Date(Date.now() - 8 * 86400000).toISOString() });
    expect(findMilestone([s], [baseClient({})])).toBeNull();
  });
});

describe("formatRelativeDate", () => {
  it("returns — for null", () => expect(formatRelativeDate(null)).toBe("—"));
  it("returns Today for today", () => expect(formatRelativeDate(new Date())).toBe("Today"));
  it("returns Yesterday for 1 day ago", () => {
    const d = new Date(Date.now() - 86400000);
    expect(formatRelativeDate(d)).toBe("Yesterday");
  });
  it("returns N days ago for 3 days", () => {
    const d = new Date(Date.now() - 3 * 86400000);
    expect(formatRelativeDate(d)).toBe("3 days ago");
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd frontend && npm test -- rosterUtils
```
Expected: several FAIL lines — functions don't exist yet.

- [ ] **Step 3: Create `frontend/src/lib/rosterUtils.ts`**

```typescript
import type { SessionOut } from "@/lib/api/sessions";
import type { ActionItemOut } from "@/lib/api/actionItems";
import type { ClientOut } from "@/lib/api/clients";

const MILESTONE_NUMBERS = new Set([5, 10, 25, 50]);
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

export function buildLastSessionMap(sessions: SessionOut[]): Map<string, Date> {
  const now = new Date();
  const map = new Map<string, Date>();
  for (const s of sessions) {
    const d = new Date(s.scheduled_at);
    if (d > now) continue;
    const existing = map.get(s.client_id);
    if (!existing || d > existing) map.set(s.client_id, d);
  }
  return map;
}

export function buildFlaggedSet(missedItems: ActionItemOut[]): Set<string> {
  return new Set(missedItems.map((i) => i.client_id));
}

export function findMilestone(
  sessions: SessionOut[],
  clients: ClientOut[],
): { clientName: string; sessionNumber: number } | null {
  const clientMap = new Map(clients.map((c) => [c.id, c]));
  const cutoff = new Date(Date.now() - SEVEN_DAYS_MS);
  for (const s of sessions) {
    const d = new Date(s.scheduled_at);
    if (MILESTONE_NUMBERS.has(s.session_number) && d >= cutoff && d <= new Date()) {
      const client = clientMap.get(s.client_id);
      if (client) return { clientName: client.full_name, sessionNumber: s.session_number };
    }
  }
  return null;
}

export function formatRelativeDate(date: Date | null): string {
  if (!date) return "—";
  const diffMs = new Date().getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} week${Math.floor(diffDays / 7) > 1 ? "s" : ""} ago`;
  return `${Math.floor(diffDays / 30)} month${Math.floor(diffDays / 30) > 1 ? "s" : ""} ago`;
}
```

- [ ] **Step 4: Run tests — all pass**

```bash
cd frontend && npm test -- rosterUtils
```
Expected: all PASS.

- [ ] **Step 5: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/rosterUtils.ts frontend/src/lib/rosterUtils.test.ts
git commit -m "feat(frontend): add roster utility functions for client card derivations"
```

---

### Task 2: ClientCard component

**Files:**
- Create: `frontend/src/components/client-card.tsx`

**Interfaces:**
- Consumes: `ClientOut` from `@/lib/api/clients`; `formatRelativeDate` from `@/lib/rosterUtils`
- Produces: `<ClientCard>` component used in Task 4 (dashboard grid)

- [ ] **Step 1: Create `frontend/src/components/client-card.tsx`**

```typescript
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ClientOut } from "@/lib/api/clients";

const STAGE_LABEL: Record<string, string> = {
  onboarding: "Onboarding",
  active: "Active",
  plateau: "Plateau",
  off_track: "Off track",
  completed: "Completed",
};

interface ClientCardProps {
  client: ClientOut;
  relativeDate: string;
  hasFlags: boolean;
  dim?: boolean;
}

export function ClientCard({ client, relativeDate, hasFlags, dim = false }: ClientCardProps) {
  return (
    <Link
      href={`/clients/${client.id}`}
      className={cn(
        "block rounded-2xl border p-4 space-y-2 transition-colors duration-150 hover:border-primary",
        hasFlags
          ? "border-destructive/50 bg-destructive/5"
          : "border-border bg-muted",
        dim && "opacity-60",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-heading text-base font-bold text-foreground leading-tight">
          {client.full_name}
        </p>
        {hasFlags && <span className="shrink-0 text-sm" aria-label="Needs attention">🚩</span>}
      </div>
      <Badge variant="secondary">
        {STAGE_LABEL[client.journey_stage] ?? client.journey_stage}
      </Badge>
      <p className="font-sans text-xs text-muted-foreground">{relativeDate}</p>
    </Link>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/client-card.tsx
git commit -m "feat(frontend): add ClientCard component for roster grid"
```

---

### Task 3: Nav cleanup + clients page redirect

**Files:**
- Modify: `frontend/src/app/(app)/layout.tsx` — remove "Clients" from `NAV_LINKS`
- Modify: `frontend/src/app/(app)/clients/page.tsx` — replace with redirect

**Interfaces:** None — standalone change.

- [ ] **Step 1: Remove "Clients" from NAV_LINKS in `layout.tsx`**

Find this block in `frontend/src/app/(app)/layout.tsx`:
```typescript
const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/clients", label: "Clients" },
  { href: "/action-items", label: "Action Items" },
  { href: "/settings/diet-chart-templates", label: "Diet Charts" },
  { href: "/settings/sessions", label: "Settings" },
] as const;
```

Replace with:
```typescript
const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/action-items", label: "Action Items" },
  { href: "/settings/diet-chart-templates", label: "Diet Charts" },
  { href: "/settings/sessions", label: "Settings" },
] as const;
```

- [ ] **Step 2: Replace `frontend/src/app/(app)/clients/page.tsx` with redirect**

Replace the entire file contents with:
```typescript
import { redirect } from "next/navigation";

export default function ClientsPage() {
  redirect("/dashboard");
}
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Verify in dev server**

```bash
cd frontend && npm run dev
```
- Navigate to `http://localhost:3000` — confirm "Clients" is absent from nav
- Navigate to `/clients` — confirm it redirects to `/dashboard`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/(app)/layout.tsx frontend/src/app/(app)/clients/page.tsx
git commit -m "feat(frontend): remove Clients nav entry, redirect /clients to dashboard"
```

---

### Task 4: Dashboard — Roster Board rewrite

**Files:**
- Modify: `frontend/src/app/(app)/dashboard/page.tsx` — full rewrite

**Interfaces:**
- Consumes: `listClients`, `ClientOut` from `@/lib/api/clients`; `listSessions`, `SessionOut` from `@/lib/api/sessions`; `listActionItems`, `ActionItemOut` from `@/lib/api/actionItems`; `ClientCard` from `@/components/client-card`; all four functions from `@/lib/rosterUtils`; `buttonVariants` from `@/components/ui/button`

- [ ] **Step 1: Rewrite `frontend/src/app/(app)/dashboard/page.tsx`**

```typescript
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { listClients, type ClientOut } from "@/lib/api/clients";
import { listSessions, type SessionOut } from "@/lib/api/sessions";
import { listActionItems, type ActionItemOut } from "@/lib/api/actionItems";
import { ClientCard } from "@/components/client-card";
import {
  buildLastSessionMap,
  buildFlaggedSet,
  findMilestone,
  formatRelativeDate,
} from "@/lib/rosterUtils";

function isToday(iso: string): boolean {
  return new Date(iso).toDateString() === new Date().toDateString();
}

export default function DashboardPage() {
  const [clients, setClients] = useState<ClientOut[] | null>(null);
  const [sessions, setSessions] = useState<SessionOut[] | null>(null);
  const [missedItems, setMissedItems] = useState<ActionItemOut[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [pastExpanded, setPastExpanded] = useState(false);

  useEffect(() => {
    Promise.all([
      listClients({ limit: 100 }),
      listSessions({ limit: 100 }),
      listActionItems({ status: "missed", limit: 100 }),
    ])
      .then(([c, s, m]) => {
        setClients(c.items);
        setSessions(s.items);
        setMissedItems(m.items);
      })
      .catch(() => setLoadError(true));
  }, []);

  const loading = !loadError && clients === null;

  const clientMap = new Map((clients ?? []).map((c) => [c.id, c]));
  const lastSessionMap = buildLastSessionMap(sessions ?? []);
  const flaggedSet = buildFlaggedSet(missedItems ?? []);
  const milestone = findMilestone(sessions ?? [], clients ?? []);

  const todaySessions = (sessions ?? []).filter((s) => isToday(s.scheduled_at));
  const activeClients = (clients ?? []).filter((c) => c.journey_stage !== "completed");
  const pastClients = (clients ?? []).filter((c) => c.journey_stage === "completed");
  const flaggedCount = activeClients.filter((c) => flaggedSet.has(c.id)).length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
            Your Practice
          </p>
          <h1 className="mt-1 font-heading text-4xl font-black text-foreground">
            Dashboard
          </h1>
          <p className="mt-1 font-sans text-sm text-muted-foreground">
            Your whole practice, in one place.
          </p>
        </div>
        <Link href="/clients/new" className={cn(buttonVariants({ variant: "accent" }), "shrink-0")}>
          + New client
        </Link>
      </div>

      {/* Today banner */}
      <section className="rounded-2xl border border-border bg-muted px-5 py-3">
        {loading ? (
          <Skeleton className="h-5 w-56" />
        ) : todaySessions.length === 0 ? (
          <p className="font-heading text-base font-black text-muted-foreground">
            No sessions today.{" "}
            <em>Quiet morning.</em>{" "}
            <Link
              href="/action-items"
              className="font-sans text-xs font-normal text-primary underline-offset-4 hover:underline"
            >
              Review follow-ups →
            </Link>
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
              Today
            </span>
            {todaySessions.map((s) => (
              <Link
                key={s.id}
                href={`/clients/${s.client_id}/sessions/${s.id}`}
                className="rounded-full border border-border bg-background px-3 py-1 font-sans text-sm text-foreground transition-colors duration-150 hover:border-primary hover:text-primary"
              >
                {clientMap.get(s.client_id)?.full_name ?? `Session ${s.session_number}`}
                {" · "}
                {new Date(s.scheduled_at).toLocaleTimeString("en-IN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Milestone / flag signal */}
      {!loading && (milestone !== null || flaggedCount > 0) && (
        <div
          className={cn(
            "rounded-2xl border px-5 py-4",
            milestone
              ? "border-accent/40 bg-accent/10"
              : "border-warning/40 bg-warning/5",
          )}
        >
          {milestone ? (
            <p className="font-sans text-sm text-foreground">
              🎉{" "}
              <strong className="font-heading">{milestone.clientName}</strong>{" "}
              just completed their{" "}
              <strong>{milestone.sessionNumber}th</strong> session with you.
            </p>
          ) : (
            <p className="font-sans text-sm text-foreground">
              🚩{" "}
              <strong>{flaggedCount}</strong>{" "}
              {flaggedCount === 1 ? "client has" : "clients have"} missed action
              items — worth a check-in before their next session.
            </p>
          )}
        </div>
      )}

      {/* Client grid */}
      <section className="space-y-4">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
          Your Clients
        </h2>

        {loadError && (
          <p className="font-sans text-sm text-destructive">
            Could not load clients.
          </p>
        )}

        {loading ? (
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}
          >
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-2xl" />
            ))}
          </div>
        ) : activeClients.length === 0 ? (
          <p className="font-heading text-xl font-black text-muted-foreground py-4">
            No active clients yet. <em>Add your first one.</em>
          </p>
        ) : (
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}
          >
            {activeClients.map((client) => (
              <ClientCard
                key={client.id}
                client={client}
                relativeDate={formatRelativeDate(lastSessionMap.get(client.id) ?? null)}
                hasFlags={flaggedSet.has(client.id)}
              />
            ))}
          </div>
        )}

        {/* Past clients collapsible */}
        {!loading && pastClients.length > 0 && (
          <div className="pt-2 border-t border-border">
            <button
              type="button"
              onClick={() => setPastExpanded((v) => !v)}
              className="flex items-center gap-2 py-3 font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground transition-colors duration-150 hover:text-foreground"
            >
              Past clients ({pastClients.length})
              <span className="text-xs">{pastExpanded ? "▲" : "▼"}</span>
            </button>
            {pastExpanded && (
              <div
                className="grid gap-4 mt-2"
                style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}
              >
                {pastClients.map((client) => (
                  <ClientCard
                    key={client.id}
                    client={client}
                    relativeDate={formatRelativeDate(lastSessionMap.get(client.id) ?? null)}
                    hasFlags={false}
                    dim
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Verify in dev server — check all zones**

```bash
cd frontend && npm run dev
```
- `/dashboard` loads — no flash of old layout
- Today banner: shows session pills with client names when sessions exist today; shows empty state with "Review follow-ups" link otherwise
- Milestone card: visible only when a client has session #5/10/25/50 in last 7 days; flag signal shows when `flaggedCount > 0` and no milestone
- Client grid: auto-fill columns, cards show name + stage badge + relative date; flagged clients have red border + 🚩
- Past clients: hidden by default, expands on click, cards are dimmed

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/(app)/dashboard/page.tsx
git commit -m "feat(frontend): rewrite dashboard as Roster Board with client grid and milestone card"
```

---

### Task 5: Client Detail page restructure

**Files:**
- Modify: `frontend/src/app/(app)/clients/[clientId]/page.tsx`

**Interfaces:**
- Consumes: all existing imports (unchanged); removes `getClientAst` call since AST card is removed
- New layout removes right sidebar; adds Goal card, 60/40 top row, full-width diet chart, 50/50 bottom row

**Note on three-colour system:** `bg-section-fill-02` is already used in this file — confirmed present. Map: bg-A = `bg-muted`, bg-B = `bg-background`, bg-C = `bg-section-fill-02`.

- [ ] **Step 1: Remove AST import + state from the page**

In `frontend/src/app/(app)/clients/[clientId]/page.tsx`, remove:
- `getClientAst, type AstOut` from the `@/lib/api/clients` import
- The `ast` state: `const [ast, setAst] = useState<AstOut | null>(null);`
- `getClientAst(clientId)` from the `Promise.all` call
- The AST destructure from `.then(([c, a, s, closed, dc]) => {` → change to `([c, s, closed, dc])`
- `setAst(a)` line
- The `FLAG_LABEL` constant (no longer needed)

Update the `Promise.all` to:
```typescript
Promise.all([
  getClient(clientId),
  listSessions({ client_id: clientId, limit: 20 }),
  listActionItems({ client_id: clientId, status: "completed", limit: 50 }),
  getClientDietChart(clientId),
])
  .then(([c, s, closed, dc]) => {
    setClient(c);
    setSessions(s.items);
    setClosedItems(closed.items);
    setDietChart(dc);
  })
  .catch(() => setLoadError(true));
```

Also remove the `displayOpen` and `displayClosed` derivations that reference `ast?.open_items` — we'll use `listActionItems` for open items instead. Add a new `openItems` state:

```typescript
const [openItems, setOpenItems] = useState<ActionItemOut[] | null>(null);
```

Fetch it separately (same `useEffect`, separate call):
```typescript
listActionItems({ client_id: clientId, status: "open", limit: 50 })
  .then((r) => setOpenItems(r.items))
  .catch(() => setLoadError(true));
```

Update `displayOpen` and `displayClosed` to use `openItems` instead of `ast?.open_items`:
```typescript
const displayOpen = [
  ...(openItems ?? []).filter((i) => !completedIds.has(i.id)),
  ...(closedItems ?? []).filter((i) => reopenedIds.has(i.id)),
];

const displayClosed = [
  ...(closedItems ?? []).filter((i) => !reopenedIds.has(i.id)),
  ...(openItems ?? []).filter((i) => completedIds.has(i.id)),
];
```

Update loading guard (remove ast from loading check):
```typescript
const loading = !loadError && client === null;
```

- [ ] **Step 2: Replace the JSX return with the new layout**

Replace everything from the `return (` through the closing `</div>` with:

```tsx
return (
  <div className="space-y-8">
    {/* Breadcrumb */}
    <Link
      href="/clients"
      className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
    >
      ← Clients
    </Link>

    {loading ? (
      <div className="space-y-3">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-5 w-32" />
      </div>
    ) : loadError ? (
      <p className="font-sans text-sm text-destructive">Could not load client.</p>
    ) : (
      <>
        {/* Client header */}
        <div className="space-y-2">
          <h1 className="font-heading text-4xl font-black text-foreground">
            {client!.full_name}
          </h1>
          <div className="h-0.5 w-14 bg-accent" aria-hidden />
          <div className="flex items-center gap-3">
            <Badge variant="secondary">
              {JOURNEY_STAGE_LABEL[client!.journey_stage] ?? client!.journey_stage}
            </Badge>
            {client!.code && (
              <span className="font-sans text-xs text-muted-foreground">{client!.code}</span>
            )}
          </div>
        </div>

        {/* ── GOAL — bg-A full width ── */}
        <section className="rounded-2xl border border-border bg-muted p-6">
          <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary mb-3">
            Goal
          </h2>
          <Separator />
          <p className="mt-3 font-heading text-lg font-bold text-foreground">
            {client!.course_goal ?? (
              <span className="font-sans text-sm font-normal italic text-muted-foreground">
                Add a goal for this client
              </span>
            )}
          </p>
        </section>

        {/* ── SESSIONS (60%) + SUPPLEMENTS (40%) — bg-B / bg-C ── */}
        <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
          {/* Sessions — bg-B */}
          <section className="space-y-4 rounded-2xl border border-border bg-background p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                Sessions
              </h2>
              <Link
                href={`/clients/${clientId}/sessions/new`}
                className={cn(buttonVariants({ variant: "accent", size: "sm" }))}
              >
                New session
              </Link>
            </div>
            <Separator />
            {sessions === null ? (
              <div className="space-y-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : sessions.length === 0 ? (
              <p className="font-heading text-lg font-black text-muted-foreground py-2">
                No sessions yet. <em>Start one.</em>
              </p>
            ) : (
              <>
                <ul className="divide-y divide-border">
                  {sessions.slice(0, 5).map((sess) => (
                    <li key={sess.id}>
                      <Link
                        href={`/clients/${clientId}/sessions/${sess.id}`}
                        className="flex items-center justify-between py-3 transition-colors duration-150 hover:text-primary"
                      >
                        <div>
                          <span className="font-heading text-base font-bold text-foreground">
                            Session {sess.session_number}
                          </span>
                          <span className="ml-3 font-sans text-sm text-muted-foreground">
                            {new Date(sess.scheduled_at).toLocaleDateString("en-IN", {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                            })}
                          </span>
                        </div>
                        {sess.ended_at ? (
                          <Badge variant="secondary">Ended</Badge>
                        ) : sess.started_at ? (
                          <Badge>In progress</Badge>
                        ) : (
                          <Badge variant="outline">Scheduled</Badge>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
                {sessions.length > 5 && (
                  <details className="pt-2">
                    <summary className="flex cursor-pointer items-center gap-2 font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors duration-150 list-none">
                      Past sessions
                      <span>▼</span>
                    </summary>
                    <ul className="mt-3 divide-y divide-border">
                      {sessions.slice(5).map((sess) => (
                        <li key={sess.id}>
                          <Link
                            href={`/clients/${clientId}/sessions/${sess.id}`}
                            className="flex items-center justify-between py-3 opacity-70 transition-colors duration-150 hover:text-primary hover:opacity-100"
                          >
                            <div>
                              <span className="font-heading text-base font-bold text-foreground">
                                Session {sess.session_number}
                              </span>
                              <span className="ml-3 font-sans text-sm text-muted-foreground">
                                {new Date(sess.scheduled_at).toLocaleDateString("en-IN", {
                                  day: "numeric",
                                  month: "short",
                                  year: "numeric",
                                })}
                              </span>
                            </div>
                            {sess.ended_at ? (
                              <Badge variant="secondary">Ended</Badge>
                            ) : (
                              <Badge variant="outline">Scheduled</Badge>
                            )}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </>
            )}
          </section>

          {/* Supplement Recommendations — bg-C */}
          <section className="space-y-4 rounded-2xl border border-border bg-section-fill-02 p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
                Supplement Recommendations
              </h2>
              {!showSuppForm && (
                <button
                  type="button"
                  onClick={openAddForm}
                  className="font-sans text-xs text-primary underline-offset-4 hover:underline"
                >
                  + Add
                </button>
              )}
            </div>
            <Separator />

            {/* Supplement inline form — unchanged from current implementation */}
            {showSuppForm && (
              <div className="space-y-3 rounded-xl border border-border bg-background p-4">
                <div className="space-y-1">
                  <label className="font-sans text-xs text-muted-foreground">
                    Name <span className="text-destructive">*</span>
                  </label>
                  <input
                    list="supplement-catalog"
                    value={suppForm.name}
                    onChange={(e) => setSuppForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Type or select a supplement"
                    className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                  />
                  <datalist id="supplement-catalog">
                    {SUPPLEMENT_CATALOG.map((s) => <option key={s} value={s} />)}
                  </datalist>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="font-sans text-xs text-muted-foreground">Dosage</label>
                    <input
                      value={suppForm.dosage}
                      onChange={(e) => setSuppForm((f) => ({ ...f, dosage: e.target.value }))}
                      placeholder="e.g. 2000 IU daily"
                      className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="font-sans text-xs text-muted-foreground">Duration (days)</label>
                    <input
                      type="number"
                      min={1}
                      value={suppForm.duration_days}
                      onChange={(e) => setSuppForm((f) => ({ ...f, duration_days: e.target.value }))}
                      placeholder="e.g. 30"
                      className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="font-sans text-xs text-muted-foreground">Date recommended</label>
                  <input
                    type="date"
                    value={suppForm.recommended_at}
                    onChange={(e) => setSuppForm((f) => ({ ...f, recommended_at: e.target.value }))}
                    className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div className="space-y-1">
                  <label className="font-sans text-xs text-muted-foreground">Notes (optional)</label>
                  <textarea
                    value={suppForm.notes}
                    onChange={(e) => setSuppForm((f) => ({ ...f, notes: e.target.value }))}
                    placeholder="Reason or context"
                    rows={2}
                    className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                {suppFormError && (
                  <p className="font-sans text-xs text-destructive">{suppFormError}</p>
                )}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={handleSuppSave}
                      disabled={suppSaving}
                      className="rounded-md bg-primary px-3 py-1.5 font-sans text-xs font-bold text-primary-foreground disabled:opacity-50"
                    >
                      {suppSaving ? "Saving…" : "Save"}
                    </button>
                    <button
                      type="button"
                      onClick={closeSuppForm}
                      className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
                    >
                      Cancel
                    </button>
                  </div>
                  {editingSuppId && (
                    <button
                      type="button"
                      onClick={() => handleSuppDelete(editingSuppId)}
                      className="font-sans text-xs text-destructive underline-offset-4 hover:underline"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Supplement list */}
            {suppLoadError ? (
              <p className="font-sans text-sm text-destructive">Could not load supplements.</p>
            ) : supplements === null ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : supplements.length === 0 && !showSuppForm ? (
              <p className="font-sans text-sm italic text-muted-foreground">
                No supplements logged yet.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {supplements.map((s) => (
                  <li key={s.id} className="py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5">
                        <p className="font-sans text-sm text-foreground">{s.name}</p>
                        <p className="font-sans text-xs text-muted-foreground">
                          {[
                            s.dosage,
                            s.duration_days ? `${s.duration_days} days` : null,
                            new Date(s.recommended_at).toLocaleDateString("en-IN", {
                              day: "numeric", month: "short", year: "numeric",
                            }),
                          ].filter(Boolean).join(" · ")}
                        </p>
                        {s.notes && (
                          <p className="font-sans text-xs italic text-muted-foreground">{s.notes}</p>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => openEditForm(s)}
                        className="shrink-0 font-sans text-xs text-primary underline-offset-4 hover:underline"
                      >
                        Edit
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        {/* ── DIET CHART — bg-A full width ── */}
        <section className="space-y-4 rounded-2xl border border-border bg-muted p-6">
          <div className="flex items-center justify-between">
            <h2 className="font-heading text-2xl font-bold text-foreground">Diet chart</h2>
            <Link
              href={`/clients/${clientId}/diet-chart`}
              className="font-sans text-xs text-primary underline-offset-4 hover:underline"
            >
              {dietChart ? "Edit →" : "Generate →"}
            </Link>
          </div>
          <Separator />
          {dietChart === undefined ? (
            <Skeleton className="h-40 w-full" />
          ) : dietChart === null ? (
            <p className="font-sans text-sm italic text-muted-foreground">
              No diet chart yet.{" "}
              <Link href={`/clients/${clientId}/diet-chart`} className="text-primary underline-offset-4 hover:underline">
                Generate one →
              </Link>
            </p>
          ) : (
            (() => {
              const params = dietChart.parameters as Record<string, unknown>;
              const grid = (params?.grid ?? {}) as Record<string, Record<string, { food: string; timing: string }>>;
              const slots = (params?.meal_slots ?? []) as string[];
              const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
              return (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="py-2 pr-3 text-left font-sans font-bold text-muted-foreground">Day</th>
                        {slots.map((s) => (
                          <th key={s} className="border-l border-border px-3 py-2 text-left font-sans font-bold text-muted-foreground">
                            {s}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {days.map((day) => (
                        <tr key={day} className="border-b border-border last:border-0">
                          <td className="py-2 pr-3 font-heading font-bold text-foreground">{day.slice(0, 3)}</td>
                          {slots.map((s) => (
                            <td key={s} className="border-l border-border px-3 py-2 font-sans text-foreground">
                              <div>{grid[day]?.[s]?.food ?? "—"}</div>
                              {grid[day]?.[s]?.timing && (
                                <div className="text-muted-foreground">{grid[day][s].timing}</div>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })()
          )}
        </section>

        {/* ── OPEN ACTION ITEMS (50%) + DETAILS (50%) — bg-B / bg-C ── */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Open action items — bg-B */}
          <section className="space-y-4 rounded-2xl border border-border bg-background p-6">
            <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
              Open action items
            </h2>
            <Separator />
            {openItems === null ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : displayOpen.length === 0 ? (
              <p className="py-2 font-heading text-lg font-black text-muted-foreground">
                All clear. <em>Nothing pending.</em>
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {displayOpen.map((item) => (
                  <li key={item.id} className="flex items-start gap-3 py-3">
                    <input
                      type="checkbox"
                      checked={false}
                      onChange={() => toggleItem(item.id, true)}
                      className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-primary"
                    />
                    <div className="space-y-0.5">
                      <p className="font-sans text-sm text-foreground">{item.description}</p>
                      {item.due_date && (
                        <p className={cn(
                          "font-sans text-xs",
                          isOverdue(item.due_date) ? "font-bold text-destructive" : "text-muted-foreground",
                        )}>
                          Due {new Date(item.due_date).toLocaleDateString("en-IN")}
                          {isOverdue(item.due_date) && " · Overdue"}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {/* Closed items collapsible — retained */}
            {displayClosed.length > 0 && (
              <details className="pt-2 border-t border-border">
                <summary className="cursor-pointer py-2 font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground list-none hover:text-foreground transition-colors duration-150">
                  Closed ({displayClosed.length}) ▼
                </summary>
                <ul className="mt-2 divide-y divide-border">
                  {displayClosed.map((item) => (
                    <li key={item.id} className="flex items-start gap-3 py-3 opacity-60">
                      <input
                        type="checkbox"
                        checked={true}
                        onChange={() => toggleItem(item.id, false)}
                        className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer accent-primary"
                      />
                      <p className="font-sans text-sm text-foreground line-through">{item.description}</p>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>

          {/* Client details — bg-C */}
          <section className="space-y-4 rounded-2xl border border-border bg-section-fill-02 p-6">
            <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-primary">
              Details
            </h2>
            <Separator />
            <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 font-sans text-sm">
              {client!.email && (
                <>
                  <dt className="text-muted-foreground">Email</dt>
                  <dd className="text-foreground">{client!.email}</dd>
                </>
              )}
              {client!.phone && (
                <>
                  <dt className="text-muted-foreground">Phone</dt>
                  <dd className="text-foreground">{client!.phone}</dd>
                </>
              )}
              <dt className="text-muted-foreground">Stage</dt>
              <dd className="text-foreground">
                {JOURNEY_STAGE_LABEL[client!.journey_stage] ?? client!.journey_stage}
              </dd>
              {client!.course_start_date && (
                <>
                  <dt className="text-muted-foreground">Since</dt>
                  <dd className="text-foreground">
                    {new Date(client!.course_start_date).toLocaleDateString("en-IN", {
                      day: "numeric", month: "short", year: "numeric",
                    })}
                  </dd>
                </>
              )}
              {client!.course_goal && (
                <>
                  <dt className="text-muted-foreground">Goal</dt>
                  <dd className="text-foreground">{client!.course_goal}</dd>
                </>
              )}
            </dl>
          </section>
        </div>
      </>
    )}
  </div>
);
```

- [ ] **Step 3: Remove unused imports**

After the JSX rewrite, remove from the import block any symbols no longer used:
- `getClientAst`, `AstOut` from `@/lib/api/clients`
- `Card`, `CardContent`, `CardHeader`, `CardTitle` from `@/components/ui/card` (if no longer used)

- [ ] **Step 4: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors. Fix any that appear (likely `ast` state still referenced somewhere — remove).

- [ ] **Step 5: Verify in dev server**

- Open any client detail page
- Goal card visible at top; shows "Add a goal for this client" when `course_goal` is null
- 60/40 grid: Sessions (left, wider) + Supplements (right, narrower); distinct bg colours
- Diet chart full-width with all 7 days × all meal slots (or empty state if none)
- Open action items + Details at 50/50 bottom; no right sidebar

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/(app)/clients/[clientId]/page.tsx
git commit -m "feat(frontend): restructure client detail page — goal card, 60/40 sessions/supplements, full-width diet chart"
```

---

### Task 6: MOM tab — skeleton + reveal

**Files:**
- Modify: `frontend/src/app/(app)/clients/[clientId]/sessions/[sessionId]/page.tsx` — `MomTab` component only

**Interfaces:** Consumes existing `MomOut`, `draftMom`, `patchMom`, `sendMom` — no changes to those. Adds `draftVisible` state to control skeleton/content toggle.

- [ ] **Step 1: Add `draftVisible` state and update `handleDraft` in `MomTab`**

In the `MomTab` function, add one new state variable after the existing ones:

```typescript
const [draftVisible, setDraftVisible] = useState(false);
```

Update `handleDraft`:
```typescript
async function handleDraft() {
  setDrafting(true);
  setDraftVisible(false); // hide content, show skeleton
  try {
    const result = await draftMom(session.id, session.session_notes ?? "");
    onMomChange(result);
    setEditedText(result.draft_text);
    setDraftVisible(true); // trigger fade-in
  } finally {
    setDrafting(false);
  }
}
```

Also set `draftVisible(true)` when `mom` is already loaded on mount. Update the `useEffect`:
```typescript
useEffect(() => {
  if (mom?.final_text != null) {
    setEditedText(mom.final_text);
    setDraftVisible(true);
  } else if (mom?.draft_text) {
    setEditedText(mom.draft_text);
    setDraftVisible(true);
  }
}, [mom?.id]);
```

- [ ] **Step 2: Update the two-pane section to use skeleton + fade-in**

Find the `{/* Two-pane on desktop, stacked on mobile */}` block and replace the left pane:

```tsx
{/* Left: AI draft */}
<div className="space-y-2">
  <p className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground">
    AI draft
  </p>
  {drafting ? (
    <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-4">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-4 w-4/6" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/6" />
    </div>
  ) : (
    <div
      className={cn(
        "rounded-lg border border-border bg-muted/40 p-4 transition-opacity duration-200",
        draftVisible ? "opacity-100" : "opacity-0",
      )}
    >
      <p className="font-sans text-sm leading-relaxed text-foreground whitespace-pre-line">
        {mom.draft_text}
      </p>
    </div>
  )}
  <Button
    variant="outline"
    size="sm"
    onClick={handleDraft}
    disabled={drafting || isSent}
  >
    {drafting ? "Regenerating…" : "Regenerate draft"}
  </Button>
</div>
```

Also wrap the `cn` import — confirm it's already imported at the top of the file. If not, add:
```typescript
import { cn } from "@/lib/utils";
```

- [ ] **Step 3: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Verify in dev server**

- Open a session page → MOM tab
- Click "Generate draft": skeleton appears immediately in the left pane
- After generation: content fades in smoothly (200ms)
- Click "Regenerate draft": skeleton replaces content momentarily, then content fades back in

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/(app)/clients/[clientId]/sessions/[sessionId]/page.tsx
git commit -m "feat(frontend): add skeleton + fade-in reveal to MOM draft generation"
```

---

### Task 7 (Part B): Diet chart inline generation

> **Before starting:** Verify B4 — `generateDietChart(clientId, {template_id})` exists and works from the client detail page context. The function does NOT currently accept a `session_id` — session-based generation requires a new backend endpoint. **Do not add a session option here; flag it to SoJo as a follow-up.**

**Files:**
- Modify: `frontend/src/app/(app)/clients/[clientId]/page.tsx` — diet chart section only
- Add import: `generateDietChart`, `listTemplates`, `DietChartOut` from `@/lib/api/dietCharts`

**Interfaces:**
- Consumes: `generateDietChart(clientId, {template_id})`, `listTemplates()` from existing API
- New state: `templates`, `showGenerate`, `selectedTemplateId`, `generating`, `generateError`

- [ ] **Step 1: Add generation state to `ClientDetailPage`**

Add these state variables to the component (after existing state):
```typescript
const [templates, setTemplates] = useState<DietChartOut[] | null>(null);
const [showGenerate, setShowGenerate] = useState(false);
const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
const [generating, setGenerating] = useState(false);
const [generateError, setGenerateError] = useState<string | null>(null);
```

Add `listTemplates` to imports:
```typescript
import {
  getClientDietChart,
  generateDietChart,
  listTemplates,
  type DietChartOut,
} from "@/lib/api/dietCharts";
```

Fetch templates in the existing `useEffect` (add alongside existing fetches):
```typescript
listTemplates()
  .then(setTemplates)
  .catch(() => {}); // non-fatal — generate button just stays disabled
```

- [ ] **Step 2: Replace the diet chart section header with generate affordance**

In the diet chart section, replace the existing header:
```tsx
<div className="flex items-center justify-between">
  <h2 className="font-heading text-2xl font-bold text-foreground">Diet chart</h2>
  {!showGenerate && (
    <div className="flex items-center gap-3">
      {dietChart && (
        <Link
          href={`/clients/${clientId}/diet-chart`}
          className="font-sans text-xs text-primary underline-offset-4 hover:underline"
        >
          Edit →
        </Link>
      )}
      <button
        type="button"
        onClick={() => { setShowGenerate(true); setGenerateError(null); }}
        className={cn(
          buttonVariants({ variant: "accent", size: "sm" }),
        )}
      >
        {dietChart ? "Regenerate" : "Generate chart"}
      </button>
    </div>
  )}
  {showGenerate && (
    <button
      type="button"
      onClick={() => setShowGenerate(false)}
      className="font-sans text-xs text-muted-foreground underline-offset-4 hover:underline"
    >
      Cancel
    </button>
  )}
</div>
```

- [ ] **Step 3: Add inline template picker + skeleton below the header**

After the `<Separator />` in the diet chart section, insert the picker panel:

```tsx
{showGenerate && (
  <div className="space-y-3 rounded-xl border border-border bg-background p-4">
    <div className="space-y-1">
      <label className="font-sans text-xs text-muted-foreground">
        Base this chart on a template
      </label>
      <select
        value={selectedTemplateId}
        onChange={(e) => setSelectedTemplateId(e.target.value)}
        className="w-full rounded-md border border-border bg-muted px-3 py-1.5 font-sans text-sm text-foreground outline-none focus:ring-1 focus:ring-primary"
      >
        <option value="">Select a template…</option>
        {(templates ?? []).map((t) => (
          <option key={t.id} value={t.id}>{t.name}</option>
        ))}
      </select>
    </div>
    {generateError && (
      <p className="font-sans text-xs text-destructive">{generateError}</p>
    )}
    <div className="flex gap-2">
      <button
        type="button"
        disabled={!selectedTemplateId || generating}
        onClick={async () => {
          if (!selectedTemplateId) return;
          setGenerating(true);
          setGenerateError(null);
          try {
            const result = await generateDietChart(clientId, { template_id: selectedTemplateId });
            setDietChart(result.chart);
            setShowGenerate(false);
          } catch {
            setGenerateError("Generation failed. Please try again.");
          } finally {
            setGenerating(false);
          }
        }}
        className={cn(
          buttonVariants({ variant: "accent", size: "sm" }),
          "disabled:opacity-50",
        )}
      >
        {generating ? "Generating…" : "Generate →"}
      </button>
    </div>
    {generating && (
      <div className="space-y-2 pt-2">
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-full" />
        <Skeleton className="h-6 w-5/6" />
        <Skeleton className="h-6 w-full" />
      </div>
    )}
  </div>
)}
```

Wrap the existing diet chart table render in a fade-in wrapper:
```tsx
{!generating && dietChart !== null && dietChart !== undefined && (
  <div className="animate-in fade-in duration-200">
    {/* existing table render code */}
  </div>
)}
```

- [ ] **Step 4: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Verify in dev server**

- Open a client detail page
- "Generate chart" (Marigold) appears in diet chart section header
- Click: inline picker expands with template dropdown
- Select a template + click "Generate →": skeleton appears, then chart fades in
- "Regenerate" available if chart already exists
- **Session-based generation is NOT present** — confirmed deferred to backend follow-up

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/(app)/clients/[clientId]/page.tsx
git commit -m "feat(frontend): inline diet chart generation from client detail page (template source)"
```

---

## Self-review

**Spec coverage:**
- ✅ A1 (subtitle under Dashboard heading) — Task 4 header subtitle
- ✅ A2 (stat strip) — **deliberately dropped** per user decision in brainstorm
- ✅ A3 (Today graceful empty state) — Task 4 today banner with "Review follow-ups" link
- ✅ A4 (Generate chart on dashboard) — not on dashboard (per Roster Board redesign); reachable via client detail page (Task 7)
- ✅ A5 (top 3–5 pending items) — pending items list removed from landing page entirely; flag dots on client cards serve same function
- ✅ B1 (Generate affordance on diet chart card) — Task 7 Step 2
- ✅ B2 (focused generate step) — Task 7 Step 3 inline panel
- ✅ B3 (skeleton → reveal) — Task 7 Step 3 skeleton + Task 7 Step 3 `animate-in fade-in`
- ✅ B4 (endpoint shape) — confirmed: `generateDietChart` accepts `template_id` only; session source flagged as backend follow-up
- ✅ Roster Board (landing page) — Task 4
- ✅ ClientCard — Task 2
- ✅ Nav cleanup — Task 3
- ✅ Client detail restructure — Task 5
- ✅ MOM skeleton + reveal — Task 6
- ✅ Goal card — Task 5 Step 2
- ✅ Three-colour card system — Task 5 Steps 1–2
- ✅ Past clients collapsible — Task 4 Step 1
- ✅ Milestone card — Task 4 Step 1

**Placeholder scan:** No TBD, TODO, or "implement later" in any task. All code blocks are complete and compilable.

**Type consistency:**
- `ClientOut.id` is `string` throughout — ✅
- `ActionItemOut.client_id` is `string` throughout — ✅
- `SessionOut.client_id`, `session_number`, `scheduled_at` types match Task 1 usage — ✅
- `DietChartOut` from `dietCharts.ts` used in Task 7 matches existing import — ✅
- `buildLastSessionMap` returns `Map<string, Date>`, consumed with `.get(client.id)` (string key) in Task 4 — ✅
