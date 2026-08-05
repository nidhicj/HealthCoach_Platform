# PHASE-02d — F8 Client-Facing Diet Chart View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This plan builds on PHASE-02a (`/me/*` shell) — must be shipped first. It does **not** depend on PHASE-02b or 02c and can be built in either order relative to them.

**Goal:** The client sees the current (latest sent) diet chart and a history of every past version, at `/me/diet-chart`. This is the last piece of F8 — the HC-side half (chart editor, "Send to client" action, `diet_chart_sends` table) **already fully exists and ships today** (`backend/src/api/diet_charts.py:335-356`, confirmed by reading the code — not spec text). No migration, no new table: this plan is a read-only client-facing view onto data that's already being written on every HC "Send to client" click.

**Architecture:** One new backend endpoint (`GET /api/me/diet-chart-sends`, paginated, in the already-existing `me.py`) and one new frontend page. The grid-rendering logic is a direct, deliberate copy of the read-only rendering already used by the HC editor page (`frontend/src/app/(app)/clients/[clientId]/page.tsx` lines 770–823) — not extracted into a shared component, matching this codebase's existing convention of not refactoring across HC/client boundaries preemptively (same call made in PHASE-02a's Self-review for the action-items list).

**Tech stack:** Same as PHASE-02a/b/c. No new dependency, no migration.

## Global Constraints

- Python ≥ 3.12, FastAPI ≥ 0.115, SQLAlchemy ≥ 2.0, Pydantic ≥ 2.7
- Activate the Python env with `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate` before backend commands
- Read-only from the client's perspective — no PATCH/POST in this plan; sending remains exclusively an HC action via the already-existing `/api/clients/{id}/diet-chart/send`
- Follow this app's existing Tailwind/design-token conventions exactly (see PHASE-02a's Global Constraints)

---

## Task 1: Backend — `GET /api/me/diet-chart-sends`

**Files:**
- Modify: `backend/src/api/me.py`
- Test: `backend/tests/integration/test_me.py` (extend)

**Interfaces:**
- Produces: `MyDietChartSendOut{id, client_id, chart_name, chart_parameters, sent_at}`, `GET /api/me/diet-chart-sends -> PaginatedList[MyDietChartSendOut]`, ordered newest-first — Task 3 consumes this; the frontend treats `items[0]` as "current" and the rest as "history."

- [ ] **Step 1.1: Write the failing tests**

`DietChart` has no `client_id` column — a client's "active chart" is a join through `ContentAssignment` (`backend/src/api/diet_charts.py:127-141`, `_get_active_chart`), created via the paste-template + generate flow. Reuse the exact same real-API setup pattern `test_diet_chart_send.py` already uses (paste a template, generate for the client) rather than constructing `DietChart`/`ContentAssignment` rows by hand:

