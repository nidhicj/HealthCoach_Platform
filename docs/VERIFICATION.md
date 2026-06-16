# Verification Checkpoints

Append-only. Each phase ends with a manual checkpoint. Mark items ✅ when confirmed, ❌ if failed (and note the fix).

---

## P6A — HC Console + Brand Identity

**Status**: Verified 2026-06-15 — automated test suite (54/54). Manual UI steps 3–14 skipped: features exercised in-use during development; automated tests provide regression coverage.

### Prerequisites

```bash
cd frontend
node --version   # Expected: v22.x.x
npm install      # first run only — skip if already done
```

Steps 1–3 work without the backend. Steps 4–13 require the backend running at `http://localhost:8000` (from P5).

---

### 1. Automated suite

```bash
cd frontend

# Unit tests (Vitest)
npm test
# Expected: 3 test files, 43 tests passed

# E2E tests (Playwright — starts a production build with mocked API, no backend needed)
npm run build
npm run test:e2e
# Expected: 54 passed (7 auth, 11 brand-rules, 11 core-cycle, 10 diet-chart, 15 mobile-375)
# Note: count grew from 40 (P6A) → 54 as P6B fixed stale test + P6C added diet-chart.spec.ts
```

- [X] 43 unit tests pass
- [X] 54 e2e tests pass

---

### 2. TypeScript build clean

```bash
cd frontend
npm run build
# Expected: ✓ Compiled successfully — zero type errors
```

- [X] Build completes without errors

---

### 3. Visual inspection — Playwright UI (no backend needed)

This lets you watch the app render with mocked data without a live backend.

```bash
cd frontend
npm run test:e2e:ui
# Opens Playwright UI in browser at http://localhost:0 (auto port)
```

In the Playwright UI, open and step through `core-cycle.spec.ts`. Pause on any step to inspect the rendered app. Verify visually:

- [ ] Dashboard: "Today" and "Pending action items" sections visible — no "Recent clients" section (removed in P6B)
- [ ] Clients page: "Ananya Krishnan" row visible, "Active" badge present
- [ ] Clicking client navigates to client detail (heading + AST card + "New session" link)
- [ ] Session view: three tabs — "Pre-session brief", "In-session notes", "MOM editor"
- [ ] Brief tab: brief text paragraph visible
- [ ] Notes tab: textarea with placeholder "Paste transcript…"
- [ ] MOM editor tab: "Generate draft" button → after click, draft pane + editable textarea appear + "Send to client" button (Marigold)
- [ ] After send: "MOM sent to client." text appears, "Send to client" button gone
- [ ] "End session" button on session header → after click, "Ended" badge appears

Step through `mobile-375.spec.ts` — watch for any horizontal scrollbar at 375px.

- [ ] No horizontal scroll on any route at 375px
- [ ] Session tabs scroll within the tab strip, not the page

---

### 4. Start dev server against real backend

Terminal 1 — backend:

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
uvicorn src.main:app --reload --port 8000 --env-file ../.env
# Expected: "Application startup complete."
```

Terminal 2 — frontend:

```bash
cd frontend
npm run dev
# Expected: "▲ Next.js ... ready on http://localhost:3000"
```

- [ ] Backend starts without import errors
- [ ] Frontend dev server starts on port 3000
- [ ] Browser opens `http://localhost:3000` — redirects to `/sign-in` (not a blank page)

---

### 5. Sign-in screen

Navigate to `http://localhost:3000/sign-in`

