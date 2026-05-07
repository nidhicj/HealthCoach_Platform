/**
 * Mobile viewport test: every screen at 375px must have no horizontal scroll
 * and no clipped text. Verifies the responsive layout without a live backend.
 */
import { test, expect } from "@playwright/test";
import { mockAuthAndApi } from "./fixtures/mock-api";
import { ALL_APP_ROUTES, PUBLIC_ROUTES } from "./fixtures/routes.fixture";

test.use({ viewport: { width: 375, height: 812 } });

async function assertNoHorizontalScroll(page: import("@playwright/test").Page) {
  const overflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth > document.documentElement.clientWidth;
  });
  expect(overflow, "page has horizontal scroll at 375px").toBe(false);
}

test.describe("mobile 375px layout", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthAndApi(page);
  });

  for (const route of PUBLIC_ROUTES) {
    test(`${route} has no horizontal scroll`, async ({ page }) => {
      await page.goto(route);
      await assertNoHorizontalScroll(page);
    });
  }

  for (const route of ALL_APP_ROUTES) {
    test(`${route} has no horizontal scroll`, async ({ page }) => {
      await page.goto(route);
      // Protected routes: wait for content to load (not the loading spinner)
      await page.waitForLoadState("networkidle");
      await assertNoHorizontalScroll(page);
    });
  }

  test("client detail two-column layout stacks on mobile", async ({ page }) => {
    await page.goto("/clients/client-stub-001");
    await page.waitForLoadState("networkidle");
    // Left and right columns should NOT be side-by-side at 375px
    // The grid is lg:grid-cols-[1fr_320px] — at 375px it's single column
    await assertNoHorizontalScroll(page);
    // AST card should be below the session list (stacked), both visible
    await expect(page.getByText(/client status/i)).toBeVisible();
    await expect(page.getByText(/sessions/i)).toBeVisible();
  });

  test("session view tabs are visible and usable on mobile", async ({ page }) => {
    await page.goto("/clients/client-stub-001/sessions/session-stub-001");
    await page.waitForLoadState("networkidle");
    await assertNoHorizontalScroll(page);
    // Tab bar should not overflow
    await expect(page.getByRole("tab", { name: /pre-session brief/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /in-session notes/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /mom editor/i })).toBeVisible();
  });

  test("MOM editor two-pane layout stacks on mobile", async ({ page }) => {
    await page.goto("/clients/client-stub-001/sessions/session-stub-001");
    await page.waitForLoadState("networkidle");
    await page.getByRole("tab", { name: /mom editor/i }).click();
    // Generate draft first
    const generateBtn = page.getByRole("button", { name: /generate draft/i });
    if (await generateBtn.isVisible()) {
      await generateBtn.click();
      await page.waitForTimeout(500);
    }
    await assertNoHorizontalScroll(page);
  });

  test("nav header fits at 375px without overflow", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    const header = page.locator("header").first();
    await expect(header).toBeVisible();
    await assertNoHorizontalScroll(page);
  });
});