```python
@pytest.mark.asyncio
async def test_client_sees_latest_diet_chart_send_first(http_client, hc_headers, client_headers, client_rec):
    template_r = await http_client.post(
        "/api/diet-charts/templates/paste", headers=hc_headers,
        json={"name": "Week 1", "text": "Day\tBreakfast\nMonday\tOats"},
    )
    template_id = template_r.json()["id"]
    await http_client.post(
        f"/api/clients/{client_rec.id}/diet-chart/generate", headers=hc_headers,
        json={"template_id": template_id},
    )
    send_r = await http_client.post(f"/api/clients/{client_rec.id}/diet-chart/send", headers=hc_headers)
    assert send_r.status_code == 201, send_r.text

    r = await http_client.get("/api/me/diet-chart-sends", headers=client_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["chart_name"] == "Week 1"
    assert "grid" in items[0]["chart_parameters"]


@pytest.mark.asyncio
async def test_client_sees_empty_diet_chart_sends_when_none_sent_yet(http_client, client_headers, client_rec):
    r = await http_client.get("/api/me/diet-chart-sends", headers=client_headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_client_sees_multiple_sends_newest_first(http_client, hc_headers, client_headers, client_rec):
    template_r = await http_client.post(
        "/api/diet-charts/templates/paste", headers=hc_headers,
        json={"name": "Week 1", "text": "Day\tBreakfast\nMonday\tOats"},
    )
    template_id = template_r.json()["id"]
    await http_client.post(
        f"/api/clients/{client_rec.id}/diet-chart/generate", headers=hc_headers,
        json={"template_id": template_id},
    )
    await http_client.post(f"/api/clients/{client_rec.id}/diet-chart/send", headers=hc_headers)

    await http_client.patch(
        f"/api/clients/{client_rec.id}/diet-chart", headers=hc_headers,
        json={"parameters": {"meal_slots": ["Breakfast"], "grid": {"Monday": {"Breakfast": {"food": "Poha", "timing": "8am"}}}}},
    )
    await http_client.post(f"/api/clients/{client_rec.id}/diet-chart/send", headers=hc_headers)

    r = await http_client.get("/api/me/diet-chart-sends", headers=client_headers)
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["chart_parameters"]["grid"]["Monday"]["Breakfast"]["food"] == "Poha"  # newest first


@pytest.mark.asyncio
async def test_client_cannot_see_other_clients_diet_chart_sends(http_client, hc_headers, client_headers):
    other_r = await http_client.post("/api/clients", headers=hc_headers, json={"full_name": "Other Client"})
    other_id = other_r.json()["id"]
    template_r = await http_client.post(
        "/api/diet-charts/templates/paste", headers=hc_headers,
        json={"name": "Not yours", "text": "Day\tBreakfast\nMonday\tOats"},
    )
    template_id = template_r.json()["id"]
    await http_client.post(
        f"/api/clients/{other_id}/diet-chart/generate", headers=hc_headers,
        json={"template_id": template_id},
    )
    await http_client.post(f"/api/clients/{other_id}/diet-chart/send", headers=hc_headers)

    r = await http_client.get("/api/me/diet-chart-sends", headers=client_headers)
    assert r.json()["items"] == []
```

- [ ] **Step 1.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_me.py -k diet_chart -v`
Expected: FAIL — route doesn't exist

- [ ] **Step 1.3: Implement**

Add to the imports in `backend/src/api/me.py`:

```python
from src.db.models import DietChartSend
```

Add the schema and route:

```python
class MyDietChartSendOut(BaseModel):
    id: UUID
    client_id: UUID
    chart_name: str
    chart_parameters: dict
    sent_at: datetime

    model_config = {"from_attributes": True}


@router.get("/diet-chart-sends")
async def list_my_diet_chart_sends(
    claims: ClientClaimsDep,
    hc_id: TenantDep,
    db: DbDep,
    limit: LimitDep = 20,
    cursor: Annotated[str | None, Query()] = None,
) -> PaginatedList[MyDietChartSendOut]:
    client = await _resolve_client(db, claims, hc_id)

    q = select(DietChartSend).where(DietChartSend.client_id == client.id)
    if cursor:
        cur_ts, cur_id = decode_cursor(cursor)
        q = q.where(
            or_(
                DietChartSend.sent_at < cur_ts,
                and_(DietChartSend.sent_at == cur_ts, DietChartSend.id < cur_id),
            )
        )
    q = q.order_by(DietChartSend.sent_at.desc(), DietChartSend.id.desc()).limit(limit + 1)
    rows = (await db.execute(q)).scalars().all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = encode_cursor(rows[-1].sent_at, rows[-1].id)

    return PaginatedList(items=[MyDietChartSendOut.model_validate(r) for r in rows], next_cursor=next_cursor)
