import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const DietChartOutSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  parameters: z.record(z.string(), z.unknown()).nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const GenerateResponseSchema = z.object({
  chart: DietChartOutSchema,
  generation_status: z.string(),
});

export type DietChartOut = z.infer<typeof DietChartOutSchema>;

// ── api wrappers ─────────────────────────────────────────────────────────────

export async function uploadTemplate(file: File): Promise<DietChartOut> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetchWithAuth(`${API_URL}/api/diet-charts/templates/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return DietChartOutSchema.parse(await res.json());
}

export async function listTemplates(): Promise<DietChartOut[]> {
  const res = await fetchWithAuth(`${API_URL}/api/diet-charts/templates`);
  if (!res.ok) throw new Error(`List templates failed: ${res.status}`);
  return z.array(DietChartOutSchema).parse(await res.json());
}

export async function deleteTemplate(templateId: string): Promise<void> {
  const res = await fetchWithAuth(
    `${API_URL}/api/diet-charts/templates/${templateId}`,
    { method: "DELETE" },
  );
  if (!res.ok) throw new Error(`Delete template failed: ${res.status}`);
}

export async function getClientDietChart(clientId: string): Promise<DietChartOut | null> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/diet-chart`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Get diet chart failed: ${res.status}`);
  return DietChartOutSchema.parse(await res.json());
}

export async function generateDietChart(
  clientId: string,
  input: { template_id: string; modifications?: string },
): Promise<{ chart: DietChartOut; generation_status: string }> {
  const res = await fetchWithAuth(
    `${API_URL}/api/clients/${clientId}/diet-chart/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
  if (!res.ok) throw new Error(`Generate diet chart failed: ${res.status}`);
  return GenerateResponseSchema.parse(await res.json());
}

export async function patchDietChart(
  clientId: string,
  parameters: Record<string, unknown>,
): Promise<DietChartOut> {
  const res = await fetchWithAuth(
    `${API_URL}/api/clients/${clientId}/diet-chart`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parameters }),
    },
  );
  if (!res.ok) throw new Error(`Patch diet chart failed: ${res.status}`);
  return DietChartOutSchema.parse(await res.json());
}
