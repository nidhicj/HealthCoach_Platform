/**
 * Playwright route mocks for all backend API calls.
 *
 * Uses a single catch-all handler that dispatches by pathname — this avoids
 * glob-vs-query-string ambiguity (Playwright globs don't match ?params without
 * a trailing ** wildcard, so a single regex handler is more reliable).
 */
import type { Page } from "@playwright/test";
import { STUB_CLIENT_ID, STUB_SESSION_ID, STUB_TEMPLATE_ID } from "./routes.fixture";

const FAKE_TOKEN = "fake-access-token-for-e2e";
const NOW = new Date().toISOString();

// Use today's ISO string for scheduled_at so it shows up in "Today" section
const TODAY = new Date().toISOString();

const STUB_CLIENT = {
  id: STUB_CLIENT_ID,
  hc_user_id: "hc-001",
  code: "CLI001",
  full_name: "Ananya Krishnan",
  email: "ananya@example.com",
  phone: "+91 98765 43210",
  timezone: null,
  journey_stage: "active",
  course_start_date: null,
  course_end_date: null,
  course_goal: "Build a sustainable routine",
  created_at: NOW,
  updated_at: NOW,
  // ClientDetailOut extras (returned by GET /api/clients/:id)
  ast: null,
  open_action_items_count: 0,
  last_session_at: null,
};

const STUB_SESSION = {
  id: STUB_SESSION_ID,
  hc_user_id: "hc-001",
  client_id: STUB_CLIENT_ID,
  session_number: 1,
  scheduled_at: TODAY,
  started_at: null,
  ended_at: null,
  zoom_meeting_id: null,
  notes_internal: null,
  session_notes: null,
  created_at: NOW,
};

const STUB_AST = {
  triage_flags: [],
  status_summary: "Client is progressing well. Last check-in 3 days ago.",
  trend_tags: [],
  open_items: [],
  missed_items: [],
};

export const STUB_TEMPLATE = {
  id: STUB_TEMPLATE_ID,
  name: "Base Weekly Plan",
  description: null,
  parameters: {
    meal_slots: ["Breakfast", "Lunch", "Dinner"],
    grid: {
      Monday: {
        Breakfast: { food: "Oats", timing: "8am" },
        Lunch: { food: "Dal rice", timing: "1pm" },
        Dinner: { food: "Sabzi roti", timing: "8pm" },
      },
    },
    is_template: true,
  },
  created_at: NOW,
  updated_at: NOW,
};

export const STUB_GENERATED_CHART = {
  id: "dc-stub-001",
  name: "Ananya's diet plan",
  description: null,
  parameters: {
    meal_slots: ["Breakfast", "Lunch", "Dinner"],
    grid: {
      Monday: { Breakfast: { food: "Poha", timing: "8am" }, Lunch: { food: "Dal rice", timing: "1pm" }, Dinner: { food: "Sabzi chapati", timing: "8pm" } },
      Tuesday: { Breakfast: { food: "Upma", timing: "8am" }, Lunch: { food: "Rajma rice", timing: "1pm" }, Dinner: { food: "Khichdi", timing: "8pm" } },
      Wednesday: { Breakfast: { food: "Idli", timing: "8am" }, Lunch: { food: "Chole rice", timing: "1pm" }, Dinner: { food: "Roti sabzi", timing: "8pm" } },
      Thursday: { Breakfast: { food: "Dosa", timing: "8am" }, Lunch: { food: "Dal tadka", timing: "1pm" }, Dinner: { food: "Paneer roti", timing: "8pm" } },
      Friday: { Breakfast: { food: "Paratha", timing: "8am" }, Lunch: { food: "Pulao", timing: "1pm" }, Dinner: { food: "Soup salad", timing: "8pm" } },
      Saturday: { Breakfast: { food: "Poha", timing: "9am" }, Lunch: { food: "Biryani", timing: "2pm" }, Dinner: { food: "Dal roti", timing: "8pm" } },
      Sunday: { Breakfast: { food: "Aloo paratha", timing: "9am" }, Lunch: { food: "Chole bhature", timing: "1pm" }, Dinner: { food: "Khichdi", timing: "8pm" } },
    },
    is_template: false,
  },
  created_at: NOW,
  updated_at: NOW,
};

const STUB_BRIEF = {
  id: "brief-001",
  session_id: STUB_SESSION_ID,
  client_id: STUB_CLIENT_ID,
  brief_text:
    "Ananya has been consistent with her morning walks. Key focus this session: review nutrition habits and set week 3 targets.",
  triage_flags: [],
  llm_call_id: "llm-001",
  generated_at: NOW,
};

const STUB_MOM = {
  id: "mom-001",
  session_id: STUB_SESSION_ID,
  client_id: STUB_CLIENT_ID,
  draft_text: "Session summary: Reviewed week 2 progress. Targets for week 3 agreed.",
  final_text: null,
  status: "draft",
  llm_call_id: "llm-002",
  sent_at: null,
  created_at: NOW,
  updated_at: NOW,
};

function jsonOk(body: unknown, status = 200) {
  return {
    status,
    contentType: "application/json",
    headers: {
      "Access-Control-Allow-Origin": "http://localhost:3000",
      "Access-Control-Allow-Credentials": "true",
    },
    body: JSON.stringify(body),
  };
}

