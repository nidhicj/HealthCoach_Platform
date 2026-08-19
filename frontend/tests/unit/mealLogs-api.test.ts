import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

beforeEach(() => { vi.resetModules(); });
afterEach(() => { vi.restoreAllMocks(); });

const mealLogFixture = {
  id: "ml-1",
  client_id: "c-1",
  hc_user_id: "hc-1",
  meal_slot: "lunch",
  description: "Dal, rice, veggies",
  photo_original_filename: "lunch.jpg",
  photo_mime_type: "image/jpeg",
  captured_at: "2026-07-30T12:00:00Z",
  logged_at: "2026-07-30T12:05:00Z",
  hc_reaction: null,
  reacted_at: null,
};

describe("mealLogs API wrapper", () => {
  it("listClientMealLogs calls GET /api/clients/:clientId/meal-logs and parses the paginated shape", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [mealLogFixture], next_cursor: null }), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { listClientMealLogs } = await import("@/lib/api/mealLogs");
    const result = await listClientMealLogs("c-1");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/clients/c-1/meal-logs");
    expect(result.items).toHaveLength(1);
    expect(result.items[0].meal_slot).toBe("lunch");
  });

  it("listClientMealLogs throws on non-ok response", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    vi.doMock("@/lib/auth/client", () => ({
      fetchWithAuth: vi.fn().mockResolvedValue(new Response("", { status: 500 })),
    }));
    const { listClientMealLogs } = await import("@/lib/api/mealLogs");
    await expect(listClientMealLogs("c-1")).rejects.toThrow("List meal logs failed: 500");
  });

  it("reactToMealLog POSTs the reaction body and returns the updated meal log", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ...mealLogFixture, hc_reaction: "happy", reacted_at: "2026-07-30T13:00:00Z" }), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { reactToMealLog } = await import("@/lib/api/mealLogs");
    const result = await reactToMealLog("c-1", "ml-1", "happy");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/clients/c-1/meal-logs/ml-1/react",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reaction: "happy" }) },
    );
    expect(result.hc_reaction).toBe("happy");
  });

  it("reactToMealLog throws on non-ok response", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    vi.doMock("@/lib/auth/client", () => ({
      fetchWithAuth: vi.fn().mockResolvedValue(new Response("", { status: 500 })),
    }));
    const { reactToMealLog } = await import("@/lib/api/mealLogs");
    await expect(reactToMealLog("c-1", "ml-1", "happy")).rejects.toThrow("React to meal log failed: 500");
  });

  it("mealLogPhotoUrl builds the HC-side photo URL", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const { mealLogPhotoUrl } = await import("@/lib/api/mealLogs");
    expect(mealLogPhotoUrl("c-1", "ml-1")).toBe("http://localhost:8000/api/clients/c-1/meal-logs/ml-1/photo");
  });

  it("listMyMealLogs calls GET /api/me/meal-logs and parses the paginated shape", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [mealLogFixture], next_cursor: null }), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { listMyMealLogs } = await import("@/lib/api/mealLogs");
    const result = await listMyMealLogs();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/me/meal-logs");
    expect(result.items).toHaveLength(1);
    expect(result.items[0].id).toBe("ml-1");
  });

  it("listMyMealLogs throws on non-ok response", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    vi.doMock("@/lib/auth/client", () => ({
      fetchWithAuth: vi.fn().mockResolvedValue(new Response("", { status: 500 })),
    }));
    const { listMyMealLogs } = await import("@/lib/api/mealLogs");
    await expect(listMyMealLogs()).rejects.toThrow("List my meal logs failed: 500");
  });

  it("submitMyMealLog POSTs a multipart form with meal_slot, description, and photo", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mealLogFixture), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { submitMyMealLog } = await import("@/lib/api/mealLogs");
    const photo = new File(["fake-bytes"], "lunch.jpg", { type: "image/jpeg" });
    const result = await submitMyMealLog({ mealSlot: "lunch", description: "Dal, rice, veggies", photo });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/me/meal-logs");
    expect(init.method).toBe("POST");
    const form = init.body as FormData;
    expect(form.get("meal_slot")).toBe("lunch");
    expect(form.get("description")).toBe("Dal, rice, veggies");
    expect(form.get("photo")).toBe(photo);
    expect(result.id).toBe("ml-1");
  });

  it("submitMyMealLog omits description when not provided", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(mealLogFixture), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { submitMyMealLog } = await import("@/lib/api/mealLogs");
    const photo = new File(["fake-bytes"], "lunch.jpg", { type: "image/jpeg" });
    await submitMyMealLog({ mealSlot: "breakfast", photo });

    const [, init] = fetchMock.mock.calls[0];
    const form = init.body as FormData;
    expect(form.has("description")).toBe(false);
    expect(form.get("meal_slot")).toBe("breakfast");
  });

  it("submitMyMealLog throws on non-ok response", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    vi.doMock("@/lib/auth/client", () => ({
      fetchWithAuth: vi.fn().mockResolvedValue(new Response("", { status: 500 })),
    }));
    const { submitMyMealLog } = await import("@/lib/api/mealLogs");
    const photo = new File(["fake-bytes"], "lunch.jpg", { type: "image/jpeg" });
    await expect(submitMyMealLog({ mealSlot: "lunch", photo })).rejects.toThrow("Submit meal log failed: 500");
  });

  it("myMealLogPhotoUrl builds the client-side photo URL", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const { myMealLogPhotoUrl } = await import("@/lib/api/mealLogs");
    expect(myMealLogPhotoUrl("ml-1")).toBe("http://localhost:8000/api/me/meal-logs/ml-1/photo");
  });
});
