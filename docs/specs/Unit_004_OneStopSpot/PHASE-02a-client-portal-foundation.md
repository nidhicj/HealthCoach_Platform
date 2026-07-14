# PHASE-02a — Client Portal Foundation (role-aware routing + `/me/*` shell) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the concrete bug D-31 surfaced (`frontend/src/app/auth/callback/page.tsx` hardcodes `router.replace("/dashboard")` regardless of role) and stand up the minimal real `/me/*` shell so that redirect target isn't a 404 — a client logging in for the first time lands on `/me` and sees their own open action items.

**Scope note (why this isn't "all of PHASE-02"):** PHASE-02 per `SPEC-0001-one-stop-spot.md` §9 bundles four largely-independent subsystems: this foundation (routing + shell), the check-in request/answer lifecycle (D-21–D-23), free messaging (D-25), and F8's client-facing diet-chart view. Each is substantial enough to deserve its own plan and its own shippable checkpoint — matching this spec's existing PHASE-01a–f sub-lettering precedent (PHASE-01c/d/e/f already exist as separate docs for exactly this reason). This plan is **PHASE-02a**; check-ins (02b), messaging (02c), and diet-chart view (02d) are separate follow-on plans, written after this one ships.

**Architecture:** Two small additive changes, no new tables, no new dependencies:
1. Backend: `/api/auth/refresh`'s `TokenResponse` gains a `role: str` field — the value (`user.role`) is already computed server-side at every call site, just not returned today.
2. Frontend: the callback page reads that field and branches its redirect; a new `/me/*` route tree (layout + one page) exists as the client-facing landing target, reusing the already-shipped `GET /api/me/action-items` endpoint (`backend/src/api/me.py`) for its first real content.

No client-facing routes exist anywhere in the frontend today (confirmed: only `(app)/*` for HC, `(public)/sign-in`, `auth/callback`). This plan creates the first one.

**Tech stack:** Same as the rest of Unit_004 — FastAPI/SQLAlchemy async backend, Next.js/TypeScript frontend (App Router, `"use client"` pages), Vitest for unit tests, Playwright for E2E. No new dependency of any kind.

## Global Constraints

- Python ≥ 3.12, FastAPI ≥ 0.115, SQLAlchemy ≥ 2.0, Pydantic ≥ 2.7
- Activate the Python env with `source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate` before running backend commands
- Backend tests hit a real PostgreSQL DB (`parivarthan_test`) — no mocking the DB
- This plan does **not** touch `frontend/src/app/(app)/layout.tsx` or any other existing HC-facing route — an HC-side symmetric role-guard (redirecting a client who wanders onto `/dashboard`) is real defense-in-depth but is genuinely adjacent work, not the named bug; flagged as a suggested follow-up in Self-review, not built here
- Follow existing frontend conventions exactly: Tailwind + this app's own design tokens (`font-heading`, `font-sans`, `text-primary`, `text-muted-foreground` etc. — visible throughout `(app)/layout.tsx` and `settings/sessions/page.tsx`), `@/components/ui/button` for buttons, no default styling from a UI library
- Follow existing backend conventions exactly: `ClientClaimsDep`/`TenantDep`/`DbDep` from `src/api/deps.py`, tenant-scoped 404-not-403 on cross-tenant access (already the pattern in `src/api/me.py`)
- No new Alembic migration in this plan — no schema changes

---

## Task 1: `role` field on `/api/auth/refresh` response

**Files:**
- Modify: `backend/src/auth/router.py:36-38` (`TokenResponse`), `backend/src/auth/router.py:351-356` (`refresh_token_endpoint`'s return)
- Test: `backend/tests/integration/test_client_auth.py:188-206` (`test_refresh_preserves_client_role`)

**Interfaces:**
- Produces: `TokenResponse{access_token: str, token_type: str = "bearer", role: str}` — Task 2's frontend change consumes `data.role`.
- Consumes: `user.role` (already loaded in `refresh_token_endpoint`, `backend/src/auth/router.py:335`) — no new query.

- [ ] **Step 1.1: Extend the failing assertion**

In `backend/tests/integration/test_client_auth.py`, extend `test_refresh_preserves_client_role` (currently lines 188–206) to also assert the response body carries the role:

```python
@pytest.mark.asyncio
async def test_refresh_preserves_client_role(http_client, hc_headers, hc_user):
    _, invite_token = await _make_client_and_invite(http_client, hc_headers)
    state = await _start_and_get_state(http_client, invite_token)

    with patch("src.auth.router.exchange_code_for_userinfo", new=AsyncMock(return_value=_FAKE_GOOGLE_USER)):
        login_r = await http_client.get(
            "/api/auth/client/callback",
            params={"code": "fake-google-code", "state": state},
            follow_redirects=False,
        )
    assert login_r.status_code == 302

    refresh_r = await http_client.post("/api/auth/refresh")
    assert refresh_r.status_code == 200

    body = refresh_r.json()
    assert body["role"] == "client"

    claims = decode_access_token(body["access_token"], public_key=get_settings().jwt_public_key)
    assert claims.role == "client"
    assert claims.hc_id == str(hc_user.id)
```

- [ ] **Step 1.2: Run — confirm failure**

Run: `cd backend && pytest tests/integration/test_client_auth.py::test_refresh_preserves_client_role -v`
Expected: FAIL with `KeyError: 'role'`

- [ ] **Step 1.3: Implement**

In `backend/src/auth/router.py`:

```python
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
```

And in `refresh_token_endpoint` (replace the final two lines):

```python
    access_token = create_access_token(
        sub=str(user.id), role=user.role, hc_id=hc_id,
        private_key=settings.jwt_private_key,
    )
    _set_refresh_cookie(response, new_raw)
    return TokenResponse(access_token=access_token, role=user.role)
```

- [ ] **Step 1.4: Run — confirm pass**

Run: `cd backend && pytest tests/integration/test_client_auth.py -v`
Expected: all PASS (this is additive — no existing test asserts an exact/closed response shape; confirmed via grep, none do)

- [ ] **Step 1.5: Full backend suite — confirm no regressions**

Run: `cd backend && pytest -x`
Expected: same pass count as before this change, plus the one now-stronger assertion

- [ ] **Step 1.6: Commit**

```bash
git add backend/src/auth/router.py backend/tests/integration/test_client_auth.py
git commit -m "feat(auth): return role on /api/auth/refresh (PHASE-02a Task 1)"
```

---

## Task 2: Frontend — role-aware redirect on `/auth/callback`

**Files:**
- Modify: `frontend/src/app/auth/callback/page.tsx`
- Test: `frontend/tests/e2e/auth.spec.ts` (extend the existing `describe("auth flows")` block)

**Interfaces:**
- Consumes: `TokenResponse.role` from Task 1 (`"hc" | "client"`, defaults to `"hc"`-shaped behavior if the field is ever absent — see Step 2.3's fallback).
- Produces: nothing new consumed elsewhere; this is the leaf redirect decision.

- [ ] **Step 2.1: Write the failing E2E test**

Add to `frontend/tests/e2e/auth.spec.ts`, inside `test.describe("auth flows", ...)`:

```ts
  test("/auth/callback with a client-role refresh lands on /me", async ({ page }) => {
    await page.route(/localhost:8000\/api\//, async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname === "/api/auth/refresh") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ access_token: "fake-client-token", token_type: "bearer", role: "client" }),
        });
      }
      if (url.pathname === "/api/me/action-items") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ items: [], next_cursor: null }),
        });
      }
      return route.fulfill({ status: 404, body: "" });
    });
    await page.goto("/auth/callback");
    await expect(
      page.getByRole("heading", { name: /your action items/i }),
    ).toBeVisible({ timeout: 10000 });
  });
```

- [ ] **Step 2.2: Run — confirm failure**

Run: `cd frontend && npx playwright test auth.spec.ts -g "lands on /me"`
Expected: FAIL — currently always redirects to `/dashboard`, so the heading never appears (test times out or `/dashboard`'s own auth-guard fetch, un-mocked here, fails first)

- [ ] **Step 2.3: Implement the redirect branch**

Replace the `.then()` handler in `frontend/src/app/auth/callback/page.tsx`:

```tsx
    fetch(`${API_URL}/api/auth/refresh`, { method: "POST", credentials: "include" })
      .then(async (res) => {
        if (!res.ok) throw new Error("refresh failed");
        const data = await res.json();
        setToken(data.access_token);
        router.replace(data.role === "client" ? "/me" : "/dashboard");
      })
      .catch(() => {
        setError("Sign-in failed. Redirecting to sign-in…");
        setTimeout(() => router.replace("/sign-in"), 1800);
      });
```

(Everything else in the file — imports, error state, JSX — is unchanged. `data.role === "client"` is the only new branch; any other value, including the field being absent on some future response shape, falls through to today's `/dashboard` behavior, so this is fully backward compatible.)

- [ ] **Step 2.4: Run — confirm this test passes**

Run: `cd frontend && npx playwright test auth.spec.ts -g "lands on /me"`
Expected: still FAIL at this step — `/me` doesn't exist yet (404 / no matching heading). This is expected; Tasks 3–5 build the page. Leave this test red and move on — it will go green once Task 5 lands.

- [ ] **Step 2.5: Run the full existing auth E2E suite — confirm no regressions**

Run: `cd frontend && npx playwright test auth.spec.ts`
Expected: the pre-existing 6 tests still PASS (their mocked refresh responses have no `role` field, so `data.role === "client"` is `false`, preserving today's `/dashboard` redirect exactly)

- [ ] **Step 2.6: Commit**

```bash
git add frontend/src/app/auth/callback/page.tsx frontend/tests/e2e/auth.spec.ts
git commit -m "feat(auth): branch post-login redirect on role, hc unchanged (PHASE-02a Task 2)"
```

---

## Task 3: Frontend — `frontend/src/lib/api/me.ts` client-facing API wrapper

**Files:**
- Create: `frontend/src/lib/api/me.ts`
- Test: `frontend/tests/unit/me-api.test.ts` (new)

**Interfaces:**
- Consumes: `ActionItemOutSchema`/`ActionItemOut` from `frontend/src/lib/api/actionItems.ts` (exported already, `id/client_id/session_id/hc_user_id/description/due_date/status/completed_at/created_at`), `fetchWithAuth` from `@/lib/auth/client`.
- Produces: `listMyActionItems(): Promise<{items: ActionItemOut[]; next_cursor: string | null}>`, `patchMyActionItem(itemId: string, input: {status: string}): Promise<ActionItemOut>` — Task 5 consumes both.

- [ ] **Step 3.1: Write the failing tests**

```ts
// frontend/tests/unit/me-api.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

beforeEach(() => { vi.resetModules(); });
afterEach(() => { vi.restoreAllMocks(); });

describe("me API wrapper", () => {
  it("listMyActionItems calls GET /api/me/action-items and parses the paginated shape", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        items: [{
          id: "ai-1", client_id: "c-1", session_id: null, hc_user_id: "hc-1",
          description: "Walk 20 min daily", due_date: null, status: "open",
          completed_at: null, created_at: "2026-07-01T00:00:00Z",
        }],
        next_cursor: null,
      }), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { listMyActionItems } = await import("@/lib/api/me");
    const result = await listMyActionItems();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/me/action-items");
    expect(result.items).toHaveLength(1);
    expect(result.items[0].description).toBe("Walk 20 min daily");
  });

  it("listMyActionItems throws on non-ok response", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    vi.doMock("@/lib/auth/client", () => ({
      fetchWithAuth: vi.fn().mockResolvedValue(new Response("", { status: 500 })),
    }));
    const { listMyActionItems } = await import("@/lib/api/me");
    await expect(listMyActionItems()).rejects.toThrow("List my action items failed: 500");
  });

  it("patchMyActionItem PATCHes with the status body and returns the updated item", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        id: "ai-1", client_id: "c-1", session_id: null, hc_user_id: "hc-1",
        description: "Walk 20 min daily", due_date: null, status: "completed",
        completed_at: "2026-07-14T00:00:00Z", created_at: "2026-07-01T00:00:00Z",
      }), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { patchMyActionItem } = await import("@/lib/api/me");
    const result = await patchMyActionItem("ai-1", { status: "completed" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/me/action-items/ai-1",
      { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "completed" }) },
    );
    expect(result.status).toBe("completed");
  });
});
```

- [ ] **Step 3.2: Run — confirm failure**

Run: `cd frontend && npx vitest run tests/unit/me-api.test.ts`
Expected: FAIL — `frontend/src/lib/api/me.ts` doesn't exist

- [ ] **Step 3.3: Implement**

```ts
// frontend/src/lib/api/me.ts
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";
import { ActionItemOutSchema, type ActionItemOut } from "@/lib/api/actionItems";
import { z } from "zod";

const PaginatedActionItemsSchema = z.object({
  items: z.array(ActionItemOutSchema),
  next_cursor: z.string().nullable(),
});

export async function listMyActionItems(): Promise<{ items: ActionItemOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/me/action-items`);
  if (!res.ok) throw new Error(`List my action items failed: ${res.status}`);
  return PaginatedActionItemsSchema.parse(await res.json());
}

export async function patchMyActionItem(
  itemId: string,
  input: { status: string },
): Promise<ActionItemOut> {
  const res = await fetchWithAuth(`${API_URL}/api/me/action-items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Patch my action item failed: ${res.status}`);
  return ActionItemOutSchema.parse(await res.json());
}
```

- [ ] **Step 3.4: Run — confirm pass**

Run: `cd frontend && npx vitest run tests/unit/me-api.test.ts`
Expected: all 3 PASS

- [ ] **Step 3.5: Commit**

```bash
git add frontend/src/lib/api/me.ts frontend/tests/unit/me-api.test.ts
git commit -m "feat(me): client-facing action-items API wrapper (PHASE-02a Task 3)"
```

---

## Task 4: Frontend — `/me/*` layout (auth-guarded client shell)

**Files:**
- Create: `frontend/src/app/me/layout.tsx`

**Interfaces:**
- Consumes: `getToken`/`setToken` from `@/lib/auth/tokens`, `API_URL` from `@/lib/config` — identical shape to `(app)/layout.tsx`'s guard.
- Produces: renders `children` once authed — Task 5's page is the first (and for this plan, only) child.

- [ ] **Step 4.1: Implement**

No new test for this step — it's a direct structural mirror of `(app)/layout.tsx`'s already-tested guard behavior (that file has no dedicated unit test either; it's covered by the E2E suite, same as this will be via Task 2's and Task 5's E2E tests exercising the full mounted tree).

```tsx
// frontend/src/app/me/layout.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL } from "@/lib/config";
import { getToken, setToken } from "@/lib/auth/tokens";

type AuthState = "checking" | "authed" | "denied";

export default function ClientPortalLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [auth, setAuth] = useState<AuthState>("checking");

  useEffect(() => {
    if (getToken()) {
      setAuth("authed");
      return;
    }
    fetch(`${API_URL}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("unauthenticated");
        const data = await res.json();
        setToken(data.access_token);
        setAuth("authed");
      })
      .catch(() => {
        setAuth("denied");
        router.replace("/sign-in");
      });
  }, [router]);

  if (auth === "checking") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-sans text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (auth === "denied") return null;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-background">
        <nav className="mx-auto flex h-12 max-w-2xl items-center px-4 sm:px-6">
          <span className="font-heading text-lg font-black text-foreground">Tapas</span>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-8">
        {children}
      </main>
    </div>
  );
}
```

(No nav links yet, deliberately — `/me/checkins`, `/me/chat`, `/me/diet-chart` don't exist until PHASE-02b/c/d ship. Each of those plans adds its own link here when its route lands, so no link in this header ever points at a 404.)

- [ ] **Step 4.2: Commit**

```bash
git add frontend/src/app/me/layout.tsx
git commit -m "feat(me): client-facing portal shell layout (PHASE-02a Task 4)"
```

---

## Task 5: Frontend — `/me` home page (open action items)

**Files:**
- Create: `frontend/src/app/me/page.tsx`

**Interfaces:**
- Consumes: `listMyActionItems`, `patchMyActionItem` from `@/lib/api/me` (Task 3).
- Produces: the page Task 2's E2E test (`getByRole("heading", { name: /your action items/i })`) asserts against.

- [ ] **Step 5.1: Implement**

```tsx
// frontend/src/app/me/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { listMyActionItems, patchMyActionItem } from "@/lib/api/me";
import type { ActionItemOut } from "@/lib/api/actionItems";

export default function ClientHomePage() {
  const router = useRouter();
  const [items, setItems] = useState<ActionItemOut[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    listMyActionItems()
      .then((data) => setItems(data.items))
      .catch((err) => {
        // A 403 here means a non-client JWT hit a client-only endpoint
        // (wrong account) — treat like any other auth problem.
        if (err instanceof Error && err.message.includes("403")) {
          router.replace("/sign-in");
          return;
        }
        setError(true);
      });
  }, [router]);

  async function handleToggle(item: ActionItemOut) {
    const nextStatus = item.status === "completed" ? "open" : "completed";
    const updated = await patchMyActionItem(item.id, { status: nextStatus });
    setItems((prev) => prev?.map((i) => (i.id === updated.id ? updated : i)) ?? prev);
  }

  const openItems = (items ?? []).filter((i) => i.status !== "completed");

  return (
    <div className="space-y-6">
      <h1 className="font-heading text-3xl font-black text-foreground">
        Your action items
      </h1>

      {error && (
        <p className="font-sans text-sm text-destructive">
          Couldn&rsquo;t load your action items. Try refreshing.
        </p>
      )}

      {!error && items === null && (
        <p className="font-sans text-sm text-muted-foreground">Loading…</p>
      )}

      {!error && items !== null && openItems.length === 0 && (
        <p className="font-sans text-sm text-muted-foreground">
          Nothing open right now — your coach will send new action items after your next session.
        </p>
      )}

      {!error && openItems.length > 0 && (
        <ul className="space-y-3">
          {openItems.map((item) => (
            <li
              key={item.id}
              className="flex items-start justify-between gap-4 rounded-md border p-4"
            >
              <div>
                <p className="font-sans text-sm text-foreground">{item.description}</p>
                {item.due_date && (
                  <p className="mt-1 font-sans text-xs text-muted-foreground">
                    Due {item.due_date}
                  </p>
                )}
              </div>
              <Button size="sm" variant="outline" onClick={() => handleToggle(item)}>
                Mark done
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

(v1 simplification, stated plainly rather than hidden: `GET /api/me/action-items` has no status filter param today — this page fetches the default first page, unfiltered, and filters to non-`completed` client-side. Fine for a first login with a handful of items; pagination/status-filtering is real future work if item counts grow, not needed for this foundation slice.)

- [ ] **Step 5.2: Run Task 2's E2E test — confirm it now passes**

Run: `cd frontend && npx playwright test auth.spec.ts -g "lands on /me"`
Expected: PASS

- [ ] **Step 5.3: Run the full frontend unit + E2E suites — confirm no regressions**

Run: `cd frontend && npx vitest run && npx playwright test`
Expected: all PASS

- [ ] **Step 5.4: Commit**

```bash
git add frontend/src/app/me/page.tsx
git commit -m "feat(me): client home page shows open action items (PHASE-02a Task 5)"
```

---

## Self-review

**Spec coverage:** This plan covers exactly the slice it scoped — D-31's named bug (role-aware redirect) and a real, non-stub `/me` landing page. Check-ins (D-21–D-23), free messaging (D-25), and F8's client-facing diet-chart view are explicitly out of scope, deferred to PHASE-02b/c/d as stated in the Goal section.

**Placeholder scan:** No TBD/TODO. The one "not built here" item (HC-layout symmetric role-guard) is named explicitly as a follow-up, not left vague.

**Type consistency:** `ActionItemOut` is imported from the existing `actionItems.ts`, not redefined — Task 3 and Task 5 both use the identical type, no drift possible. `TokenResponse.role: str` (backend) ↔ `data.role` (frontend, Task 2) ↔ unused-but-present in Task 3/4/5 (they don't need role, only the token) — consistent.

**Known, deliberately out-of-scope items** (for the user to weigh, not silently dropped):
- `frontend/src/app/(app)/layout.tsx` gets no symmetric guard (a client JWT wandering onto `/dashboard` today would 403 against every HC-only endpoint it tries to call, which is safe but produces a confusing broken-page experience rather than a clean redirect). Real, but adjacent — not the named bug.
- The unused, pre-existing `refreshAccessToken()` helper in `frontend/src/lib/api/auth.ts` (dead code — no callers exist; both the callback page and `(app)/layout.tsx` inline their own `fetch` instead) is untouched. Consolidating onto it is a real cleanup opportunity but unrelated to this bug fix.
- `/me`'s home page has no client name/greeting (no existing endpoint returns the client's own profile/name — only the already-scoped-by-JWT action items/moms lists). A "who am I" endpoint is reasonable future scope if PHASE-02b/c/d need one for their own headers; not manufactured here since nothing in this plan needs it.

**Execution handoff:** Two options —

1. **Subagent-driven (recommended)** — a fresh subagent per task, review between tasks, fast iteration
2. **Inline execution** — batch execution in this session with checkpoints between tasks

Which approach?