```

- [ ] **Step 1.4: Run — confirm pass, then full suite**

Run: `cd backend && pytest tests/integration/test_me.py -v && pytest -x`

- [ ] **Step 1.5: Commit**

```bash
git add backend/src/api/me.py backend/tests/integration/test_me.py
git commit -m "feat(me): GET /api/me/diet-chart-sends — client-facing F8 read view (PHASE-02d Task 1)"
```

---

## Task 2: Frontend — `lib/api/me.ts` diet-chart-sends wrapper

**Files:**
- Modify: `frontend/src/lib/api/me.ts`
- Test: `frontend/tests/unit/me-api.test.ts` (extend, same style as its existing tests)

**Interfaces:**
- Produces: `listMyDietChartSends(): Promise<{items: MyDietChartSendOut[]; next_cursor: string|null}>` — Task 3 consumes this.

- [ ] **Step 2.1: Write the failing test**

Add one test to `frontend/tests/unit/me-api.test.ts`, matching the exact style of its existing 3 tests (mock `fetchWithAuth`, assert URL called and shape parsed) — asserting `listMyDietChartSends()` calls `GET /api/me/diet-chart-sends` and returns parsed items including a nested `chart_parameters` object.

- [ ] **Step 2.2: Run — confirm failure**

Run: `cd frontend && npx vitest run tests/unit/me-api.test.ts`

- [ ] **Step 2.3: Implement**

Add to `frontend/src/lib/api/me.ts`:

```ts
export const MyDietChartSendOutSchema = z.object({
  id: z.string(),
  client_id: z.string(),
  chart_name: z.string(),
  chart_parameters: z.record(z.string(), z.unknown()),
  sent_at: z.string(),
});

export type MyDietChartSendOut = z.infer<typeof MyDietChartSendOutSchema>;

const PaginatedDietChartSendsSchema = z.object({
  items: z.array(MyDietChartSendOutSchema),
  next_cursor: z.string().nullable(),
});

