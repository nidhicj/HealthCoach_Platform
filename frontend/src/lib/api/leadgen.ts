import { z } from "zod";
import { fetchWithAuth } from "@/lib/auth/client";
import { API_URL } from "@/lib/config";

const QuestionSchema = z.object({
  key: z.string(),
  text: z.string(),
  type: z.enum(["free_text", "multiple_choice", "scale"]),
  required: z.boolean(),
  removable: z.boolean(),
  options: z.array(z.string()).optional(),
});

const TestPanelSchema = z.object({
  standard_tests: z.array(z.string()),
  condition_rules: z.array(z.object({ keywords: z.array(z.string()), tests: z.array(z.string()) })),
});

export const LeadgenConfigStatusSchema = z.object({
  configured: z.boolean(),
  hc_slug: z.string().nullable().optional(),
  questionnaire: z.array(QuestionSchema).nullable().optional(),
  test_panel: TestPanelSchema.nullable().optional(),
  consultation_fee_inr: z.number().nullable().optional(),
  consultation_duration_min: z.number().nullable().optional(),
  scheduling_link: z.string().nullable().optional(),
  notification_delivery: z.string().nullable().optional(),
  lead_expiry_days: z.number().nullable().optional(),
});
export type LeadgenConfigStatus = z.infer<typeof LeadgenConfigStatusSchema>;

export async function getLeadgenConfig(): Promise<LeadgenConfigStatus> {
  const res = await fetchWithAuth(`${API_URL}/api/leadgen/config`);
  if (!res.ok) throw new Error(`Failed to fetch leadgen config: ${res.status}`);
  return LeadgenConfigStatusSchema.parse(await res.json());
}

export async function initLeadgenConfig(): Promise<LeadgenConfigStatus> {
  const res = await fetchWithAuth(`${API_URL}/api/leadgen/config/init`, { method: "POST", body: "{}" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.message ?? `Failed to initialize leadgen config: ${res.status}`);
  }
  return LeadgenConfigStatusSchema.parse({ configured: true, ...(await res.json()) });
}

export async function patchLeadgenConfig(patch: Record<string, unknown>): Promise<LeadgenConfigStatus> {
  const res = await fetchWithAuth(`${API_URL}/api/leadgen/config`, {
    method: "PATCH",
    body: JSON.stringify(patch),
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`Failed to update leadgen config: ${res.status}`);
  return LeadgenConfigStatusSchema.parse({ configured: true, ...(await res.json()) });
}
