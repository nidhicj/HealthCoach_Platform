/**
 * fetchWithAuth unit tests.
 *
 * Verifies: Bearer injection, refresh-once-on-401, redirect-on-second-401.
 * Uses vi.stubGlobal to mock fetch and window.location.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Reset the in-memory token module between tests
beforeEach(async () => {
  vi.resetModules();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchWithAuth", () => {
  it("injects Bearer token from memory on first call", async () => {
    // Set a token before importing the module
    vi.doMock("@/lib/auth/tokens", () => ({
      getToken: () => "my-access-token",
      setToken: vi.fn(),
      clearToken: vi.fn(),
    }));
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));

    const fetchMock = vi.fn().mockResolvedValue(
      new Response("{}", { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { fetchWithAuth } = await import("@/lib/auth/client");
    await fetchWithAuth("http://localhost:8000/api/test");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit & { headers: Headers }];
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer my-access-token");
  });

  it("returns response immediately when status is not 401", async () => {
    vi.doMock("@/lib/auth/tokens", () => ({
      getToken: () => "token",
      setToken: vi.fn(),
      clearToken: vi.fn(),
    }));
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));

    const fetchMock = vi.fn().mockResolvedValue(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { fetchWithAuth } = await import("@/lib/auth/client");
    const res = await fetchWithAuth("http://localhost:8000/api/test");

    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("refreshes silently on 401 and retries the request", async () => {
    const setToken = vi.fn();
    vi.doMock("@/lib/auth/tokens", () => ({
      getToken: vi.fn().mockReturnValueOnce("expired").mockReturnValueOnce("fresh"),
      setToken,
      clearToken: vi.fn(),
    }));
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));

    const fetchMock = vi
      .fn()
      // First call: the protected endpoint → 401
      .mockResolvedValueOnce(new Response("", { status: 401 }))
      // Second call: POST /api/auth/refresh → 200 with new token
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: "fresh" }), { status: 200 }),
      )
      // Third call: retry the protected endpoint → 200
      .mockResolvedValueOnce(new Response("ok", { status: 200 }));

    vi.stubGlobal("fetch", fetchMock);

    const { fetchWithAuth } = await import("@/lib/auth/client");
    const res = await fetchWithAuth("http://localhost:8000/api/test");

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(setToken).toHaveBeenCalledWith("fresh");
    expect(res.status).toBe(200);
  });

  it("redirects to /sign-in when refresh also fails (second 401 path)", async () => {
    vi.doMock("@/lib/auth/tokens", () => ({
      getToken: () => "bad-token",
      setToken: vi.fn(),
      clearToken: vi.fn(),
    }));
    vi.doMock("@/lib/config", () => ({ API_URL: "http://localhost:8000" }));

    const fetchMock = vi
      .fn()
      // Protected endpoint → 401
      .mockResolvedValueOnce(new Response("", { status: 401 }))
      // Refresh → also fails
      .mockResolvedValueOnce(new Response("", { status: 401 }));

    vi.stubGlobal("fetch", fetchMock);

    let redirectTarget = "";
    vi.stubGlobal("window", {
      location: {
        get href() { return redirectTarget; },
        set href(val: string) { redirectTarget = val; },
      },
    });

    const { fetchWithAuth } = await import("@/lib/auth/client");
    await fetchWithAuth("http://localhost:8000/api/test");

    expect(redirectTarget).toBe("/sign-in");
  });
});