export async function listMyDietChartSends(): Promise<{ items: MyDietChartSendOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/me/diet-chart-sends`);
  if (!res.ok) throw new Error(`List my diet chart sends failed: ${res.status}`);
  return PaginatedDietChartSendsSchema.parse(await res.json());
}
```

- [ ] **Step 2.4: Run — confirm pass**

Run: `cd frontend && npx vitest run`

- [ ] **Step 2.5: Commit**

```bash
git add frontend/src/lib/api/me.ts frontend/tests/unit/me-api.test.ts
git commit -m "feat(me): frontend wrapper for diet-chart-sends (PHASE-02d Task 2)"
```

---

## Task 3: Frontend — `/me/diet-chart` page (read-only, current + history)

**Files:**
- Create: `frontend/src/app/me/diet-chart/page.tsx`
- Modify: `frontend/src/app/me/layout.tsx` (add nav link)

**Interfaces:**
- Consumes: `listMyDietChartSends` (Task 2).

- [ ] **Step 3.1: Add the nav link**

`frontend/src/app/me/layout.tsx` ships (PHASE-02a) with no nav links at all — only the "Tapas" wordmark. If PHASE-02b and/or 02c have already shipped by the time this task runs, they'll have added `/me/checkins`/`/me/chat` links; add this one alongside whatever's already there. If 02d runs before 02b/02c (this plan's header notes it doesn't depend on them), this is the *first* nav link in the file — add it as the sole entry, same markup, and whichever of 02b/02c/02d lands next adds its own link alongside the ones already present rather than assuming a fixed set:

```tsx
          <Link href="/me/diet-chart" className="font-sans text-xs font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground">
            Diet Chart
          </Link>
```

- [ ] **Step 3.2: Implement the page**

The grid-rendering block below is a direct copy of the existing read-only rendering in `frontend/src/app/(app)/clients/[clientId]/page.tsx` (lines 770–823) — same `grid`/`meal_slots` shape, same table markup, deliberately not extracted into a shared component (see this plan's Architecture note).

```tsx
// frontend/src/app/me/diet-chart/page.tsx
"use client";

import { useEffect, useState } from "react";
import { listMyDietChartSends, type MyDietChartSendOut } from "@/lib/api/me";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function ChartGrid({ parameters }: { parameters: Record<string, unknown> }) {
  const grid = (parameters?.grid ?? {}) as Record<string, Record<string, { food: string; timing: string }>>;
  const slots = (parameters?.meal_slots ?? []) as string[];

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
          {DAYS.map((day) => (
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
}

export default function ClientDietChartPage() {
  const [sends, setSends] = useState<MyDietChartSendOut[] | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  useEffect(() => {
    listMyDietChartSends().then((data) => setSends(data.items)).catch(() => setSends([]));
  }, []);

  const [current, ...history] = sends ?? [];

  return (
    <div className="space-y-8">
      <h1 className="font-heading text-3xl font-black text-foreground">Diet Chart</h1>

      {sends === null && <p className="font-sans text-sm text-muted-foreground">Loading…</p>}

      {sends !== null && sends.length === 0 && (
        <p className="font-sans text-sm italic text-muted-foreground">
          Your coach hasn&rsquo;t sent a diet chart yet.
        </p>
      )}

      {current && (
        <section className="space-y-3">
          <p className="font-sans text-xs uppercase tracking-widest text-muted-foreground">
            Current — sent {new Date(current.sent_at).toLocaleDateString()}
          </p>
          <ChartGrid parameters={current.chart_parameters} />
        </section>
      )}

      {history.length > 0 && (
        <section className="space-y-3">
          <button
            onClick={() => setHistoryOpen((v) => !v)}
            className="font-sans text-xs font-bold uppercase tracking-widest text-foreground"
          >
            {historyOpen ? "Hide" : "Show"} history ({history.length})
          </button>
          {historyOpen && (
            <div className="space-y-6">
              {history.map((h) => (
                <div key={h.id} className="space-y-2 border-t border-border pt-4">
                  <p className="font-sans text-xs uppercase tracking-widest text-muted-foreground">
                    Sent {new Date(h.sent_at).toLocaleDateString()}
                  </p>
                  <ChartGrid parameters={h.chart_parameters} />
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
```

- [ ] **Step 3.3: E2E test**

Add a test mocking `/api/me/diet-chart-sends` with 2 items, visiting `/me/diet-chart`, asserting the current chart renders and clicking "Show history" reveals the older one.

- [ ] **Step 3.4: Run full suite, then commit**

```bash
cd frontend && npx vitest run && npx playwright test
git add frontend/src/app/me/diet-chart/ frontend/src/app/me/layout.tsx frontend/tests/e2e/
git commit -m "feat(me): /me/diet-chart page — current chart + version history (PHASE-02d Task 3, F8 complete)"
```

---

## Self-review

**Spec coverage:** F8's client-facing half fully covered — "current chart = latest sent snapshot" ✓, "collapsible history of every past version" ✓. The HC-side half needed no work here since it already shipped (confirmed by reading code, not assumed from the spec).

**Placeholder scan:** None — all four Task 1 tests use the real API setup path (paste template → generate → send), matching `test_diet_chart_send.py`'s existing convention exactly, not hand-constructed DB rows.

**Type consistency:** `MyDietChartSendOut` is intentionally a distinct schema from `diet_charts.py`'s existing `DietChartSendOut` (HC-facing, omits `chart_parameters`) — not a duplicate-vs-shared-schema oversight, a deliberate shape difference for a different audience, called out in this file's Architecture section.

**Known follow-ups:** None beyond what's already called out in PHASE-02b/02c's own Self-review sections (Roster Board D-24 indicator).

**This completes PHASE-02** (02a foundation + 02b check-ins + 02c messaging + 02d diet-chart view = full F2 + F8 client-facing half, per `SPEC-0001-one-stop-spot.md` §9's PHASE-02 row). Next per the build sequence: PHASE-03 (Logged Meals, F3) or PHASE-04 (Payments, F4) — both are independent of each other and of everything in PHASE-02.

**Execution:** Subagent-driven, per SoJo's standing instruction.
