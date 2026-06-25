import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const SupplementOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  dosage: z.string().nullable(),
  duration_days: z.number().nullable(),
  recommended_at: z.string(),
  notes: z.string().nullable(),
  created_at: z.string(),
});

export type SupplementOut = z.infer<typeof SupplementOutSchema>;

export interface SupplementCreateInput {
  name: string;
  dosage?: string | null;
  duration_days?: number | null;
  recommended_at?: string;
  notes?: string | null;
}

export interface SupplementPatchInput {
  name?: string;
  dosage?: string | null;
  duration_days?: number | null;
  recommended_at?: string;
  notes?: string | null;
}

// ── API calls ────────────────────────────────────────────────────────────────

export async function listSupplements(clientId: string): Promise<SupplementOut[]> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/supplements`);
  if (!res.ok) throw new Error("Failed to fetch supplements");
  return z.array(SupplementOutSchema).parse(await res.json());
}

export async function createSupplement(
  clientId: string,
  data: SupplementCreateInput,
): Promise<SupplementOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/supplements`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create supplement");
  return SupplementOutSchema.parse(await res.json());
}

export async function patchSupplement(
  clientId: string,
  supplementId: string,
  data: SupplementPatchInput,
): Promise<SupplementOut> {
  const res = await fetchWithAuth(
    `${API_URL}/api/clients/${clientId}/supplements/${supplementId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );
  if (!res.ok) throw new Error("Failed to update supplement");
  return SupplementOutSchema.parse(await res.json());
}

export async function deleteSupplement(
  clientId: string,
  supplementId: string,
): Promise<void> {
  const res = await fetchWithAuth(
    `${API_URL}/api/clients/${clientId}/supplements/${supplementId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error("Failed to delete supplement");
}
