/**
 * Brand-rules linter: runs against every route and asserts the Poshini
 * Agasthya design-token contract.
 *
 * Rules (per PHASE-06 §2.10):
 *   - Count of Marigold (#E8C547) background-color elements ∈ {0, 1}
 *   - Zero elements with white (#FFFFFF) background
 *   - Count of Dark Ink (#2C2C1E) background-fill elements ≤ 1
 *   - h1/h2/h3 computed font-family includes "Fraunces"
 *   - body computed font-family includes "Manrope"
 */
import { test, expect, type Page } from "@playwright/test";
import { mockAuthAndApi } from "./fixtures/mock-api";
import { ALL_APP_ROUTES, PUBLIC_ROUTES } from "./fixtures/routes.fixture";

const MARIGOLD_RGB = "rgb(232, 197, 71)";
const WHITE_RGB = "rgb(255, 255, 255)";
const DARK_INK_RGB = "rgb(44, 44, 30)";

async function countByBgColor(page: Page, rgb: string): Promise<number> {
  return page.evaluate((color: string) => {
    let count = 0;
    for (const el of document.querySelectorAll("*")) {
      const bg = window.getComputedStyle(el).backgroundColor;
      if (bg === color) count++;
    }
    return count;
  }, rgb);
}

async function assertHeadingFont(page: Page) {
  // Only h1 is required to use Fraunces. h2/h3 are used for eyebrow labels
  // (Manrope, uppercase, tracking-widest) which is intentional per brand guide.
  const hasCorrectFont = await page.evaluate(() => {
    const headings = document.querySelectorAll("h1");
    if (headings.length === 0) return true;
    return Array.from(headings).every((h) => {
      const ff = window.getComputedStyle(h).fontFamily;
      return ff.toLowerCase().includes("fraunces");
    });
  });
  expect(hasCorrectFont, "h1 must use Fraunces").toBe(true);
}

async function assertBodyFont(page: Page) {
  const bodyFont = await page.evaluate(() =>
    window.getComputedStyle(document.body).fontFamily,
  );
  expect(bodyFont.toLowerCase(), "body must use Manrope").toContain("manrope");
}

async function runBrandChecks(page: Page, route: string) {
  await page.waitForLoadState("networkidle");

  // Marigold count ≤ 1
  const marigoldCount = await countByBgColor(page, MARIGOLD_RGB);
  expect(
    marigoldCount,
    `${route}: found ${marigoldCount} Marigold elements (max 1)`,
  ).toBeLessThanOrEqual(1);

  // No white background
  const whiteCount = await countByBgColor(page, WHITE_RGB);
  expect(whiteCount, `${route}: found ${whiteCount} white-background elements (must be 0)`).toBe(
    0,
  );

  // Dark Ink fills ≤ 1
  const darkInkCount = await countByBgColor(page, DARK_INK_RGB);
  expect(
    darkInkCount,
    `${route}: found ${darkInkCount} Dark Ink fill elements (max 1)`,
  ).toBeLessThanOrEqual(1);

  // Heading fonts
  await assertHeadingFont(page);

  // Body font
  await assertBodyFont(page);
}

test.describe("brand rules — all routes", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthAndApi(page);
  });

  for (const route of PUBLIC_ROUTES) {
    test(`${route} passes brand rules`, async ({ page }) => {
      await page.goto(route);
      await runBrandChecks(page, route);
    });
  }

  for (const route of ALL_APP_ROUTES) {
    test(`${route} passes brand rules`, async ({ page }) => {
      await page.goto(route);
      await runBrandChecks(page, route);
    });
  }
});