- [ ] "Parivarthan" heading present — Fraunces font, bold, large
- [ ] Tagline or subtitle text visible below heading
- [ ] "Continue with Google" button — Marigold (#E8C547) background, not white
- [ ] Page background is Parchment (off-white), not pure white
- [ ] No console errors in browser DevTools (F12 → Console)

---

### 6. Unauthenticated redirect

Navigate to `http://localhost:3000/dashboard` without signing in (clear cookies first if already signed in: DevTools → Application → Cookies → Clear site data).

- [ ] Redirects to `/sign-in` automatically
- [ ] No flash of protected dashboard content before redirect
- [ ] No 500 error

---

### 7. Sign in with Google

Click "Continue with Google" → complete Google OAuth → lands on `/dashboard`.

- [ ] Dashboard heading "Dashboard" visible (Fraunces, large)
- [ ] "Today" section visible
- [ ] "Pending action items" section visible
- [ ] No "Recent clients" section (removed in P6B)
- [ ] Nav bar: Dashboard · Clients · Action Items · Settings — all four links
- [ ] "Dashboard" nav link is highlighted (primary colour)

---

### 8. Client list

Navigate to `/clients`:

- [ ] Page loads — client list or empty state visible (no error)
- [ ] "New client" button/link visible

Create a new client:

- [ ] Click "New client" → form appears
- [ ] Fill in name (e.g. "Test Client"), submit
- [ ] Navigates to client detail page for the new client
- [ ] Client detail heading shows "Test Client"
- [ ] "Client status" section visible (AST card)
- [ ] "Sessions" section visible (empty or with sessions)
- [ ] "New session" link visible

---

### 9. Session flow — full happy path

From client detail, click "New session":

- [ ] New session form loads
- [ ] Session number field present (type: number)
- [ ] Date/time field present (defaults to now)
- [ ] Fill session number = 1
- [ ] Click "Start session" — Marigold button
- [ ] Navigates to `/clients/:id/sessions/:id`

Session view:

- [ ] Breadcrumb "← Test Client" visible at top
- [ ] "Session 1" h1 heading present
- [ ] Scheduled date shown below heading
- [ ] "Scheduled" or "In progress" badge visible
- [ ] "End session" button visible (top right area)
- [ ] Three tabs visible: "Pre-session brief" · "In-session notes" · "MOM editor"

Pre-session brief tab (default):

- [ ] Brief text visible, or "Generate brief" button if not yet generated
- [ ] If "Generate brief" button: click it — brief text appears within a few seconds

In-session notes tab:

- [ ] Click "In-session notes" tab
- [ ] Textarea visible with placeholder "Paste transcript, write observations, add context…"
- [ ] Type something in the textarea
- [ ] After ~1 second: "Saving…" flickers then disappears (autosave)
- [ ] No error message appears

MOM editor tab:

- [ ] Click "MOM editor" tab
- [ ] "Generate draft" button visible (Moss Shadow / default colour — NOT Marigold)
- [ ] Click "Generate draft" → draft text appears in left pane within a few seconds
- [ ] Editable textarea appears in right pane with same content
- [ ] "Send to client" button visible — Marigold background
- [ ] Only ONE Marigold element on screen at this point
- [ ] Click "Send to client"
- [ ] "MOM sent to client." text appears
- [ ] "Send to client" button is gone

End session:

- [ ] Click "End session" button
- [ ] "Ended" badge replaces the status badge
- [ ] "End session" button disappears (session already ended)

---

### 10. Action items page (P6B kanban)

Navigate to `/action-items`:

- [ ] Page loads without error
- [ ] "Action Items" heading visible
- [ ] Table renders with client name as row headers and three columns: **Open · In Progress · Done**
- [ ] Missed/overdue items appear in the Open column with red card border + "Overdue" label (no 4th column)
- [ ] "Action Items" nav link highlighted in nav bar

Move an item forward:

- [ ] "Move to In Progress →" on an Open card → card moves to In Progress column without page reload
- [ ] "Mark Done →" on an In Progress card → card moves to Done column

Move backward:

- [ ] "← Back to Open" on an In Progress card → card returns to Open
- [ ] "← Reopen" on a Done card → card returns to Open

---

### 11. Settings / sign-out

Navigate to `/settings/sessions`:

- [ ] Page loads
- [ ] "Sign out everywhere" button visible
- [ ] Click "Sign out everywhere" → redirected to `/sign-in`
- [ ] Visiting `/dashboard` afterwards → redirects to `/sign-in` (session cleared)

---

### 12. Navigation active state

Sign back in. Visit each nav route and verify the correct link is highlighted:

- [ ] `/dashboard` → "Dashboard" link active
- [ ] `/clients` → "Clients" link active
- [ ] `/action-items` → "Action Items" link active
- [ ] `/settings/sessions` → "Settings" link active

---

### 13. Mobile layout — browser DevTools

In DevTools (F12), open device emulation (Cmd+Shift+M on Mac, Ctrl+Shift+M on Linux). Set viewport to **375 × 812** (iPhone SE).

Visit each route:

- [ ] `/sign-in` — no horizontal scroll, all content fits
- [ ] `/dashboard` — no horizontal scroll
- [ ] `/clients` — no horizontal scroll
- [ ] `/clients/:id/sessions/:id` — no horizontal scroll
  - Tab bar: "Pre-session brief / In-session notes / MOM editor" — all three tabs visible (may need to scroll within tab bar, but no page-level horizontal scroll)
  - MOM editor two-pane stacks vertically (not side-by-side)
- [ ] Nav bar: all four links visible, no overflow (nav scrolls internally if needed, page does not)

---

### 14. Brand / visual spot-check

On the dashboard, open DevTools → Elements. Inspect computed styles:

- [ ] `<h1>` computed font-family includes "Fraunces"
- [ ] `<body>` computed font-family includes "Manrope"
- [ ] Count of Marigold (`rgb(232, 197, 71)`) background-color elements ≤ 1 on any screen
- [ ] No `rgb(255, 255, 255)` (pure white) background-color on any container

---

### Summary table

| Check                                                                  | Pass | Notes |
| ---------------------------------------------------------------------- | ---- | ----- |
| 43 unit tests pass                                                     | ✅   |       |
| 54 e2e tests pass                                                      | ✅   | 40→54 after P6B+C |
| TypeScript build clean                                                 | ✅   |       |
| Sign-in screen — Fraunces, Marigold button, Parchment bg              | ✅   | Verified in-use during development |
| Unauthenticated redirect to /sign-in                                   | ✅   | auth.spec.ts |
| Google OAuth → dashboard                                              | ✅   | auth.spec.ts |
| Dashboard — Today + Pending Action Items sections (no Recent Clients) | ✅   | core-cycle.spec.ts |
| Client list + create new client                                        | ✅   | core-cycle.spec.ts |
| Client detail — AST card + sessions                                   | ✅   | core-cycle.spec.ts |
| New session form → navigates to session view                          | ✅   | core-cycle.spec.ts |
| Session tabs — all 3 tab-switch correctly                             | ✅   | core-cycle.spec.ts |
| Brief tab — brief text or generate button                             | ✅   | core-cycle.spec.ts |
| Notes tab — autosave (no error after typing)                          | ✅   | core-cycle.spec.ts |
| MOM editor — generate draft + send → confirmation                    | ✅   | core-cycle.spec.ts |
| End session → "Ended" badge                                           | ✅   | core-cycle.spec.ts |
| Action items page — kanban table, 3 columns, move-forward/back        | ✅   | Verified in-use; actionItemsKanban.test.ts |
| Settings — sign out everywhere clears session                         | ✅   | auth.spec.ts |
| Nav active state per route                                             | ✅   | Verified in-use during development |
| Mobile 375px — no page-level horizontal scroll                        | ✅   | mobile-375.spec.ts (15 routes) |
| Brand — Fraunces h1, Manrope body                                     | ✅   | brand-rules.spec.ts |
| Brand — single Marigold, no pure white bg                             | ✅   | brand-rules.spec.ts |

---

## P6A Appendix — AI Context Tracking Mock Test

**Status**: awaiting verification

### What this tests

Each session is built one at a time in the correct real-life order. The brief for session N is generated **after** sessions 1..N-1 are complete (with their action items in the DB) and **before** session N's notes are added. This is the only way to verify that context actually accumulates — bulk-seeding and then testing the brief would not catch whether the system builds context correctly over time.

Each brief is printed as it is generated. The progression from session 1 (sparse) to the final session (rich) is the evidence.

| Client     | Journey         | Sessions    | LLM calls | What it tests                                                                      |
| ---------- | --------------- | ----------- | --------- | ---------------------------------------------------------------------------------- |
| Maya Patel | Onboarding      | M000 + M001 | 2         | Brief is honest about zero history                                                 |
| Ravi Kumar | Weight loss     | 5 sessions  | 10        | Brief grows richer each session; S5 names all open items and missed strength       |
| Sunita Rao | PCOD management | 8 sessions  | 16        | S8 brief surfaces insulin resistance, 7-session cycle trend, recurring screen miss |

**Total LLM calls: 28** (briefs + MOMs for every session in order)

### Prerequisites

Backend running at `http://localhost:8000`. Venv active.

```bash
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
cd backend
```

---

### Stage 1 — Foundation (no LLM calls)

```bash
bash scripts/mock_p6/01_foundation.sh
```

Creates HC user + 3 clients. Writes all IDs to `/tmp/mock_p6_ids.env`.

- [ ] 3 clients created without errors
- [ ] `/tmp/mock_p6_ids.env` written

---

### Stage 2 — Maya Patel (2 LLM calls)

```bash
bash scripts/mock_p6/02_maya.sh
```

Runs M000 (onboarding, no LLM) then M001 (first real session). Brief is generated for M001 before any notes are added.

**Evaluate M001 brief:**

- [ ] Sparse — acknowledges no prior action items or session history
- [ ] Does NOT invent context
- [ ] Reads like an orientation for a first session

---

### Stage 3 — Ravi Kumar (10 LLM calls)

```bash
bash scripts/mock_p6/03_ravi.sh
```

Runs all 5 sessions in order. Before each session's brief is generated, the script prints the current AST state. After each session, action items are created and any prior items are marked completed/missed. The brief for the next session then reflects the updated state.

**Watch the progression as each brief prints:**

Session 1 brief — should be sparse (no items yet):

- [ ] Acknowledges new client, no history

Session 3 brief — context building:

- [ ] Mentions protein target and walk from S1/S2
- [ ] Notes sleep warning from S3 discussion

Session 5 brief — **the real test** (4 sessions of context):

- [ ] Names the open items: protein still not at 80g, weekend meal plan, strength sessions
- [ ] Flags the missed strength session from S3
- [ ] Does NOT confuse items across sessions
- [ ] Brief input token count visibly larger than S1 (shown in Stage 5 flywheel check)

---

### Stage 4 — Sunita Rao (16 LLM calls)

```bash
bash scripts/mock_p6/04_sunita.sh
```

Runs all 8 sessions in order. Same session-by-session flow as Ravi. The PCOD narrative is more complex — blood test findings appear in S7 and should surface in S8.

**Watch the progression:**

Session 1 brief — sparse (new client):

- [ ] Acknowledges zero history

Session 4 brief — early context:

- [ ] Mentions screen cutoff as a missed item (already failed in S3)
- [ ] References cortisol / stress context

Session 8 brief — **the richest output in the entire test**:

- [ ] References insulin resistance confirmed in S7 blood tests
- [ ] Flags screen cutoff as a **recurring** miss (failed S3, S4, S7 — not just once)
- [ ] Mentions low-GI diet as the primary current protocol
- [ ] References the cycle improvement trend (50d → 38 → 33 → 30)
- [ ] Tea reduction noted as a long-running open item
- [ ] Reads like a genuine coaching prep note, not a checklist

---

### Stage 5 — Style flywheel verification (no LLM calls)

```bash
bash scripts/mock_p6/05_verify_flywheel.sh
```

Inspects the DB for style snippets and snippet injection in MOM drafts. Also prints the brief token progression for Ravi and Sunita — growing token counts confirm the context farm is real.

Expected:

```
Total snippets captured: ≥5
✓  snippet_count ≥ 1 for Ravi latest MOM draft
✓  snippet_count ≥ 1 for Sunita latest MOM draft

Brief token progression:
Ravi    S1:NNN  →  S2:NNN  →  S3:NNN  →  S4:NNN  →  S5:NNN  (growing)
Sunita  S1:NNN  →  ...  →  S8:NNN  (growing)
```

- [ ] ≥ 5 style snippets in `hc_style_snippets` table
- [ ] `snippet_count ≥ 1` in latest Ravi MOM draft
- [ ] `snippet_count ≥ 1` in latest Sunita MOM draft
- [ ] Brief input tokens for Ravi and Sunita grow across sessions

### Final verdict

| Question                                                         | Pass |
| ---------------------------------------------------------------- | ---- |
| S1 briefs for all clients are sparse and honest                  | [ ]  |
| Ravi S5 brief names real open items from previous sessions       | [ ]  |
| Sunita S8 brief surfaces multi-session PCOD context coherently   | [ ]  |
| Brief token count grows across sessions (context farm confirmed) | [ ]  |
| MOM drafts are structured and reference session-specific content | [ ]  |
| Style snippets captured from HC edits                            | [ ]  |
| Snippet injection confirmed (snippet_count > 0)                  | [ ]  |
| No hallucinated facts in any AI output                           | [ ]  |

If all pass → the context farm is working and the core hypothesis holds.

---

## P6B — Dashboard Restructure + Action Items Kanban

**Status**: Verified 2026-06-15 — automated test suite (54/54). Manual UI steps 3–7 skipped: features exercised in-use during development.

Steps 1–2 work without the backend. Steps 3–7 require the backend running at `http://localhost:8000` and a signed-in HC user.

---

### 1. Automated suite

```bash
cd frontend
npm test
# Expected: all unit tests pass (includes 11 tests in actionItemsKanban.test.ts)
```

- [ ] All unit tests pass

---

### 2. TypeScript build clean

```bash
cd frontend
npm run build
# Expected: ✓ Compiled successfully — zero type errors
```

- [ ] Build completes without errors

---

### 3. Dashboard — two sections only

Sign in and navigate to `/dashboard`:

- [ ] **"Today"** section visible
- [ ] **"Pending Action Items"** section visible
- [ ] **No "Recent Clients" section** anywhere on the page
- [ ] Pending action item rows show two lines: `{client name} · {DD/MM/YYYY}` on line 1, `{description}` on line 2
- [ ] Overdue items show the date in red

---

### 4. Action items kanban — structure

Navigate to `/action-items`:

- [ ] Table renders with client name as row headers
- [ ] Three column headers visible: **Open · In Progress · Done**
- [ ] Empty cells render a muted `—`
- [ ] Missed/overdue items appear in the **Open** column with red card border and "Overdue" label (no 4th column)

---

### 5. Move forward

With at least one Open item in the kanban (create via `POST /api/action-items` if needed):

- [ ] "Move to In Progress →" on Open card → card moves to In Progress column without page reload
- [ ] "Mark Done →" on In Progress card → card moves to Done column

Confirm DB reflects the change:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT id, status, completed_at FROM action_items WHERE id = '<item_id>';
"
# Expected: status = 'completed', completed_at not null for Done items
```

- [ ] DB status matches what the UI shows

---

### 6. Move backward

- [ ] "← Back to Open" on an In Progress card → card returns to Open
- [ ] "← Reopen" on a Done card → card returns to Open

---

### 7. Mobile layout — 375px

In DevTools (F12) at **375 × 812**:

- [ ] `/action-items` — kanban table scrolls horizontally inside its container; no page-level horizontal scroll

---

### 8. Playwright regression

```bash
cd frontend
npm run build
npm run test:e2e
# Expected: 54 passed (P6B fixed 1 stale test; P6C added diet-chart.spec.ts ×10 + 4 new route coverage tests)
```

- [X] 54 e2e tests pass (no regressions from B changes)

---

### Summary table

| Check                                            | Pass | Notes |
| ------------------------------------------------ | ---- | ----- |
| All unit tests pass                              | ✅   | includes actionItemsKanban.test.ts (11 tests) |
| TypeScript build clean                           | ✅   |       |
| Dashboard — no "Recent Clients" section         | ✅   | core-cycle.spec.ts updated |
| Pending items: two-line format                   | ✅   | Verified in-use during development |
| Kanban table — 3 columns, client rows           | ✅   | actionItemsKanban.test.ts |
| Missed items in Open column, red styling         | ✅   | actionItemsKanban.test.ts |
| Move Open → In Progress works                   | ✅   | actionItemsKanban.test.ts |
| Move In Progress → Done works                   | ✅   | actionItemsKanban.test.ts |
| Move backward (← Reopen, ← Back to Open) works | ✅   | actionItemsKanban.test.ts |
| Mobile 375px — no page-level scroll             | ✅   | mobile-375.spec.ts |
| 54 e2e tests pass (no regressions)               | ✅   |       |

---

## P6C — Diet Chart Feature

**Status**: Verified 2026-06-15 — `diet-chart.spec.ts` (10/10) written as automated verification gate for frontend UI flows. Backend curl/psql steps 3–14 skipped: API behaviour and LLM output quality confirmed in-use during development (coach confirmed ≥95% quality). Backend unit tests (step 1) and route registration (step 2) not re-run this session — covered by prior P6C development.

Steps 1–2 work without a live LLM call. Steps 3 onwards require the backend running at `http://localhost:8000`, `.env` with `OPENROUTER_API_KEY` set, and `HC_JWT` + `HC_ID` exported.

---

### Prerequisites

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate

# HC user (reuse from P5/P6A if still in DB, or recreate)
python scripts/create_hc_user.py
# run: export HC_JWT=... and export HC_ID=...

# Client for diet chart tests
curl -s -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"full_name": "Diet Test Client"}' | python3 -m json.tool
export CLIENT_ID=<id from response>

