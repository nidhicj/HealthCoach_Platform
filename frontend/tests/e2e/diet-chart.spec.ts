/**
 * P6C diet chart e2e tests — template library + client chart editor.
 * All tests run against mocked API; no live backend required.
 *
 * Route override pattern: register per-test routes AFTER mockAuthAndApi so
 * Playwright's LIFO handler ordering gives the override first crack at matching
 * URLs. Call route.fallthrough() to pass through to the catch-all when needed.
 */
import { test, expect, type Page } from "@playwright/test";
import { mockAuthAndApi, STUB_GENERATED_CHART } from "./fixtures/mock-api";
import { STUB_CLIENT_ID } from "./fixtures/routes.fixture";

function emptyTemplates(page: Page) {
  return page.route(/localhost:8000\/api\/diet-charts\/templates$/, (route) => {
    if (route.request().method() === "GET")
      return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    return route.fallthrough();
  });
}

function existingChart(page: Page) {
  return page.route(
    new RegExp(`localhost:8000/api/clients/${STUB_CLIENT_ID}/diet-chart$`),
    (route) => {
      if (route.request().method() === "GET")
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(STUB_GENERATED_CHART),
        });
      return route.fallthrough();
    },
  );
}

test.describe("diet chart template library", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthAndApi(page);
  });

  test("renders Upload, Paste, and Library section headings", async ({ page }) => {
    await page.goto("/settings/diet-chart-templates");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { name: "Templates" })).toBeVisible();
    await expect(page.getByText(/upload a template/i)).toBeVisible();
    await expect(page.getByText(/paste from google sheets/i)).toBeVisible();
    await expect(page.getByText(/library/i).first()).toBeVisible();
  });

  test("library shows empty-state placeholder when no templates", async ({ page }) => {
    await emptyTemplates(page);
    await page.goto("/settings/diet-chart-templates");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/no templates yet/i)).toBeVisible();
  });

  test("library lists template names when templates exist", async ({ page }) => {
    await page.goto("/settings/diet-chart-templates");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Base Weekly Plan")).toBeVisible();
  });

  test("paste form saves template and adds it to the library", async ({ page }) => {
    await emptyTemplates(page);
    await page.goto("/settings/diet-chart-templates");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/no templates yet/i)).toBeVisible();

    await page.getByPlaceholder(/e\.g\. her diet chart/i).fill("Base Weekly Plan");
    await page.getByPlaceholder(/paste your copied cells/i).fill(
      "Day\tBreakfast\tLunch\tDinner\nMonday\tOats\tDal rice\tSabzi roti",
    );
    await page.getByRole("button", { name: /save template/i }).click();

    await expect(page.getByText("Base Weekly Plan")).toBeVisible({ timeout: 5000 });
  });

  test("template row expands to show grid preview and collapses", async ({ page }) => {
    await page.goto("/settings/diet-chart-templates");
    await page.waitForLoadState("networkidle");

    // Column headers only exist in the DOM when the row is expanded
    const breakfastHeader = page.getByRole("columnheader", { name: "Breakfast" });
    await expect(breakfastHeader).not.toBeVisible();

    await page.getByRole("button", { name: /Base Weekly Plan/i }).click();
    await expect(breakfastHeader).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Lunch" })).toBeVisible();

    await page.getByRole("button", { name: /Base Weekly Plan/i }).click();
    await expect(breakfastHeader).not.toBeVisible();
  });

  test("Remove button removes template from library", async ({ page }) => {
    await page.goto("/settings/diet-chart-templates");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Base Weekly Plan")).toBeVisible();

    await page.getByRole("button", { name: /remove/i }).click();

    await expect(page.getByText("Base Weekly Plan")).not.toBeVisible();
    await expect(page.getByText(/no templates yet/i)).toBeVisible();
  });
});

test.describe("client diet chart editor", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthAndApi(page);
  });

  test("shows Generate section with template select when no chart exists", async ({ page }) => {
    await page.goto(`/clients/${STUB_CLIENT_ID}/diet-chart`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: /diet chart/i })).toBeVisible();
    await expect(page.getByText(/generate chart/i)).toBeVisible();
    await expect(page.getByRole("combobox")).toBeVisible();
    await expect(page.getByRole("button", { name: /^generate$/i })).toBeVisible();
  });

  test("Generate button renders the 7-day grid", async ({ page }) => {
    await page.goto(`/clients/${STUB_CLIENT_ID}/diet-chart`);
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /^generate$/i }).click();

    await expect(page.getByText(/7-day grid/i)).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole("button", { name: /save chart/i })).toBeVisible();
    // Meal slot column headers rendered
    await expect(page.getByRole("columnheader", { name: "Breakfast" })).toBeVisible();
    // Day rows rendered (abbreviated)
    await expect(page.getByText("Mon")).toBeVisible();
    await expect(page.getByText("Sun")).toBeVisible();
  });

  test("shows upload link when template library is empty", async ({ page }) => {
    await emptyTemplates(page);
    await page.goto(`/clients/${STUB_CLIENT_ID}/diet-chart`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/no templates in library/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /upload one/i })).toBeVisible();
  });

  test("7-day grid cell inputs are editable when chart exists", async ({ page }) => {
    await existingChart(page);
    await page.goto(`/clients/${STUB_CLIENT_ID}/diet-chart`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText(/7-day grid/i)).toBeVisible();
    // First food input for Monday/Breakfast is pre-filled and editable
    const foodInput = page.getByPlaceholder("Food").first();
    await expect(foodInput).toBeVisible();
    await foodInput.fill("Brown rice porridge");
    await expect(foodInput).toHaveValue("Brown rice porridge");
  });
});