export async function mockAuthAndApi(page: Page) {
  // Single catch-all for all API traffic — dispatches by pathname.
  // This correctly handles requests with query strings (?limit=20, etc.)
  await page.route(/localhost:8000\/api\//, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    // ── auth ─────────────────────────────────────────────────────────────────
    if (path === "/api/auth/refresh") {
      return route.fulfill(
        jsonOk({ access_token: FAKE_TOKEN, token_type: "bearer" }),
      );
    }
    if (path === "/api/auth/logout") {
      return route.fulfill(jsonOk({}));
    }
    if (path === "/api/auth/sessions") {
      if (method === "GET") return route.fulfill(jsonOk([]));
    }
    if (path === "/api/auth/google/start") {
      return route.fulfill(
        jsonOk({ auth_url: "https://accounts.google.com/o/oauth2/auth?stub=1" }),
      );
    }

    // ── clients ───────────────────────────────────────────────────────────────
    if (path === "/api/clients") {
      if (method === "GET")
        return route.fulfill(jsonOk({ items: [STUB_CLIENT], next_cursor: null }));
      if (method === "POST")
        return route.fulfill(jsonOk(STUB_CLIENT, 201));
    }
    if (path === `/api/clients/${STUB_CLIENT_ID}/ast`) {
      return route.fulfill(jsonOk(STUB_AST));
    }
    if (path === `/api/clients/${STUB_CLIENT_ID}/invite`) {
      return route.fulfill(
        jsonOk({ invite_token: "tok", expires_at: NOW, invite_url: "https://example.com" }, 201),
      );
    }
    if (path === `/api/clients/${STUB_CLIENT_ID}`) {
      return route.fulfill(jsonOk(STUB_CLIENT));
    }

    // ── sessions ──────────────────────────────────────────────────────────────
    if (path === "/api/sessions") {
      if (method === "GET")
        return route.fulfill(jsonOk({ items: [STUB_SESSION], next_cursor: null }));
      if (method === "POST")
        return route.fulfill(jsonOk(STUB_SESSION, 201));
    }
    if (path === `/api/sessions/${STUB_SESSION_ID}/brief`) {
      return route.fulfill(jsonOk(STUB_BRIEF));
    }
    if (path === `/api/sessions/${STUB_SESSION_ID}/mom/draft`) {
      return route.fulfill(jsonOk(STUB_MOM));
    }
    if (path === `/api/sessions/${STUB_SESSION_ID}/mom/send`) {
      return route.fulfill(jsonOk({ ...STUB_MOM, status: "sent", sent_at: NOW }));
    }
    if (path === `/api/sessions/${STUB_SESSION_ID}/mom`) {
      if (method === "GET") return route.fulfill({ status: 404, body: "" });
      if (method === "PATCH") {
        const body = JSON.parse(req.postData() ?? "{}");
        return route.fulfill(jsonOk({ ...STUB_MOM, ...body }));
      }
    }
    if (path === `/api/sessions/${STUB_SESSION_ID}/files`) {
      if (method === "GET") return route.fulfill(jsonOk([]));
      return route.fulfill(jsonOk([], 201));
    }
    if (path === `/api/sessions/${STUB_SESSION_ID}/end`) {
      return route.fulfill(jsonOk({ ...STUB_SESSION, ended_at: NOW }));
    }
    if (path === `/api/sessions/${STUB_SESSION_ID}`) {
      if (method === "GET") return route.fulfill(jsonOk(STUB_SESSION));
      if (method === "PATCH") {
        const body = JSON.parse(req.postData() ?? "{}");
        return route.fulfill(jsonOk({ ...STUB_SESSION, ...body }));
      }
    }

    // ── action items ──────────────────────────────────────────────────────────
    if (path === "/api/action-items") {
      if (method === "GET")
        return route.fulfill(jsonOk({ items: [], next_cursor: null }));
      if (method === "POST")
        return route.fulfill(jsonOk({ id: "ai-1", description: "test", status: "open", client_id: STUB_CLIENT_ID, session_id: null, hc_user_id: "hc-001", due_date: null, completed_at: null, created_at: NOW }, 201));
    }

    // ── check-ins ─────────────────────────────────────────────────────────────
    if (path.startsWith("/api/check-ins") || path.startsWith("/api/clients/") && path.includes("/check-ins")) {
      return route.fulfill(jsonOk({ items: [], next_cursor: null }));
    }

    // ── diet chart templates ──────────────────────────────────────────────────
    if (path === "/api/diet-charts/templates") {
      if (method === "GET") return route.fulfill(jsonOk([STUB_TEMPLATE]));
    }
    if (path === "/api/diet-charts/templates/paste") {
      return route.fulfill(jsonOk(STUB_TEMPLATE, 201));
    }
    if (path.startsWith("/api/diet-charts/templates/") && method === "DELETE") {
      return route.fulfill({ status: 204, body: "" });
    }

    // ── client diet chart ─────────────────────────────────────────────────────
    // GET returns 404 (no chart yet); PATCH returns updated chart.
    // generate returns STUB_GENERATED_CHART. All keep Promise.all from rejecting.
    if (path === `/api/clients/${STUB_CLIENT_ID}/diet-chart/generate`) {
      return route.fulfill(jsonOk({ chart: STUB_GENERATED_CHART, generation_status: "success" }));
    }
    if (path === `/api/clients/${STUB_CLIENT_ID}/diet-chart`) {
      if (method === "GET") return route.fulfill({ status: 404, body: "" });
      if (method === "PATCH") {
        const body = JSON.parse(req.postData() ?? "{}");
        return route.fulfill(jsonOk({
          ...STUB_GENERATED_CHART,
          parameters: body.parameters ?? STUB_GENERATED_CHART.parameters,
        }));
      }
    }

    // Fallthrough — let anything else hit the network (shouldn't happen in tests)
    return route.continue();
  });
}