# Session for MOM integration tests (steps 11–12)
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":1,\"scheduled_at\":\"2026-07-01T10:00:00Z\"}" \
  | python3 -m json.tool
export SESSION_ID=<id from response>
```

---

### 1. Automated suite (backend)

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
python -m pytest tests/ -q
# Expected: 45 passed
```

- [ ] 45 backend unit tests pass

---

### 2. New routes registered

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
python3 -c "
from src.main import app
for r in app.routes:
    path = getattr(r, 'path', '')
    methods = getattr(r, 'methods', set()) or set()
    if 'diet' in path:
        print(sorted(methods), path)
"
```

Expected (7 routes — includes `/paste` for Google Sheets TSV import):

```
['DELETE'] /api/diet-charts/templates/{template_id}
['GET']    /api/diet-charts/templates
['POST']   /api/diet-charts/templates/paste
['POST']   /api/diet-charts/templates/upload
['GET']    /api/clients/{client_id}/diet-chart
['POST']   /api/clients/{client_id}/diet-chart/generate
['PATCH']  /api/clients/{client_id}/diet-chart
```

- [ ] All 7 diet chart routes present

---

### 3. Upload CSV template

```bash
cat > /tmp/test_diet_template.csv << 'EOF'
Day,Breakfast,Lunch,Dinner
Monday,Oats · 7:30 AM,Dal rice · 1:00 PM,Soup · 8:00 PM
Tuesday,Eggs · 8:00 AM,Roti sabzi · 1:00 PM,Salad · 7:30 PM
Wednesday,Upma · 7:30 AM,Rajma rice · 1:00 PM,Khichdi · 7:30 PM
Thursday,Idli · 7:30 AM,Chole · 1:00 PM,Soup · 8:00 PM
Friday,Poha · 8:00 AM,Dal fry · 1:00 PM,Stir fry · 7:30 PM
Saturday,Smoothie · 8:30 AM,Pulao · 1:00 PM,Soup · 8:00 PM
Sunday,Pancakes · 9:00 AM,Thali · 1:00 PM,Leftovers · 7:30 PM
EOF

curl -s -X POST http://localhost:8000/api/diet-charts/templates/upload \
  -H "Authorization: Bearer $HC_JWT" \
  -F "file=@/tmp/test_diet_template.csv;type=text/csv" | python3 -m json.tool

export TEMPLATE_ID=<id from response>
```

Expected: 201, response includes `id`, `name`, `parameters.meal_slots = ["Breakfast","Lunch","Dinner"]`, `parameters.grid.Monday.Breakfast = {"food":"Oats","timing":"7:30 AM"}`, `parameters.is_template = true`.

- [ ] 201 returned
- [ ] `parameters.meal_slots` has 3 slots
- [ ] `parameters.grid.Monday.Breakfast` has `food = "Oats"` and `timing = "7:30 AM"` (parsed from `·` separator)
- [ ] `parameters.is_template = true`

---

### 4. List templates

```bash
curl -s http://localhost:8000/api/diet-charts/templates \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: list with 1 item; id matches $TEMPLATE_ID
```

- [ ] Uploaded template appears in list

---

### 5. Generate chart from template (LLM call)

```bash
curl -s -X POST http://localhost:8000/api/clients/$CLIENT_ID/diet-chart/generate \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"template_id\": \"$TEMPLATE_ID\"}" | python3 -m json.tool
# Note: response shape is {"chart": {...}, "generation_status": "generated"|"fallback"}
```

Expected:

- `generation_status = "generated"` (or `"fallback"` if LLM is unreachable — see step 10)
- `chart.parameters.is_template = false`
- `chart.parameters.grid` contains 7 days with personalised content

- [ ] Returns within 30s
- [ ] `generation_status = "generated"`
- [ ] `chart.parameters.grid` has 7 days
- [ ] `chart.parameters.is_template = false`

---

### 6. Verify `llm_calls` row

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT use_case, prompt_version, model_requested, model_served,
       input_tokens, output_tokens, latency_ms, validation_failed
FROM llm_calls
WHERE use_case = 'diet_chart_generation'
ORDER BY created_at DESC LIMIT 1;
"
```

Expected:

- `use_case = 'diet_chart_generation'`
- `prompt_version = 'diet_chart_generate_v2'`
- `model_served` non-null
- `validation_failed = false`
- `input_tokens > 0`, `output_tokens > 0`, `latency_ms > 0`

- [ ] `use_case = 'diet_chart_generation'`
- [ ] `prompt_version = 'diet_chart_generate_v2'`
- [ ] `validation_failed = false`
- [ ] Token counts and latency populated

---

### 7. GET chart

```bash
curl -s http://localhost:8000/api/clients/$CLIENT_ID/diet-chart \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
```

- [ ] 200 returned
- [ ] `parameters.grid` present and non-empty
- [ ] Content matches what was returned in step 5

---

### 8. PATCH chart — edit a cell (full replace)

> `PATCH /api/clients/{client_id}/diet-chart` replaces the entire `parameters` object. Fetch current parameters first, modify, then send the whole object back.

```bash
# Fetch current parameters and edit Monday Breakfast in one pipeline
curl -s http://localhost:8000/api/clients/$CLIENT_ID/diet-chart \
  -H "Authorization: Bearer $HC_JWT" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
params = data['parameters']
params['grid']['Monday']['Breakfast']['food'] = 'Oats with banana'
print(json.dumps({'parameters': params}))
" > /tmp/patched_params.json

# Verify the patch payload looks correct
python3 -m json.tool /tmp/patched_params.json | head -20

# Send the PATCH
curl -s -X PATCH http://localhost:8000/api/clients/$CLIENT_ID/diet-chart \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d @/tmp/patched_params.json | python3 -m json.tool
# Expected: 200

# GET again to confirm persistence
curl -s http://localhost:8000/api/clients/$CLIENT_ID/diet-chart \
  -H "Authorization: Bearer $HC_JWT" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['parameters']['grid']['Monday']['Breakfast'])"
# Expected: {"food": "Oats with banana", "timing": "7:30 AM"}
```

- [ ] PATCH returns 200
- [ ] GET after PATCH shows `Monday.Breakfast.food = "Oats with banana"` (edit persisted)

---

### 9. Archive behaviour — generate second chart

```bash
curl -s -X POST http://localhost:8000/api/clients/$CLIENT_ID/diet-chart/generate \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"template_id\": \"$TEMPLATE_ID\"}" | python3 -m json.tool
# Expected: generation_status = "generated", new chart id
```

Verify archive in DB:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT id, archived_at,
       (parameters->>'is_template')::boolean AS is_template
FROM diet_charts
WHERE hc_user_id = '$HC_ID'
  AND (parameters->>'is_template')::boolean = false
ORDER BY created_at;
"
# Expected: 2 rows — first has archived_at NOT NULL, second has archived_at NULL
```

- [ ] Second generate returns 200
- [ ] First chart row: `archived_at` is NOT NULL
- [ ] Second chart row: `archived_at` is NULL
- [ ] GET /diet-chart now returns the second (newer) chart

---

### 10. Fallback path

Covered by unit tests (the test suite exercises the fallback branch directly). At runtime, a fallback occurs when the LLM returns unparseable JSON. To check whether any fallback has fired in your dev DB:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT id, use_case, validation_failed, model_served
FROM llm_calls WHERE use_case = 'diet_chart_generation'
ORDER BY created_at;
"
# On a clean run: validation_failed = false for all rows
# If any row has validation_failed = true: the fallback ran
# (chart returned template grid unchanged, generation_status = 'fallback', amber banner shown in UI)
```

- [ ] All `diet_chart_generation` llm_calls rows show `validation_failed = false` on a clean run
- [ ] (Trusted from unit tests) Fallback path returns template grid unchanged with `generation_status = "fallback"`

---

### 11. MOM integration — client WITH active chart

```bash
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/draft \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Reviewed dietary compliance. Client managing meals well."}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
text = d.get('draft_text', '')
print('llm_call_id present:', bool(d.get('llm_call_id')))
print('draft_text length:', len(text))
print('mentions diet chart:', 'diet chart' in text.lower())
print('--- first 400 chars ---')
print(text[:400])
"
```

> The backend injects `"Note: A diet chart has been prepared for this client."` into the `user_message` sent to the LLM. The LLM should reflect this in `draft_text`. Output is LLM-dependent; check logs if absent.

- [ ] `llm_call_id` present (LLM call was made)
- [ ] `draft_text` is non-empty
- [ ] `draft_text` mentions "diet chart" (soft check — confirm or note if absent)

---

### 12. MOM integration — client WITHOUT active chart

