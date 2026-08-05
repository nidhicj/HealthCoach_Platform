import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const SettingsProfileSchema = z.object({
  business_name: z.string().nullable(),
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

export async function updateProfile(businessName: string | null): Promise<SettingsProfile> {
  const res = await fetchWithAuth(`${API_URL}/api/settings/profile`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ business_name: businessName }),
  });
  if (!res.ok) throw new Error(`Update profile failed: ${res.status}`);
  return SettingsProfileSchema.parse(await res.json());
}
