// All routes that need auth mocked + brand-rules checked.
// Add new routes here as screens are added.

export const PUBLIC_ROUTES = ["/sign-in"] as const;

export const APP_ROUTES = [
  "/dashboard",
  "/clients",
  "/clients/new",
  "/action-items",
  "/settings/sessions",
  "/settings/diet-chart-templates",
] as const;

// Dynamic routes: stub IDs that the mock API will recognise.
export const STUB_CLIENT_ID = "client-stub-001";
export const STUB_SESSION_ID = "session-stub-001";
export const STUB_TEMPLATE_ID = "template-stub-001";

export const DYNAMIC_APP_ROUTES = [
  `/clients/${STUB_CLIENT_ID}`,
  `/clients/${STUB_CLIENT_ID}/diet-chart`,
  `/clients/${STUB_CLIENT_ID}/sessions/new`,
  `/clients/${STUB_CLIENT_ID}/sessions/${STUB_SESSION_ID}`,
] as const;

export const ALL_APP_ROUTES = [...APP_ROUTES, ...DYNAMIC_APP_ROUTES] as const;