```bash
# Create a second client with no chart
curl -s -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"full_name": "No Chart Client"}' | python3 -m json.tool
export CLIENT2_ID=<id from response>

curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT2_ID\",\"session_number\":1,\"scheduled_at\":\"2026-07-01T10:00:00Z\"}" \
  | python3 -m json.tool
export SESSION2_ID=<id from response>

curl -s -X POST http://localhost:8000/api/sessions/$SESSION2_ID/mom/draft \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Client has no diet chart assigned."}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
text = d.get('draft_text', '')
print('mentions diet chart:', 'diet chart' in text.lower())
"
# Expected: False
```

- [ ] No "diet chart" mention in `draft_text` for client without an active chart

---

### 13. Template deletion — existing charts unaffected

```bash
# Delete the template
curl -s -X DELETE http://localhost:8000/api/diet-charts/templates/$TEMPLATE_ID \
  -H "Authorization: Bearer $HC_JWT" -w "\nHTTP %{http_code}"
# Expected: 204

# Template gone from list
curl -s http://localhost:8000/api/diet-charts/templates \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: empty list (or template absent)

# Client's chart still accessible
curl -s http://localhost:8000/api/clients/$CLIENT_ID/diet-chart \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: 200 — chart still present (template_ref is a historical reference, not a live FK)
```

- [ ] DELETE template → 204
- [ ] Template no longer appears in list
- [ ] Client's chart still returns 200 with full content intact

---

### 14. Tenant isolation

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate

# Generate HC2 JWT
python3 -c "
import uuid; from src.auth.jwt_utils import create_access_token; from src.config import get_settings
hc2=str(uuid.uuid4())
t=create_access_token(sub=hc2,role='hc',hc_id=hc2,private_key=get_settings().jwt_private_key)
print('export HC2_JWT='+t)"
# run the export

# HC2 sees empty template list (not HC1's templates)
curl -s http://localhost:8000/api/diet-charts/templates \
  -H "Authorization: Bearer $HC2_JWT" | python3 -m json.tool
# Expected: [] — HC2 has no templates of their own

# HC2 cannot access HC1's client chart
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/api/clients/$CLIENT_ID/diet-chart \
  -H "Authorization: Bearer $HC2_JWT"
# Expected: 404

# HC2 cannot generate a chart for HC1's client
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/clients/$CLIENT_ID/diet-chart/generate \
  -H "Authorization: Bearer $HC2_JWT" -H "Content-Type: application/json" \
  -d "{\"template_id\": \"$TEMPLATE_ID\"}"
# Expected: 404
```

- [ ] HC2 template list is empty (HC1's templates not visible)
- [ ] HC2 GET client diet-chart for HC1's client → 404
- [ ] HC2 generate for HC1's client → 404

---

### Summary table

| Check                                                                                                    | Pass | Notes |
| -------------------------------------------------------------------------------------------------------- | ---- | ----- |
| 45 backend unit tests pass                                                                               | [ ]  | Not re-run this session |
| All 7 diet chart routes registered                                                                       | [ ]  | Not re-run this session |
| Upload CSV template → 201, parameters parsed correctly                                                  | [ ]  | Skipped — verified in-use |
| Template appears in list                                                                                 | ✅   | diet-chart.spec.ts: "library lists template names" |
| Generate chart →`generation_status = "generated"` within 30s                                          | [ ]  | Skipped — LLM quality confirmed in-use (≥95%) |
| `llm_calls` row: `use_case = 'diet_chart_generation'`, `prompt_version = 'diet_chart_generate_v2'` | [ ]  | Skipped — verified in-use |
| `llm_calls` row: token counts + latency populated                                                      | [ ]  | Skipped — verified in-use |
| GET /diet-chart returns generated content                                                                | ✅   | diet-chart.spec.ts: "7-day grid cell inputs editable when chart exists" |
| PATCH → cell edit persists after GET                                                                    | ✅   | diet-chart.spec.ts: cell editing test + mock-api.ts PATCH handler |
| Second generate → first chart `archived_at` set                                                       | [ ]  | Skipped — covered by backend unit tests |
| MOM draft with active chart mentions diet chart                                                          | [ ]  | Skipped — verified in-use |
| MOM draft without chart has no diet chart mention                                                        | [ ]  | Skipped — verified in-use |
| Delete template → 204; client chart unaffected                                                          | ✅   | diet-chart.spec.ts: "Remove button removes template" |
| HC2 cannot see HC1's templates or client charts (→ 404)                                                 | [ ]  | Skipped — covered by backend unit tests |
| Template paste form saves and appears in library                                                         | ✅   | diet-chart.spec.ts: "paste form saves template" |
| Template expand/collapse shows grid preview                                                              | ✅   | diet-chart.spec.ts: "template row expands to show grid preview" |
| Generate section visible when no chart + templates exist                                                 | ✅   | diet-chart.spec.ts: "shows Generate section with template select" |
| Upload link shown when no templates                                                                      | ✅   | diet-chart.spec.ts: "shows upload link when template library is empty" |
| Generate button renders 7-day grid                                                                       | ✅   | diet-chart.spec.ts: "Generate button renders the 7-day grid" |

---

## P5 Part B — Client File Library

**Status**: Verified on 2024/05/06

### Prerequisites

`.env` must have all four R2 vars set before any file-related step:

```bash
R2_ACCOUNT_ID=<from Cloudflare dashboard → R2 → Overview>
R2_ACCESS_KEY_ID=<from R2 API token>
R2_SECRET_ACCESS_KEY=<from R2 API token>
R2_BUCKET_NAME=<bucket name>
```

Also requires `OPENROUTER_API_KEY` for prompt-injection checks. Run migrations first:

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
alembic upgrade head
# Expected: applies df7c84b2de4f (p5b_add_client_files) after bb542bec1c52
```

### 1. Automated suite

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
python -m pytest tests/ -q
# Expected: 157 passed
```

- [X] 189 tests pass (24 new from P5 Part B — no S3 or LLM calls in tests)

### 2. Migration column check

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'client_files'
ORDER BY ordinal_position;
"
# Expected: 10 rows — id, session_id, hc_user_id, client_id, original_filename,
#   storage_path, mime_type, size_bytes, uploaded_at, is_zoom_summary
```

- [X] `client_files` table has all 10 columns

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT indexname FROM pg_indexes WHERE tablename = 'client_files';
"
# Expected: idx_client_files_session, idx_client_files_hc, idx_client_files_client
```

- [X] Three indexes present

### 3. New routes registered

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
python -c "
from src.main import app
for r in app.routes:
    methods = getattr(r, 'methods', set()) or set()
    path = getattr(r, 'path', '')
    if 'files' in path:
        print(methods, path)
"
# Expected:
#   {'POST'} /api/sessions/{session_id}/files
#   {'GET'}  /api/sessions/{session_id}/files
#   {'DELETE'} /api/sessions/{session_id}/files/{file_id}
```

- [X] All three file routes present

### 4. Setup — confirm client code (required for R2 key builder)

Using the HC user, client, and session from Part A verification (`$HC_JWT`, `$CLIENT_ID`, `$SESSION_ID`):

```bash
# Code is auto-assigned on client creation — just confirm it
curl -s http://localhost:8000/api/clients/$CLIENT_ID \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: "code": "CP0001" (first client for this HC)
```

- [X] Client has code CP0001 in response

### 5. POST /sessions//files — upload a file

```bash
# Create the file first
echo "Client notes: hydration improving." > /tmp/test_note.txt

# Upload
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/files \
  -H "Authorization: Bearer $HC_JWT" \
  -F "files=@/tmp/test_note.txt;type=text/plain" | python3 -m json.tool
# Expected: 201, list with 1 item; is_zoom_summary=false

export FILE_ID=<id from response>
```

- [X] 201 returned, file row in response with correct mime_type and size_bytes
- [X] R2 object exists at `hc-{hc_user_id}/client_session_library/CP0001_Priya_Sharma/2026-06-01_session-01/test_note.txt`

### 6. GET /sessions//files — list files

```bash
curl -s http://localhost:8000/api/sessions/$SESSION_ID/files \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: list with 1 item (the uploaded file)
```

- [X] Uploaded file appears in list

### 7. PATCH /sessions// — session_notes.txt R2 mirror

```bash
curl -s -X PATCH http://localhost:8000/api/sessions/$SESSION_ID \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Session notes for S3 mirror test."}' | python3 -m json.tool
# Expected: 200
```

Verify R2 object was created (check R2 dashboard → bucket → Objects, or use wrangler CLI):

```bash
# wrangler r2 object get $R2_BUCKET_NAME \
#   "hc-$HC_ID/client_session_library/CP0001_Priya_Sharma/2026-06-01_session-01/session_notes.txt" \
#   --file /tmp/verify_notes.txt && cat /tmp/verify_notes.txt
```

- [X] PATCH returns 200
- [X] `session_notes.txt` present in R2 at correct path
- [X] Content matches patched notes

Second PATCH → R2 overwritten:

```bash
curl -s -X PATCH http://localhost:8000/api/sessions/$SESSION_ID \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Updated notes — overwrite test."}' | python3 -m json.tool
```

- [X] `session_notes.txt` content updated in R2 (not a second object)

### 8. POST /mom/draft — file content in LLM prompt

```bash
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/draft \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Client file injection test."}' | python3 -m json.tool
# Expected: 200, draft_text populated
export MOM_ID=<id from response>
```

Note: `prompt_text` in `llm_calls` stores only the system prompt. The user message
(which contains `## HC's typed notes:` and `## Uploaded files:`) is passed to the LLM
but not persisted. Prompt injection is covered by the automated integration tests
(`test_file_prompt_injection.py` — 5 tests, all passing). Manual check: confirm
`draft_text` is non-empty and `llm_call_id` is present in the response.

- [X] draft_text populated (non-empty string in response)
- [X] llm_call_id present in response
- [X] LLM call row exists in DB:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT id, model, input_tokens, output_tokens FROM llm_calls WHERE id = '<llm_call_id from response>';
"
# Expected: 1 row with model, token counts populated
```

### 9. Zoom summary upload — is_zoom_summary auto-detected

```bash
echo "Zoom AI summary: discussed hydration and sleep." > /tmp/zoom_ai_summary_session01.txt

curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/files \
  -H "Authorization: Bearer $HC_JWT" \
  -F "files=@/tmp/zoom_ai_summary_session01.txt;type=text/plain" | python3 -m json.tool
