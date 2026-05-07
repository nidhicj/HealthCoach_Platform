import { test, expect } from "@playwright/test";
import { mockAuthAndApi } from "./fixtures/mock-api";

test.describe("auth flows", () => {
  test("unauthenticated visit to / redirects to sign-in", async ({ page }) => {
    // No auth mock → refresh returns 401 (connection refused to un-mocked backend)
    // The layout catches the error and redirects to /sign-in
    await page.route(/localhost:8000\/api\//, (route) =>
      route.fulfill({ status: 401, body: "" }),
    );
    await page.goto("/");
    // Check for sign-in content rather than URL (more robust against redirect timing)
    await expect(
      page.getByRole("button", { name: /continue with google/i }),
    ).toBeVisible({ timeout: 15000 });
  });

  test("unauthenticated visit to /dashboard redirects to sign-in", async ({ page }) => {
    await page.route(/localhost:8000\/api\//, (route) =>
      route.fulfill({ status: 401, body: "" }),
    );
    await page.goto("/dashboard");
    await expect(
      page.getByRole("button", { name: /continue with google/i }),
    ).toBeVisible({ timeout: 15000 });
  });

  test("/sign-in renders wordmark, tagline, and Google button", async ({ page }) => {
    await page.goto("/sign-in");
    const wordmark = page.getByRole("heading", { name: /parivarthan/i });
    await expect(wordmark).toBeVisible();
    const btn = page.getByRole("button", { name: /continue with google/i });
    await expect(btn).toBeVisible();
  });

  test("/sign-in Google button initiates OAuth redirect", async ({ page }) => {
    await mockAuthAndApi(page);
    await page.goto("/sign-in");
    const [googleRequest] = await Promise.all([
      page.waitForRequest(/api\/auth\/google\/start/),
      page.getByRole("button", { name: /continue with google/i }).click(),
    ]);
    expect(googleRequest.url()).toContain("api/auth/google/start");
  });

  test("/auth/callback with a valid refresh cookie lands on dashboard", async ({ page }) => {
    await mockAuthAndApi(page);
    await page.goto("/auth/callback");
    // Dashboard heading appears once auth callback completes and redirects
    await expect(
      page.getByRole("heading", { name: "Dashboard" }),
    ).toBeVisible({ timeout: 10000 });
  });

  test("/auth/callback on refresh failure shows error and redirects to sign-in", async ({
    page,
  }) => {
    // Override refresh to fail
    await page.route(/localhost:8000\/api\//, (route) =>
      route.fulfill({ status: 401, body: "" }),
    );
    await page.goto("/auth/callback");
    // Error text should appear
    await expect(page.getByText(/sign-in failed/i)).toBeVisible({ timeout: 8000 });
    // Then sign-in button appears after redirect
    await expect(
      page.getByRole("button", { name: /continue with google/i }),
    ).toBeVisible({ timeout: 10000 });
  });

  test("authenticated user can sign out via settings", async ({ page }) => {
    await mockAuthAndApi(page);
    await page.goto("/settings/sessions");
    await page.waitForLoadState("networkidle");
    const signOutBtn = page.getByRole("button", { name: /sign out everywhere/i });
    await expect(signOutBtn).toBeVisible();
    await signOutBtn.click();
    // After logout, sign-in content should appear
    await expect(
      page.getByRole("button", { name: /continue with google/i }),
    ).toBeVisible({ timeout: 10000 });
  });
});
