import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

beforeEach(() => { vi.resetModules(); });
afterEach(() => { vi.restoreAllMocks(); });

describe("checkIns API wrapper", () => {
  it("requestCheckIn POSTs to /api/clients/{clientId}/check-ins/request and returns CheckInOut", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({
        id: "cin-1",
        client_id: "c-1",
        hc_user_id: "hc-1",
        payload: null,
        requested_at: "2026-07-30T12:00:00Z",
        sentiment_flag: null,
        created_at: "2026-07-30T12:00:00Z",
      }), { status: 200 }),
    );
    vi.doMock("@/lib/auth/client", () => ({ fetchWithAuth: fetchMock }));

    const { requestCheckIn } = await import("@/lib/api/checkIns");
    const result = await requestCheckIn("c-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/clients/c-1/check-ins/request",
      { method: "POST" },
    );
    expect(result.id).toBe("cin-1");
    expect(result.requested_at).toBe("2026-07-30T12:00:00Z");
  });

  it("requestCheckIn throws on non-ok response", async () => {
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));
    vi.doMock("@/lib/auth/client", () => ({
      fetchWithAuth: vi.fn().mockResolvedValue(new Response("", { status: 500 })),
    }));
    const { requestCheckIn } = await import("@/lib/api/checkIns");
    await expect(requestCheckIn("c-1")).rejects.toThrow("Request check-in failed: 500");
  });
});