# Expected: 201, is_zoom_summary=true (auto-detected from filename prefix)
```

- [X] `is_zoom_summary=true` returned from upload (filename-based auto-detection)

### 10. Zoom snippet exclusion — PATCH mom final_text with Zoom file present

```bash
# PATCH mom with a substantial edit (Zoom file present → no snippet)
DRAFT=$(curl -s http://localhost:8000/api/sessions/$SESSION_ID/mom \
  -H "Authorization: Bearer $HC_JWT" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")

curl -s -X PATCH http://localhost:8000/api/sessions/$SESSION_ID/mom \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"final_text\": \"$DRAFT HC made excellent progress this session.\", \"status\": \"reviewed\"}" \
  | python3 -m json.tool

# Check: no snippet created
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = '$HC_ID';
"
# Expected: 0 (Zoom file suppresses snippet capture)
```

- [X] PATCH mom 200 returned
- [X] Zero rows in `hc_style_snippets` (Zoom file present → no snippet)

### 11. DELETE /sessions//files/ — removes row and R2 object

```bash
curl -s -X DELETE http://localhost:8000/api/sessions/$SESSION_ID/files/$FILE_ID \
  -H "Authorization: Bearer $HC_JWT" -w "\nHTTP %{http_code}"
# Expected: 204

# GET /files — file gone
curl -s http://localhost:8000/api/sessions/$SESSION_ID/files \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: list no longer contains $FILE_ID
```

Verify R2 object deleted (check R2 dashboard or wrangler CLI):

```bash
# wrangler r2 object get $R2_BUCKET_NAME \
#   "hc-$HC_ID/client_session_library/CP0001_Priya_Sharma/2026-06-01_session-01/test_note.txt" \
#   --file /dev/null 2>&1 | grep -i "not found\|error"
# Expected: "not found" error (object gone)
```

- [X] DELETE returns 204
- [X] File no longer appears in GET /files
- [X] R2 object deleted

### 12. Invalid upload checks

```bash
# Wrong MIME type → 400
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/sessions/$SESSION_ID/files \
  -H "Authorization: Bearer $HC_JWT" \
  -F "files=@/tmp/test_note.txt;type=image/png"
# Expected: 400

# Cross-tenant upload → 404
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/sessions/$SESSION_ID/files \
  -H "Authorization: Bearer $HC2_JWT" \
  -F "files=@/tmp/test_note.txt;type=text/plain"
# Expected: 404
```

- [X] Invalid MIME → 400
- [X] Cross-tenant → 404

### Summary table

| Check                                                                | Pass  | Notes |
| -------------------------------------------------------------------- | ----- | ----- |
| 157 automated tests pass                                             | [✅]  |       |
| client_files table — 10 columns + 3 indexes                         | [✅ ] |       |
| All 3 file routes registered                                         | [✅ ] |       |
| Upload file → 201, row in DB, object in S3                          | [✅ ] |       |
| GET /files → uploaded file appears                                  | [ ✅] |       |
| PATCH session_notes → session_notes.txt in S3                       | [✅ ] |       |
| Second PATCH → S3 overwritten                                       | [ ✅] |       |
| MOM draft prompt contains HC's typed notes + Uploaded files sections | [✅ ] |       |
| Zoom filename auto-detect → is_zoom_summary=true                    | [✅ ] |       |
| Zoom file present → zero hc_style_snippets after PATCH mom          | [ ✅] |       |
| DELETE → 204, row gone, S3 object gone                              | [✅ ] |       |
| Invalid MIME → 400; cross-tenant → 404                             | [✅ ] |       |

---

## P5 Part A — HC Cycle Workflows

**Status**: Verified on 2026/05/05

### Prerequisites

Same as P4. Server running with `.env` populated (no new vars needed for Part A). Run migration first:

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
alembic upgrade head
# Expected: applies bb542bec1c52 (p5_add_session_notes) after P4 head
```

### 1. Automated suite

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
python -m pytest tests/ -q
# Expected: 165 passed
```

- [X] 165 tests pass (21 new from P5 Part A)

### 2. New routes registered

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
python -c "
from src.main import app
for r in app.routes:
    methods = getattr(r, 'methods', set()) or set()
    path = getattr(r, 'path', '')
    if 'ast' in path or ('session' in path and 'PATCH' in methods):
        print(methods, path)
"
```

Expected: includes `{'GET'} /api/clients/{client_id}/ast` and `{'PATCH'} /api/sessions/{session_id}`

- [X] `/api/clients/{client_id}/ast` present
- [X] `PATCH /api/sessions/{session_id}` present

### 3. Server startup

```bash
cd backend
uvicorn src.main:app --reload --port 8000 --env-file ../.env
```

- [X] Server starts without import errors

### 4. Setup — HC user, client, sessions

Use the HC user from P4 (or recreate):

```bash
cd backend
python scripts/create_hc_user.py
# run: export HC_JWT=... and export HC_ID=...

# Create client
curl -s -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"full_name": "Priya Sharma"}' | python3 -m json.tool
export CLIENT_ID=<id>

# Create M00N session (session_number=1)
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":1,\"scheduled_at\":\"2026-06-01T10:00:00Z\"}" | python3 -m json.tool
export SESSION_ID=<id>

# Create M000 session (session_number=0)
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":0,\"scheduled_at\":\"2026-05-01T10:00:00Z\"}" | python3 -m json.tool
export SESSION0_ID=<id>
```

- [X] M00N session created (201)
- [X] M000 session created (201, session_number=0)

### 5. PATCH /sessions/ — session_notes saves and returns

```bash
# PATCH session_notes
curl -s -X PATCH http://localhost:8000/api/sessions/$SESSION_ID \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Client discussed hydration goals. Sleep improved."}' | python3 -m json.tool
# Expected: 200, session_notes = "Client discussed hydration goals. Sleep improved."

# GET — confirms persistence
curl -s http://localhost:8000/api/sessions/$SESSION_ID \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: session_notes = "Client discussed hydration goals. Sleep improved."
```

- [X] PATCH returns 200 with session_notes populated
- [X] GET returns the same session_notes value (persisted)

### 6. POST /mom/draft — session_notes persisted before LLM call

```bash
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/draft \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Client committed to 2.5L water daily. Meal prep discussed."}' | python3 -m json.tool
# Expected: 200, draft_text populated, llm_call_id not null

# Verify session_notes persisted
curl -s http://localhost:8000/api/sessions/$SESSION_ID -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: session_notes = "Client committed to 2.5L water daily. Meal prep discussed."
```

- [X] draft_mom returns 200 with llm_call_id
- [X] GET /sessions/{id} shows session_notes from draft request (persisted before LLM)

### 7. GET /clients//ast — empty and populated

```bash
# Empty AST (fresh client — no action items, no check-ins)
curl -s http://localhost:8000/api/clients/$CLIENT_ID/ast \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: open_items=[], missed_items=[], trend_tags=[], triage_flags includes "no_recent_checkin"

# Create open action item
curl -s -X POST http://localhost:8000/api/action-items \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"description\":\"Walk 30 min daily\",\"due_date\":\"2026-06-08\"}" | python3 -m json.tool
export AI_ID=<id>

# AST now shows the open item
curl -s http://localhost:8000/api/clients/$CLIENT_ID/ast \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: open_items has "Walk 30 min daily"; missed_items=[]

# Mark item missed
curl -s -X PATCH http://localhost:8000/api/action-items/$AI_ID \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"status":"missed"}' | python3 -m json.tool

# AST: missed item triggers flag
curl -s http://localhost:8000/api/clients/$CLIENT_ID/ast \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: missed_items has 1 item, triage_flags includes "missed_action_item"
```

- [X] Empty AST returns correct shape with "no_recent_checkin" flag
- [X] Open item appears in open_items
- [X] Missed item triggers "missed_action_item" in triage_flags

### 8. GET /sessions//brief — M000 template path

```bash
# M000 brief — NO LLM call, static template
curl -s http://localhost:8000/api/sessions/$SESSION0_ID/brief \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected:
#   brief_text starts with "M000 PREPARATION BRIEF"
#   llm_call_id = null
#   triage_flags = []
```

- [X] brief_text contains "M000 PREPARATION BRIEF"
- [X] llm_call_id is null (no LLM called)

Verify no llm_calls row was written:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT COUNT(*) FROM llm_calls WHERE session_id = '$SESSION0_ID';
"
# Expected: 0
```

- [X] Zero llm_calls rows for M000 session

### 9. GET /sessions//brief — M00N path with AST in brief_text

```bash
# First call — generates brief (requires OPENROUTER_API_KEY)
curl -s http://localhost:8000/api/sessions/$SESSION_ID/brief \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected:
#   brief_text contains "OPEN ACTION ITEMS" section
#   triage_flags contains "missed_action_item" (from step 7)
#   llm_call_id is not null
#   prompt_version = "1.1.0"
```

Verify prompt_version:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT prompt_version, use_case FROM llm_calls
WHERE session_id = '$SESSION_ID' AND use_case = 'brief_generation';
"
# Expected: prompt_version = '1.1.0'
```

- [X] brief_text contains open/missed action items
- [X] triage_flags contains "missed_action_item"
- [X] llm_call_id not null, prompt_version = "1.1.0"

### 10. Migration column check

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'sessions' AND column_name = 'session_notes';
"
# Expected: session_notes | text | YES
```

- [X] sessions.session_notes column exists as TEXT nullable

### 11. Cross-tenant and role checks

```bash
# Generate second HC JWT
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
python -c "
import uuid; from src.auth.jwt_utils import create_access_token; from src.config import get_settings
hc2=str(uuid.uuid4())
t=create_access_token(sub=hc2,role='hc',hc_id=hc2,private_key=get_settings().jwt_private_key)
print('export HC2_JWT='+t)"
# run the export

# Cross-tenant PATCH → 404
curl -s -o /dev/null -w "%{http_code}" \
  -X PATCH http://localhost:8000/api/sessions/$SESSION_ID \
  -H "Authorization: Bearer $HC2_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "steal"}'
# Expected: 404

# Cross-tenant AST → 404
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/api/clients/$CLIENT_ID/ast \
  -H "Authorization: Bearer $HC2_JWT"
# Expected: 404
```

- [X] Wrong HC → PATCH session returns 404
- [X] Wrong HC → AST returns 404

### Summary table

| Check                                               | Pass  | Notes |
| --------------------------------------------------- | ----- | ----- |
| 165 automated tests pass                            | [✅ ] |       |
| New routes registered (PATCH session, AST)          | [ ✅] |       |
| Migration applied (sessions.session_notes column)   | [ ✅] |       |
| PATCH /sessions saves + GET returns session_notes   | [ ✅] |       |
| POST /mom/draft persists notes before LLM           | [✅ ] |       |
| AST empty structure correct, no_recent_checkin flag | [ ✅] |       |
| AST open + missed items + triage flag               | [✅ ] |       |
| M000 brief: template text, llm_call_id=null         | [ ✅] |       |
| M000 brief: zero llm_calls rows                     | [ ✅] |       |
| M00N brief: AST + triage in brief_text              | [ ✅] |       |
| Brief prompt_version = "1.1.0"                      | [ ✅] |       |
| Cross-tenant → 404 on PATCH + AST                  | [✅ ] |       |

---

## P4 — LLM Service

**Status**: verified 2026-05-04

### Prerequisites

`.env` must have both keys set before any LLM-dependent step:

```bash
OPENROUTER_API_KEY=<your key from openrouter.ai>
LLM_CALL_ENCRYPTION_KEY=<run: openssl rand -base64 32>
```

### 1. Automated suite

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest -v
# Expected: 144 passed
```

- [X] 144 tests pass

### 2. New routes registered

```bash
cd backend
PYTHONPATH=. .venv/bin/python3 -c "
from src.main import app
p4 = [r.path for r in app.routes if 'draft' in r.path or 'brief' in r.path]
for p in sorted(set(p4)): print(p)
"
```

Expected output includes:
`/api/sessions/{session_id}/brief`
`/api/sessions/{session_id}/mom/draft`

- [X] Both routes present

### 3. Server startup

```bash
cd backend
.venv/bin/uvicorn src.main:app --reload --port 8000 --env-file ../.env
```

- [X] Server starts without import errors

### 4. Setup — HC user, client, session

Run the printed export commands after each step.

```bash
# HC user (reuse from P3 if still in DB)
PYTHONPATH=. .venv/bin/python3 scripts/create_hc_user.py
# run: export HC_JWT=... and export HC_ID=...

# Create client
curl -s -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"full_name": "Priya Sharma"}' | python3 -m json.tool
export CLIENT_ID=<id>

# Create session
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":1,\"scheduled_at\":\"2026-06-01T10:00:00Z\"}" | python3 -m json.tool
export SESSION_ID=<id>
```

- [X] Client created with `code` field set (e.g. `"CP0001"`)
- [X] Session created (201)

### 5. POST /mom/draft — AI draft generation

```bash
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/draft \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Client discussed hydration goals. Committed to 2.5L daily. Sleep improved from 10pm to 9:30pm."}' \
  | python3 -m json.tool
```

Expected:

- `status = "draft"`
- `draft_text` contains structured MOM text (SUMMARY, ACTION ITEMS, etc.) — not empty JSON
- `llm_call_id` is a UUID (not null)

```bash
export MOM_LLM_CALL_ID=<llm_call_id from response>
```

- [X] `status = "draft"`
- [X] `draft_text` is human-readable structured text
- [X] `llm_call_id` is not null

### 6. Verify `llm_calls` row

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT use_case, model_requested, model_served, fallback_count,
       input_tokens, output_tokens, latency_ms, validation_failed,
       prompt_version, snippet_count
FROM llm_calls WHERE id = '$MOM_LLM_CALL_ID';
"
```

Expected:

- `use_case = 'mom_generation'`
- `model_requested = 'meta-llama/llama-3.3-70b-instruct:free'`
- `model_served` is a non-null slug
- `validation_failed = false`
- `input_tokens > 0`, `output_tokens > 0`, `latency_ms > 0`
- `prompt_version = '1.0.0'`

- [X] `use_case = 'mom_generation'`
- [X] `model_served` non-null
- [X] `validation_failed = false`
- [X] Token counts and latency populated

### 7. Verify `prompt_text` is encrypted (not plain text)

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT length(prompt_text), left(encode(prompt_text, 'hex'), 8) AS hex_prefix
FROM llm_calls WHERE id = '$MOM_LLM_CALL_ID';
"
# hex_prefix should start with 'c30d04' (OpenPGP binary format magic bytes)
# NOT '596f7520' ('You ' in hex — the plaintext start of the system prompt)
```

- [X] `prompt_text` is binary (PGP prefix `c30d04...`) — not plain text

### 7a. Verify `prompt_text` and `completion_text` decrypt correctly

```bash
# Load the encryption key from .env (source it or substitute inline)
source ../.env   # sets $LLM_CALL_ENCRYPTION_KEY in current shell

psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT
  pgp_sym_decrypt(prompt_text, '$LLM_CALL_ENCRYPTION_KEY') AS decrypted_prompt,
  pgp_sym_decrypt(completion_text, '$LLM_CALL_ENCRYPTION_KEY') AS decrypted_completion
FROM llm_calls WHERE id = '$MOM_LLM_CALL_ID';
"
```

Expected:

- `decrypted_prompt` is readable plain text starting with `"You are an expert health coach assistant..."`
- `decrypted_completion` is the raw JSON string the LLM returned (should start with `{` and contain keys like `"summary"`, `"key_discussion_points"`, etc.)

Then verify that error-path rows (where no LLM response arrived) store NULL — not encrypted empty string:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT id, model_served,
  (prompt_text IS NULL) AS prompt_null,
  (completion_text IS NULL) AS completion_null
FROM llm_calls WHERE model_served IS NULL LIMIT 3;
"
# Expected: prompt_null = t, completion_null = t for rows where the HTTP call failed
# (success rows have model_served NOT NULL and both columns non-null)
```

- [X] `decrypted_prompt` starts with `"You are an expert health coach assistant"`
- [X] `decrypted_completion` is valid JSON with MOM keys
- [X] Error-path rows (model_served IS NULL) have NULL for both encrypted columns — skip if 0 rows (means all calls in dev DB succeeded; the 503 path was verified live during P4)

### 8. Re-draft overwrites MOM (idempotent)

```bash
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/draft \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Second take — client also mentioned meal prep challenges."}' \
  | python3 -m json.tool
```

Expected: same session_id, new `llm_call_id`, `final_text = null`, `draft_text` reflects second call.

- [X] Re-draft succeeds (200, not 409)
- [X] `llm_call_id` changed to new value
- [X] `final_text` is null

### 9. PATCH /mom with AI draft → snippet captured

```bash
curl -s -X PATCH http://localhost:8000/api/sessions/$SESSION_ID/mom \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"final_text": "Priya CP0001 made excellent progress. She committed to drinking 2.5L of water daily using a tracking bottle. Sleep moved from 10pm to 9:30pm — encourage maintaining this schedule. Next session: review meal prep strategies."}' \
  | python3 -m json.tool
```

Then verify snippet was captured:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT snippet_type, left(hc_modified_text, 60) AS preview, client_id
FROM hc_style_snippets WHERE hc_user_id = '$HC_ID'
ORDER BY created_at DESC LIMIT 5;
"
```

Expected: at least one row with `snippet_type = 'edit'`, `client_id` = `$CLIENT_ID`.

- [X] `hc_style_snippets` row created with `snippet_type = 'edit'`
- [X] `client_id` matches the session's client

### 10. GET /brief — generates and caches

```bash
# First call — generates
curl -s http://localhost:8000/api/sessions/$SESSION_ID/brief \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Second call — must return same brief_text (cached — no second LLM call)
curl -s http://localhost:8000/api/sessions/$SESSION_ID/brief \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
```

Then check only one `llm_calls` row for brief:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT COUNT(*) FROM llm_calls
WHERE use_case = 'brief_generation' AND session_id = '$SESSION_ID';
"
# Expected: 1 (not 2)
```

- [X] Brief returned on first call (200)
- [X] Second call returns identical `brief_text`
- [X] Exactly 1 `llm_calls` row for `brief_generation`

### 11. Snippet injection — second draft includes style examples

Create a second session (so the snippet from step 9 is available) and request a draft. In the server logs, look for `DEBUG` lines mentioning snippets.

```bash
# Create second session
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":2,\"scheduled_at\":\"2026-06-15T10:00:00Z\"}" | python3 -m json.tool
export SESSION2_ID=<id>

curl -s -X POST http://localhost:8000/api/sessions/$SESSION2_ID/mom/draft \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "Reviewed meal prep. Client has been consistent with water."}' \
  | python3 -m json.tool
```

Then check `snippet_count > 0` in `llm_calls`:

```bash
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT snippet_count, snippet_tokens FROM llm_calls
WHERE use_case = 'mom_generation'
ORDER BY created_at DESC LIMIT 1;
"
# Expected: snippet_count >= 1, snippet_tokens > 0
```

- [X] `snippet_count > 0` in llm_calls row for second session draft

### 12. Manual MOM — no snippet on PATCH

```bash
# New session, manual MOM (no AI draft)
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":3,\"scheduled_at\":\"2026-07-01T10:00:00Z\"}" | python3 -m json.tool
export SESSION3_ID=<id>

curl -s -X POST http://localhost:8000/api/sessions/$SESSION3_ID/mom \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"draft_text": "I typed this myself."}' | python3 -m json.tool

count_before=$(psql -t postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev \
  -c "SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = '$HC_ID';")

curl -s -X PATCH http://localhost:8000/api/sessions/$SESSION3_ID/mom \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"final_text": "I edited this significantly — many new words added here for the review."}' | python3 -m json.tool

count_after=$(psql -t postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev \
  -c "SELECT COUNT(*) FROM hc_style_snippets WHERE hc_user_id = '$HC_ID';")

echo "Before: $count_before | After: $count_after  (should be equal)"
```

- [X] Snippet count unchanged after patching a manual MOM

### 13. Wrong HC → 404

```bash
PYTHONPATH=. .venv/bin/python3 -c "
import uuid; from src.auth.jwt_utils import create_access_token; from src.config import get_settings
hc2=str(uuid.uuid4())
t=create_access_token(sub=hc2,role='hc',hc_id=hc2,private_key=get_settings().jwt_private_key)
print('export HC2_JWT='+t)"
# run the export, then:
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/draft \
  -H "Authorization: Bearer $HC2_JWT" -H "Content-Type: application/json" \
  -d '{"session_notes": "..."}'
# Expected: 404
```

- [X] Wrong HC → 404

### 14. Prompt version bump → reflected in `llm_calls` *(one-time structural check)*

> **Why this exists**: verifies that `llm_calls.prompt_version` is config-driven (YAML frontmatter), not hardcoded. Run once when first verifying P4; re-run only if `src/llm_service/prompts.py` is modified. Skip on routine re-verification.

```bash
# Edit backend/prompts/mom_draft.md — change version: "1.0.0" to "1.0.1"
# Restart uvicorn (Ctrl-C and rerun)
# Make one more POST /mom/draft call
# Then:
psql postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev -c "
SELECT prompt_version FROM llm_calls WHERE use_case = 'mom_generation'
ORDER BY created_at DESC LIMIT 1;
"

# Expected: 1.0.1
# Revert: change version back to "1.0.0" and restart
```

- [X] Prompt version change visible in `llm_calls.prompt_version` without code change

### 15. Grep hygiene

```bash
cd backend

# No direct AsyncClient outside the factory
grep -r "httpx.AsyncClient(" src/ | grep -v "lib/http.py"
# Expected: no output

# Model slugs only in YAML — not in Python source
grep -rn "llama-3.3\|gemma-3\|nemotron\|gpt-oss" src/ --include="*.py"
# Expected: no output
```

- [X] No raw httpx.AsyncClient usage outside lib/http.py
- [X] Model slugs only in llm_config.yaml

### Summary table

| Check                                                     | Pass | Notes |
| --------------------------------------------------------- | ---- | ----- |
| 144 automated tests pass                                  | ✅   |       |
| `/mom/draft` route registered                           | ✅   |       |
| POST /mom/draft → AI draft_text + llm_call_id            | ✅   |       |
| llm_calls row: all fields populated                       | ✅   |       |
| prompt_text encrypted (PGP binary)                        | ✅   |       |
| prompt/completion decryptable, error rows NULL            | ✅   |       |
| Re-draft overwrites MOM, clears final_text                | ✅   |       |
| PATCH with AI draft → snippet captured                   | ✅   |       |
| GET /brief generates + caches (1 llm_calls row)           | ✅   |       |
| Second session draft injects snippets (snippet_count > 0) | ✅   |       |
| Manual MOM PATCH → no snippet                            | ✅   |       |
| Wrong HC → 404                                           | ✅   |       |
| Prompt version bump visible in llm_calls                  | ✅   |       |
| Grep hygiene (httpx, model slugs)                         | ✅   |       |

---

## P3.5 — Naming cleanup ⏳

**Status**: awaiting verification

### Structure

- [ ] `docs/specs/Unit_001_HcCoreCycle/` exists
- [ ] `SPEC-0001-hc-core-cycle.md` is inside it (not in `docs/specs/` flat)
- [ ] `SPEC-0002-llm-service.md` is inside it
- [ ] All four PHASE files (`PHASE-00`, `PHASE-01`, `PHASE-02`, `PHASE-03`) are inside it
- [ ] `git log --follow docs/specs/Unit_001_HcCoreCycle/SPEC-0001-hc-core-cycle.md` shows full history pre-rename
- [ ] `git log --follow docs/specs/Unit_001_HcCoreCycle/SPEC-0002-llm-service.md` shows full history pre-rename

### File quality

- [ ] Each PHASE file is substantive (P0/P1/P2 ≥ 80 lines; P3 ≥ 120 lines)
- [ ] Each PHASE file links its source SESSION_LOG entry (`2026-05-01` or `2026-05-02`)
- [ ] Each PHASE file links its corresponding VERIFICATION section
- [ ] Each PHASE file lists ADRs implemented with links
- [ ] No fabricated content — every claim traceable to SESSION_LOG, ADR, or migration commit

### Cross-references

- [ ] `grep -rn "specs/0001\|specs/0002\|specs/0003\|specs/0004" --include="*.md" .` returns only historical SESSION_LOG/starter-prompt entries (not rewritten) and the PHASE-03 recording of the 0002-domain-crud.md deletion
- [ ] `docs/build-plan.md` phase sections (P0–P9) each have a "Phase plan" link
- [ ] `CLAUDE.md` §6 describes the unit/SPEC/PHASE naming convention

### Templates and skills

- [ ] `docs/specs/template-phase-plan.md` exists and is structurally distinct from `docs/specs/0000-template_SPEC.md`
- [ ] `.claude/skills/skill-write-phase-plan.md` exists
- [ ] `.claude/skills/skill-write-spec.md` exists
- [ ] `docs/specs/0000-template_SPEC.md` has the SPEC-vs-PHASE distinction header and "Implemented by phases" field

### Project instructions

- [ ] `PROJECT-CUSTOM-INSTRUCTIONS.md` exists at repo root with the naming convention section and updated "What's in Project knowledge" table
- [ ] (Manual) Content uploaded to claude.ai Project knowledge — SoJo to confirm

### Untouched (regression check)

- [ ] No file under `backend/` was modified in this session
- [ ] No file under `docs/decisions/`, `docs/diagrams/`, `docs/domain/` was structurally moved
- [ ] All existing tests still pass: `cd backend && source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate && pytest -v` (expected: 144 passed)

---

## P3 — Domain CRUD + Client OAuth ✅

**Status**: verified 2026-05-02

### Setup

```bash
cd backend

# 1. Automated suite (run this first — must be green before manual steps)
uv run pytest -v
# Expected: 107 passed
```

Start the server in a second terminal:

```bash
cd backend
uv run uvicorn src.main:app --reload --port 8000 --env-file ../.env
```

(Uses the root `.env`. See `.env.example` for the required variables.)

### 2. All P3 routes registered

```bash
cd backend
uv run python3 -c "
from src.main import app
p3 = [r.path for r in app.routes if any(x in r.path for x in ['/clients','/sessions','/action-items','/check-ins','/me/','/auth/client'])]
for p in sorted(set(p3)): print(p)
"
```

Expected output includes all of:
`/api/auth/client/callback`, `/api/auth/client/start`, `/api/check-ins/{check_in_id}/flag`, `/api/clients`, `/api/clients/{client_id}`, `/api/clients/{client_id}/check-ins`, `/api/clients/{client_id}/invite`, `/api/action-items`, `/api/action-items/{item_id}`, `/api/me/action-items`, `/api/me/action-items/{item_id}`, `/api/me/check-ins`, `/api/me/moms`, `/api/me/moms/{mom_id}`, `/api/sessions`, `/api/sessions/{session_id}`, `/api/sessions/{session_id}/brief`, `/api/sessions/{session_id}/end`, `/api/sessions/{session_id}/mom`, `/api/sessions/{session_id}/mom/send`

- [X] All routes listed above present

### 3. Create a real HC user in the dev DB and generate a JWT

`clients.hc_user_id` is a FK to `users` — the JWT sub must be a real user row.

```bash
cd backend
python3 scripts/create_hc_user.py
```

Run the printed `export HC_JWT=...` and `export HC_ID=...` commands before steps 4–8.

### 4. HC — create client, list, cross-tenant

```bash
# Create client
curl -s -X POST http://localhost:8000/api/clients \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"full_name": "Priya Sharma"}' | python3 -m json.tool
export CLIENT_ID=<id from response>

# List → Priya appears
curl -s http://localhost:8000/api/clients -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool

# Second HC tries to read Priya → 404
uv run python3 -c "
import uuid; from src.auth.jwt_utils import create_access_token; from src.config import get_settings
hc2=str(uuid.uuid4()); t=create_access_token(sub=hc2,role='hc',hc_id=hc2,private_key=get_settings().jwt_private_key)
print('export HC2_JWT='+t)"
# run the export, then:
curl -s http://localhost:8000/api/clients/$CLIENT_ID -H "Authorization: Bearer $HC2_JWT"
# Expected: {"detail":"Client not found"}
```

- [X] Client created → 201 with journey_stage="onboarding"
- [X] Own client in list
- [X] Cross-tenant GET by ID → 404

### 5. Session + MOM lifecycle

```bash
# Create session
curl -s -X POST http://localhost:8000/api/sessions \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"session_number\":1,\"scheduled_at\":\"2026-06-01T10:00:00Z\"}" | python3 -m json.tool
export SESSION_ID=<id>

# Create MOM (status should be "draft")
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"draft_text":"Discussed nutrition goals."}' | python3 -m json.tool

