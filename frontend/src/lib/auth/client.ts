import { API_URL } from "@/lib/config";
import { clearToken, getToken, setToken } from "@/lib/auth/tokens";

export async function silentRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) {
      clearToken();
      return false;
    }
    const data = await res.json();
    setToken(data.access_token);
    return true;
  } catch {
    clearToken();
    return false;
  }
}

// Wraps fetch with:
//  1. Injects Bearer token from memory
//  2. On 401: refreshes once silently, retries
//  3. On second 401: clears token and redirects to /sign-in
export async function fetchWithAuth(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const makeHeaders = (token: string | null): Headers => {
    const headers = new Headers(init.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return headers;
  };

  const res = await fetch(input, {
    ...init,
    headers: makeHeaders(getToken()),
    credentials: "include",
  });

  if (res.status !== 401) return res;

  const refreshed = await silentRefresh();
  if (!refreshed) {
    if (typeof window !== "undefined") {
      window.location.href = "/sign-in";
    }
    return res;
  }

  return fetch(input, {
    ...init,
    headers: makeHeaders(getToken()),
    credentials: "include",
  });
}
