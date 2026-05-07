import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const CheckInOutSchema = z.object({
  id: z.string(),
  client_id: z.string(),
  hc_user_id: z.string(),
  payload: z.record(z.string(), z.unknown()),
  sentiment_flag: z.string().nullable(),
  created_at: z.string(),
});

const PaginatedCheckInsSchema = z.object({
  items: z.array(CheckInOutSchema),
  next_cursor: z.string().nullable(),
});

export type CheckInOut = z.infer<typeof CheckInOutSchema>;

// ── api wrappers ─────────────────────────────────────────────────────────────

export async function listClientCheckIns(
  clientId: string,
  params?: { limit?: number; cursor?: string },
): Promise<{ items: CheckInOut[]; next_cursor: string | null }> {
  const url = new URL(`${API_URL}/api/clients/${clientId}/check-ins`);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  if (params?.cursor) url.searchParams.set("cursor", params.cursor);

  const res = await fetchWithAuth(url.toString());
  if (!res.ok) throw new Error(`List check-ins failed: ${res.status}`);
  return PaginatedCheckInsSchema.parse(await res.json());
}

export async function flagCheckIn(
  checkInId: string,
  sentiment_flag: string | null,
): Promise<CheckInOut> {
  const res = await fetchWithAuth(`${API_URL}/api/check-ins/${checkInId}/flag`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sentiment_flag }),
  });
  if (!res.ok) throw new Error(`Flag check-in failed: ${res.status}`);
  return CheckInOutSchema.parse(await res.json());
}