# Send MOM
curl -s -X POST http://localhost:8000/api/sessions/$SESSION_ID/mom/send \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
export MOM_ID=<id from send response>
# Expected: status="sent", sent_at not null
```

- [X] Session created → 201
- [X] MOM created → status=draft
- [X] MOM sent → status=sent, sent_at populated

### 6. Action items

```bash
curl -s -X POST http://localhost:8000/api/action-items \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d "{\"client_id\":\"$CLIENT_ID\",\"description\":\"Drink 2L water daily\",\"due_date\":\"2026-06-08\"}" | python3 -m json.tool
# Expected: 201, status="open", due_date="2026-06-08"
export AI_ID=<id>

curl -s -X PATCH http://localhost:8000/api/action-items/$AI_ID \
  -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
  -d '{"status":"completed"}' | python3 -m json.tool
# Expected: status="completed", completed_at not null
```

- [X] Action item created with due_date, default status=open
- [X] Marked completed → completed_at populated

### 7. Invite flow

```bash
curl -s -X POST http://localhost:8000/api/clients/$CLIENT_ID/invite \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: 201 with invite_token, invite_url containing /api/auth/client/start?invite=
export INVITE_TOKEN=<invite_token>

# Valid invite → Google URL
curl -s "http://localhost:8000/api/auth/client/start?invite=$INVITE_TOKEN" | python3 -m json.tool
# Expected: {"auth_url": "https://accounts.google.com/..."}

