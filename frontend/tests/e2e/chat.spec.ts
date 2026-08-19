import { test, expect } from "@playwright/test";

// Client-role auth mock, mirroring the pattern used by checkins.spec.ts's
// mockClientAuthAndCheckIns() — the shared mockAuthAndApi() fixture only
// mocks HC-side (/api/clients, /api/check-ins) routes, not /api/me/*.
async function mockClientAuthAndMessages(
  page: import("@playwright/test").Page,
  opts: { existingMessages: Array<Record<string, unknown>> },
) {
  const NOW = new Date().toISOString();
  let messages = [...opts.existingMessages];

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

    return route.fulfill({ status: 404, body: "" });
  });
}

test.describe("client /me/chat", () => {
  test("sending a message appends it to the thread", async ({ page }) => {
    await mockClientAuthAndMessages(page, { existingMessages: [] });

    await page.goto("/me/chat");

    await expect(page.getByText(/no messages yet/i)).toBeVisible({ timeout: 10000 });

    await page.getByPlaceholder(/type a message/i).fill("Hello coach!");
    await page.getByRole("button", { name: /^send$/i }).click();

    await expect(page.getByText("Hello coach!")).toBeVisible();
    await expect(page.getByText(/no messages yet/i)).not.toBeVisible();
  });

  test("with existing messages, shows them on load", async ({ page }) => {
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
});
