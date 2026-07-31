import { test, expect } from "@playwright/test";

// Client-role auth mock, mirroring the pattern used by the
// "/auth/callback with a client-role refresh lands on /me" test in
// auth.spec.ts — the shared mockAuthAndApi() fixture only mocks HC-side
// (/api/clients, /api/check-ins) routes, not /api/me/*.
async function mockClientAuthAndCheckIns(
  page: import("@playwright/test").Page,
  opts: { pendingRequestedAt: string | null },
) {
  const NOW = new Date().toISOString();

  await page.route(/localhost:8000\/api\//, async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path === "/api/auth/refresh") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          access_token: "fake-client-token",
          token_type: "bearer",
          role: "client",
        }),
      });
    }

    if (path === "/api/me/check-ins" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: opts.pendingRequestedAt
            ? [
                {
                  id: "cin-1",
                  client_id: "c-1",
                  hc_user_id: "hc-1",
                  payload: null,
                  requested_at: opts.pendingRequestedAt,
                  sentiment_flag: null,
                  created_at: opts.pendingRequestedAt,
                },
              ]
            : [],
          next_cursor: null,
        }),
      });
    }

    if (path === "/api/me/check-ins" && method === "POST") {
      const body = JSON.parse(req.postData() ?? "{}");
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "cin-1",
          client_id: "c-1",
          hc_user_id: "hc-1",
          payload: body.payload,
          requested_at: opts.pendingRequestedAt,
          sentiment_flag: null,
          created_at: NOW,
        }),
      });
    }

    return route.fulfill({ status: 404, body: "" });
  });
}

test.describe("client /me/checkins", () => {
  test("answering a pending check-in clears the banner and adds it to history", async ({ page }) => {
    await mockClientAuthAndCheckIns(page, { pendingRequestedAt: "2026-07-25T09:30:00Z" });

    await page.goto("/me/checkins");

    await expect(page.getByText(/your coach asked for a check-in/i)).toBeVisible({ timeout: 10000 });

    await page.getByRole("button", { name: "Energy levels", exact: true }).click();
    await page.getByRole("button", { name: "Sleep quality", exact: true }).click();
    await page.getByRole("button", { name: "Mood", exact: true }).click();

    const submitBtn = page.getByRole("button", { name: /submit check-in/i });
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Pending banner disappears; "nothing to answer" message shows instead.
    await expect(page.getByText(/your coach asked for a check-in/i)).not.toBeVisible();
    await expect(page.getByText(/nothing to answer right now/i)).toBeVisible();

    // The answered check-in now appears under "Past check-ins".
    await expect(page.locator("pre")).toContainText("Energy levels");
  });

  test("with nothing pending, shows the empty state and no banner", async ({ page }) => {
    await mockClientAuthAndCheckIns(page, { pendingRequestedAt: null });

    await page.goto("/me/checkins");

    await expect(page.getByText(/nothing to answer right now/i)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/your coach asked for a check-in/i)).not.toBeVisible();
  });
});