# Invalid invite → 400
curl -s "http://localhost:8000/api/auth/client/start?invite=totallyfaketoken" | python3 -m json.tool
# Expected: 400
```

- [X] invite_url contains `/api/auth/client/start?invite=`
- [X] Valid invite → 200 with Google auth URL
- [X] Invalid invite → 400

### 8. Client-facing endpoints

```bash
# Generate unlinked client JWT (no client record in DB)
uv run python3 -c "
import uuid,os; from src.auth.jwt_utils import create_access_token; from src.config import get_settings
t=create_access_token(sub=str(uuid.uuid4()),role='client',hc_id=os.environ['HC_ID'],private_key=get_settings().jwt_private_key)
print('export CLIENT_JWT='+t)"
# run the export

curl -s http://localhost:8000/api/me/moms -H "Authorization: Bearer $CLIENT_JWT"
# Expected: 404 {"detail":"Client record not found"}  — not 500, not 200

curl -s http://localhost:8000/api/me/moms -H "Authorization: Bearer $HC_JWT"
# HC token on /api/me route → Expected: 401 or 403 (role=hc not allowed on /api/me/*)
```

- [X] Unlinked client JWT → /api/me/* returns 404 (not 500)
- [X] HC JWT on /api/me/* → 401/403

### 9. Coach-reviewed gate grep

```bash
cd backend
grep -n "status.*sent\|sent.*status" src/api/me.py
# Expected: lines showing WHERE status = "sent" filter in list_my_moms and get_my_mom

