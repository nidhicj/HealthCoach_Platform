import { test, expect } from "@playwright/test";

// Client-role auth mock, mirroring the pattern used by checkins.spec.ts's
// mockClientAuthAndCheckIns() — the shared mockAuthAndApi() fixture only
// mocks HC-side (/api/clients, /api/check-ins) routes, not /api/me/*.
//
// Covers both of /me/chat's sub-tabs (Text + Logged Meals, PHASE-03 Task 12,
// D-26/D-31) since both mount from this one page and this one mock function.
async function mockClientAuthAndMessages(
  page: import("@playwright/test").Page,
  opts: {
    existingMessages: Array<Record<string, unknown>>;
    existingMealLogs?: Array<Record<string, unknown>>;
  },
) {
  const NOW = new Date().toISOString();
  let messages = [...opts.existingMessages];
  let mealLogs = [...(opts.existingMealLogs ?? [])];

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

    if (path === "/api/me/messages" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: messages, next_cursor: null }),
      });
    }

    if (path === "/api/me/messages" && method === "POST") {
      // Sent as multipart/form-data; body field is what matters for this test.
      const bodyText = (req.postData() ?? "").match(/name="body"\r\n\r\n([\s\S]*?)\r\n--/);
      const newMessage = {
        id: `msg-${messages.length + 1}`,
        client_id: "c-1",
        hc_user_id: "hc-1",
        direction: "client",
        body: bodyText ? bodyText[1] : "",
        has_attachment: false,
        attachment_original_filename: null,
        attachment_mime_type: null,
        sent_at: NOW,
      };
      messages = [newMessage, ...messages];
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(newMessage),
      });
    }

    if (path === "/api/me/meal-logs" && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: mealLogs, next_cursor: null }),
      });
    }

    if (path === "/api/me/meal-logs" && method === "POST") {
      // Sent as multipart/form-data; meal_slot/description fields matter for this test.
      const raw = req.postData() ?? "";
      const slotMatch = raw.match(/name="meal_slot"\r\n\r\n([\s\S]*?)\r\n--/);
      const descMatch = raw.match(/name="description"\r\n\r\n([\s\S]*?)\r\n--/);
      const newMealLog = {
        id: `meal-log-${mealLogs.length + 1}`,
        client_id: "c-1",
        hc_user_id: "hc-1",
        meal_slot: slotMatch ? slotMatch[1] : "breakfast",
        description: descMatch ? descMatch[1] : null,
        photo_original_filename: "photo.jpg",
        photo_mime_type: "image/jpeg",
        captured_at: NOW,
        logged_at: NOW,
        hc_reaction: null,
        reacted_at: null,
      };
      mealLogs = [newMealLog, ...mealLogs];
      return route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(newMealLog),
      });
    }

    if (path.startsWith("/api/me/meal-logs/") && path.endsWith("/photo")) {
      // 1x1 transparent PNG, base64-encoded — enough for AuthedImage's fetch-as-blob flow.
      return route.fulfill({
        status: 200,
        contentType: "image/png",
        body: Buffer.from(
          "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
          "base64",
        ),
      });
    }

    return route.fulfill({ status: 404, body: "" });
  });
}

test.describe("client /me/chat", () => {
  // PHASE-02c final-review fix (Finding 5): frontend/src/lib/config.ts's API_URL
  // is "" — all browser calls go to same-origin /api/*, proxied server-side to
  // the real backend by frontend/src/app/api/[...path]/route.ts (the BFF proxy).
  // That server-to-server fetch happens in the Next.js server process, not the
  // browser page, so Playwright's page.route(/localhost:8000\/api\//) here can
  // never intercept it — these mocks are dead on arrival. This is a confirmed
  // pre-existing, environment-wide gap (it affects mock-api.ts's mockAuthAndApi
  // too, used by the rest of the e2e suite), not something introduced by this
  // plan. Marked fixme rather than fixed here so real breakage stays
  // distinguishable from this known infra gap; see PHASE-02c final-fix-report.md.
  test.fixme("sending a message appends it to the thread", async ({ page }) => {
    await mockClientAuthAndMessages(page, { existingMessages: [] });

    await page.goto("/me/chat");

    await expect(page.getByText(/no messages yet/i)).toBeVisible({ timeout: 10000 });

    await page.getByPlaceholder(/type a message/i).fill("Hello coach!");
    await page.getByRole("button", { name: /^send$/i }).click();

    await expect(page.getByText("Hello coach!")).toBeVisible();
    await expect(page.getByText(/no messages yet/i)).not.toBeVisible();
  });

  // Same BFF-proxy/mock-interception gap as above — see the comment on the
  // first test in this describe block.
  test.fixme("with existing messages, shows them on load", async ({ page }) => {
    await mockClientAuthAndMessages(page, {
      existingMessages: [
        {
          id: "msg-0",
          client_id: "c-1",
          hc_user_id: "hc-1",
          direction: "coach",
          body: "Welcome! How can I help?",
          has_attachment: false,
          attachment_original_filename: null,
          attachment_mime_type: null,
          sent_at: "2026-07-25T09:30:00Z",
        },
      ],
    });

    await page.goto("/me/chat");

    await expect(page.getByText("Welcome! How can I help?")).toBeVisible({ timeout: 10000 });
  });

  // Same BFF-proxy/mock-interception gap as above — see the comment on the
  // first test in this describe block. PHASE-03 Task 12 (D-26, D-31): the
  // Logged Meals sub-tab, nested alongside Text in this same page.
  test.fixme(
    "Logged Meals sub-tab: rejects submit with no photo, then logs a meal with one",
    async ({ page }) => {
      await mockClientAuthAndMessages(page, { existingMessages: [], existingMealLogs: [] });

      await page.goto("/me/chat");

      await page.getByRole("tab", { name: "Logged Meals" }).click();

      await expect(page.getByText(/no meals logged yet/i)).toBeVisible({ timeout: 10000 });

      // Submit with no photo attached — inline error, nothing saved.
      await page.getByRole("button", { name: /^log meal$/i }).click();
      await expect(page.getByText(/a photo is required to log a meal/i)).toBeVisible();
      await expect(page.getByText(/no meals logged yet/i)).toBeVisible();

      // Attach a photo and submit — appears under today's day group.
      await page.setInputFiles('input[type="file"]', {
        name: "lunch.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(
          "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
          "base64",
        ),
      });
      await page.getByRole("button", { name: /^log meal$/i }).click();

      await expect(page.getByText(/no meals logged yet/i)).not.toBeVisible();
      await expect(page.getByText("Breakfast", { exact: true })).toBeVisible();
    },
  );
});
