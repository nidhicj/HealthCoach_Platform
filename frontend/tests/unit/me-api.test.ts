import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

beforeEach(() => { vi.resetModules(); });
afterEach(() => { vi.restoreAllMocks(); });

describe("me API wrapper", () => {
  it("listMyActionItems calls GET /api/me/action-items and parses the paginated shape", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        items: [{
          id: "ai-1", client_id: "c-1", session_id: null, hc_user_id: "hc-1",
          description: "Walk 20 min daily", due_date: null, status: "open",
          completed_at: null, created_at: "2026-07-01T00:00:00Z",
        }],
        next_cursor: null,
      }), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { listMyActionItems } = await import("@/lib/api/me");
    const result = await listMyActionItems();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/me/action-items");
    expect(result.items).toHaveLength(1);
    expect(result.items[0].description).toBe("Walk 20 min daily");
  });

  it("listMyActionItems throws on non-ok response", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    vi.doMock("@/lib/auth/client", () => ({
      fetchWithAuth: vi.fn().mockResolvedValue(new Response("", { status: 500 })),
    }));
    const { listMyActionItems } = await import("@/lib/api/me");
    await expect(listMyActionItems()).rejects.toThrow("List my action items failed: 500");
  });

  it("patchMyActionItem PATCHes with the status body and returns the updated item", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        id: "ai-1", client_id: "c-1", session_id: null, hc_user_id: "hc-1",
        description: "Walk 20 min daily", due_date: null, status: "completed",
        completed_at: "2026-07-14T00:00:00Z", created_at: "2026-07-01T00:00:00Z",
      }), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { patchMyActionItem } = await import("@/lib/api/me");
    const result = await patchMyActionItem("ai-1", { status: "completed" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/me/action-items/ai-1",
      { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "completed" }) },
    );
    expect(result.status).toBe("completed");
  });

  it("listMyCheckIns calls GET /api/me/check-ins and parses the paginated shape", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        items: [{
          id: "cin-1", client_id: "c-1", hc_user_id: "hc-1",
          payload: { mood: "good" }, requested_at: "2026-07-30T12:00:00Z",
          sentiment_flag: null, created_at: "2026-07-30T12:00:00Z",
        }],
        next_cursor: null,
      }), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { listMyCheckIns } = await import("@/lib/api/me");
    const result = await listMyCheckIns();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/me/check-ins");
    expect(result.items).toHaveLength(1);
    expect(result.items[0].payload).toEqual({ mood: "good" });
  });

  it("listMyCheckIns throws on non-ok response", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    vi.doMock("@/lib/auth/client", () => ({
      fetchWithAuth: vi.fn().mockResolvedValue(new Response("", { status: 500 })),
    }));
    const { listMyCheckIns } = await import("@/lib/api/me");
    await expect(listMyCheckIns()).rejects.toThrow("List my check-ins failed: 500");
  });

  it("submitMyCheckIn POSTs the payload to /api/me/check-ins and returns CheckInOut", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        id: "cin-1", client_id: "c-1", hc_user_id: "hc-1",
        payload: { mood: "good" }, requested_at: "2026-07-30T12:00:00Z",
        sentiment_flag: null, created_at: "2026-07-30T12:00:00Z",
      }), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { submitMyCheckIn } = await import("@/lib/api/me");
    const result = await submitMyCheckIn({ mood: "good" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/me/check-ins",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ payload: { mood: "good" } }) },
    );
    expect(result.payload).toEqual({ mood: "good" });
  });

  it("submitMyCheckIn throws on non-ok response", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    vi.doMock("@/lib/auth/client", () => ({
      fetchWithAuth: vi.fn().mockResolvedValue(new Response("", { status: 500 })),
    }));
    const { submitMyCheckIn } = await import("@/lib/api/me");
    await expect(submitMyCheckIn({})).rejects.toThrow("Submit check-in failed: 500");
  });
});
