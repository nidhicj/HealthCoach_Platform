import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";
import { clearToken, setToken } from "@/lib/auth/tokens";

// ── schemas ──────────────────────────────────────────────────────────────────

const TokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
});

// Note: GET /api/auth/sessions and DELETE /api/auth/sessions/{id} are defined in
// ADR-0005 §11 but not yet implemented in the backend. Schemas are declared here
// for when they ship (settings screen). The wrappers are commented out below.

// ── public (no Bearer required) ─────────────────────────────────────────────

export async function refreshAccessToken(): Promise<string> {
  const res = await fetch(`${API_URL}/api/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Token refresh failed");
  const data = TokenResponseSchema.parse(await res.json());
  setToken(data.access_token);
  return data.access_token;
}

export async function logout(): Promise<void> {
  await fetch(`${API_URL}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
  clearToken();
}

// ── authenticated ────────────────────────────────────────────────────────────

// Placeholder for when GET /api/auth/sessions ships in the backend.
// export async function listAuthSessions() { ... }
// export async function revokeAuthSession(id: string) { ... }

export async function revokeAuthSession(id: string): Promise<void> {
  const res = await fetchWithAuth(`${API_URL}/api/auth/sessions/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to revoke session");
}