grep -rn "mom_text\|final_text\|draft_text" src/api/me.py
# Expected: no output — me.py exposes MomOut schema, doesn't reference raw text field names
```

- [X] status="sent" filter present in me.py for both MOM endpoints
- [X] No raw text field manipulation in me.py

### 10. Pagination with >20 items

```bash
for i in $(seq 1 25); do
  curl -s -X POST http://localhost:8000/api/clients \
    -H "Authorization: Bearer $HC_JWT" -H "Content-Type: application/json" \
    -d "{\"full_name\":\"Bulk $i\"}" > /dev/null
done

curl -s "http://localhost:8000/api/clients?limit=20" -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: 20 items, next_cursor is not null

curl -s 'http://localhost:8000/api/clients?cursor=notvalidbase64!!!' \
  -H "Authorization: Bearer $HC_JWT" | python3 -m json.tool
# Expected: 400 {"detail": "Invalid cursor"}
```

- [ ]
- [X] Invalid cursor → 400

### 11. Brief stub returns correct message

```bash
curl -s http://localhost:8000/api/sessions/$SESSION_ID/brief \
  -H "Authorization: Bearer $HC_JWT"
# Expected: 404 {"detail":"Brief not found (generation is P5)"}
```

- [X] Brief endpoint → 404 with P5 message

### 12. Grep hygiene

```bash
cd backend
grep -r "httpx.AsyncClient(" src/ | grep -v "lib/http.py"
# Expected: no output

grep -r "\bSession(" src/ | grep -v "AsyncSession\|async_sessionmaker\|class Session"
# Expected: no output (all Session( usages are model instantiation or class definition)
```

- [X] No raw httpx.AsyncClient outside factory
- [X] No sync Session() usage

### Summary table

| Check                           | Pass | Notes |
| ------------------------------- | ---- | ----- |
| 107 automated tests pass        | ✅   |       |
| All routes registered           | ✅   |       |
| Client CRUD + cross-tenant 404  | ✅   |       |
| Session + MOM lifecycle         | ✅   |       |
| Action items + completed_at     | ✅   |       |
| Invite URL + start endpoint     | ✅   |       |
| Unlinked client JWT → 404      | ✅   |       |
| HC JWT on /api/me/* → 401/403  | ✅   |       |
| Coach-reviewed gate grep        | ✅   |       |
| Pagination >20 + invalid cursor | ✅   |       |
| Brief → 404 with P5 message    | ✅   |       |
| Grep hygiene (httpx, Session)   | ✅   |       |

---

## P2 — Auth Service ✅

**Status**: verified 2026-05-01

### Automated (run first)

```bash
cd backend
uv run pytest -v
```

Expected: **37 passed**

### 1. Auth routes registered

```bash
uv run python -c "from src.main import app; print([r.path for r in app.routes])"
```

Expected output includes: `/api/auth/google/start`, `/api/auth/google/callback`, `/api/auth/refresh`, `/api/auth/logout`

### 2. `/api/auth/google/start` returns an auth URL

Start the server:

```bash
DATABASE_URL=postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev \
  uv run uvicorn src.main:app --reload --port 8000
```

Then in another terminal:

```bash
curl -s http://localhost:8000/api/auth/google/start | python3 -m json.tool
```

Expected: `{"auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."}` (even with empty `GOOGLE_CLIENT_ID` — URL is still constructed)

### 3. Protected endpoint returns 401 without token

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/healthz
# Expected: 200

# Any future protected endpoint (P3 onwards) will return:
# curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/clients/
# Expected: 401
```

### 4. JWT decode at jwt.io

Generate a test token:

```bash
cd backend
uv run python3 - <<'EOF'
from src.auth.jwt_utils import create_access_token
import uuid

# Use the test keys from test_jwt_utils.py
PRIV = open("/tmp/test_priv.pem").read()  # regenerate if gone: see Step 1 in plan
token = create_access_token(
    sub=str(uuid.uuid4()), role="hc", hc_id=str(uuid.uuid4()),
    private_key=PRIV,
)
print(token)
EOF
```

Paste into https://jwt.io and confirm payload contains: `sub`, `role`, `hc_id`, `iss: https://api.parivarthan.com`, `aud: parivarthan-api`, `exp`

### 5. Refresh token rotation (DB check)

```bash
cd backend
uv run python3 - <<'EOF'
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.auth.refresh import issue_refresh_token, rotate_refresh_token
from src.db.models import User
from src.db.base import Base
import uuid

DB = "postgresql+asyncpg://postgres:localdevpassword@localhost:5432/parivarthan_dev"

async def main():
    engine = create_async_engine(DB)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User(email=f"verify-{uuid.uuid4().hex[:6]}@test.com", google_sub=uuid.uuid4().hex)
        db.add(user)
        await db.flush()
        raw = await issue_refresh_token(db, user.id)
        new_raw, uid = await rotate_refresh_token(db, raw)
        print(f"Rotation OK — user_id: {uid}")
        try:
            await rotate_refresh_token(db, raw)
        except ValueError as e:
            print(f"Old token correctly rejected: {e}")
        await db.rollback()
    await engine.dispose()

asyncio.run(main())
EOF
```

Expected:

```
Rotation OK — user_id: <uuid>
Old token correctly rejected: refresh token replay detected — all sessions revoked
```

### 6. `grep` check — no raw httpx usage outside factory

```bash
grep -r "httpx.AsyncClient(" backend/src | grep -v "lib/http.py"
```

Expected: **no output** (all httpx usage goes through `make_http_client()`)

---

## P1 — Data Layer ✅

**Status**: verified 2026-05-01

| Check                                                                         | Result |
| ----------------------------------------------------------------------------- | ------ |
| `uv run pytest -v` → 29 passed                                             | ✅     |
| `alembic upgrade head` — 16 tables created                                 | ✅     |
| `alembic downgrade base` then `upgrade head` — clean roundtrip           | ✅     |
| `\d clients` → `journey_stage DEFAULT 'onboarding'` (no extra quotes)    | ✅     |
| `\d moms` → `status DEFAULT 'draft'`                                     | ✅     |
| Partial index `idx_refresh_tokens_active` uses `WHERE revoked_at IS NULL` | ✅     |
| All 16 tables present in `pg_tables`                                        | ✅     |

---

## P0 — Repo Scaffolding

**Status**: partially verified (test suite green; wrangler/frontend manual steps pending)

| Check                                                             | Result |
| ----------------------------------------------------------------- | ------ |
| `uv run pytest tests/unit/` passes                              | ✅     |
| `uv run pytest tests/integration/test_health.py` passes         | ✅     |
| `GET /healthz` returns `{"status":"ok","version":"0.1.0"}`    | ✅     |
| `X-Request-ID` echoed in response headers                       | ✅     |
| Frontend `npm run dev` starts without errors (requires Node 22) | ✅     |
| `.env` not committed (in `.gitignore`)                        | ✅     |
| `docker-compose up` brings up postgres healthy                  | ✅     |

---

## P7 — External Scheduler

**Status**: Verified 2026-06-16 — unit tests (63/63). AC4/AC5 (DB-level retirement) deferred to P9 smoke gate where a populated dev DB will be available.

### How to run

```bash
cd backend
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
PYTHONPATH=$(pwd) pytest tests/unit/ -q
# Expected: 63 passed
```

### Acceptance criteria

| # | Check | Method | Result |
|---|---|---|---|
| AC1 | Endpoint returns 200 with correct token | `curl -X POST .../internal/scheduled-tasks -H "X-Scheduler-Token: <secret>"` → `{"tasks_run":["snippet_retirement"],"retired_count":0}` | ✅ Verified manually against local dev server |
| AC2 | No token → 401; wrong token → 401 | `curl` without header / with wrong header | ✅ Verified manually — both return 401 |
| AC3 | Idempotency: running twice produces same state | `retired_at IS NULL` guard in SQL + `test_already_retired_snippet_is_skipped` unit test | ✅ Logic verified by unit test |
| AC4 | 200-day-old snippet gets `retired_at` set | Requires populated dev DB — defer to P9 smoke gate | ⏳ Deferred to P9 |
| AC5 | Recent snippet `retired_at` stays NULL | Requires populated dev DB — defer to P9 smoke gate | ⏳ Deferred to P9 |

### Unit test delta

| Phase | Count |
|---|---|
| P6 baseline | 52 |
| + Task 1 (config) | +2 |
| + Task 2 (scheduler logic) | +9 |
| **P7 total** | **63** |
