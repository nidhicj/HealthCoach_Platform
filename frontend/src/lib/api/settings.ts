import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const SettingsProfileSchema = z.object({
  business_name: z.string().nullable(),
  first_name: z.string().nullable(),
  last_name: z.string().nullable(),
  display_name: z.string().nullable(),
  photo_url: z.string().nullable(),
  email: z.string(),
});

export type SettingsProfile = z.infer<typeof SettingsProfileSchema>;

// ── api wrappers ─────────────────────────────────────────────────────────────

export async function getProfile(): Promise<SettingsProfile> {
  const res = await fetchWithAuth(`${API_URL}/api/settings/profile`);
  if (!res.ok) throw new Error(`Get profile failed: ${res.status}`);
  return SettingsProfileSchema.parse(await res.json());
}

// `businessName` keeps its existing clearable contract: pass `null` to clear it.
// `firstName`/`lastName` do NOT share that contract — the backend rejects `null`
// and empty/whitespace strings for these two fields with a 422 (they can never be
// cleared back to null via this endpoint once set). Callers must always pass real,
// non-empty, trimmed strings for them; this signature (plain `string`, not
// `string | null`) makes that a type-level expectation, not just a convention.
export async function updateProfile(
  businessName: string | null,
  firstName: string,
  lastName: string,
): Promise<SettingsProfile> {
  const res = await fetchWithAuth(`${API_URL}/api/settings/profile`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      business_name: businessName,
      first_name: firstName,
      last_name: lastName,
    }),
  });
  if (!res.ok) throw new Error(`Update profile failed: ${res.status}`);
  return SettingsProfileSchema.parse(await res.json());
}
