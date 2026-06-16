/**
 * Core-cycle acceptance test: full HC workflow through the browser UI
 * against mocked API (no live backend required).
 *
 * Happy path: dashboard → client detail → new session →
 *             brief tab → notes tab → MOM tab → generate → send
 */
import { test, expect } from "@playwright/test";
import { mockAuthAndApi } from "./fixtures/mock-api";
import { STUB_CLIENT_ID, STUB_SESSION_ID } from "./fixtures/routes.fixture";

test.beforeEach(async ({ page }) => {
  await mockAuthAndApi(page);
});

test.describe("HC core cycle", () => {
  test("dashboard shows Today and Pending action items sections", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Today" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /pending action items/i })).toBeVisible();
  });

  test("dashboard shows today's session in the Today section", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    // The stub session is scheduled today — it should appear
    await expect(page.getByText(/session 1/i).first()).toBeVisible();
  });

  test("client list shows client name and stage", async ({ page }) => {
    await page.goto("/clients");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Ananya Krishnan")).toBeVisible();
    await expect(page.getByText(/active/i).first()).toBeVisible();
  });

  test("clicking client name navigates to client detail", async ({ page }) => {
    await page.goto("/clients");
    await page.waitForLoadState("networkidle");
    await page.getByText("Ananya Krishnan").click();
    // Wait for client name to appear in heading (detail page)
    await expect(page.getByRole("heading", { name: "Ananya Krishnan" })).toBeVisible({
      timeout: 8000,
    });
  });

  test("client detail shows AST card and session history", async ({ page }) => {
    await page.goto(`/clients/${STUB_CLIENT_ID}`);
    await page.waitForLoadState("networkidle");
    await expect(page.getByText(/client status/i)).toBeVisible();
    await expect(page.getByText(/progressing well/i)).toBeVisible();
    await expect(page.getByRole("link", { name: /new session/i })).toBeVisible();
  });

  test("new session form creates session and navigates to it", async ({ page }) => {
    await page.goto(`/clients/${STUB_CLIENT_ID}/sessions/new`);
    await page.waitForLoadState("networkidle");
    await page.getByLabel(/session number/i).fill("1");
    await page.getByRole("button", { name: /start session/i }).click();
    // After create, session view renders with tabs
    await expect(page.getByRole("tab", { name: /pre-session brief/i })).toBeVisible({
      timeout: 8000,
    });
  });

  test("session view has three tabs: brief, notes, MOM", async ({ page }) => {
    await page.goto(`/clients/${STUB_CLIENT_ID}/sessions/${STUB_SESSION_ID}`);
    await expect(page.getByRole("tab", { name: /pre-session brief/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /in-session notes/i })).toBeVisible();
    await expect(page.getByRole("tab", { name: /mom editor/i })).toBeVisible();
  });

  test("brief tab shows generated brief text", async ({ page }) => {
    await page.goto(`/clients/${STUB_CLIENT_ID}/sessions/${STUB_SESSION_ID}`);
    await expect(page.getByText(/consistent with her morning walks/i)).toBeVisible();
  });

  test("notes tab allows entering session notes", async ({ page }) => {
    await page.goto(`/clients/${STUB_CLIENT_ID}/sessions/${STUB_SESSION_ID}`);
    await page.getByRole("tab", { name: /in-session notes/i }).click();
    const textarea = page.getByPlaceholder(/paste transcript/i);
    await expect(textarea).toBeVisible();
    await textarea.fill("Test session note content");
    // Autosave fires after 800ms — wait for it
    await page.waitForTimeout(1200);
    await expect(page.getByText(/error/i)).not.toBeVisible();
  });

  test("MOM tab: generate draft then send to client", async ({ page }) => {
    await page.goto(`/clients/${STUB_CLIENT_ID}/sessions/${STUB_SESSION_ID}`);
    await page.getByRole("tab", { name: /mom editor/i }).click();

    // Generate draft
    const generateBtn = page.getByRole("button", { name: /generate draft/i });
    await expect(generateBtn).toBeVisible();
    await generateBtn.click();

    // Draft text appears (first match — draft <p> and editable textarea both contain this text)
    await expect(page.getByText(/session summary/i).first()).toBeVisible({ timeout: 5000 });

    // "Send to client" (Marigold) button appears and is clickable
    const sendBtn = page.getByRole("button", { name: /send to client/i });
    await expect(sendBtn).toBeVisible();
    await sendBtn.click();

    // After send: confirmation text appears
    await expect(page.getByText(/mOM sent to client/i)).toBeVisible({ timeout: 5000 });
  });

  test("end session button marks session as ended", async ({ page }) => {
    await page.goto(`/clients/${STUB_CLIENT_ID}/sessions/${STUB_SESSION_ID}`);
    const endBtn = page.getByRole("button", { name: /end session/i });
    await expect(endBtn).toBeVisible();
    await endBtn.click();
    await expect(page.getByText("Ended")).toBeVisible({ timeout: 5000 });
  });
});
