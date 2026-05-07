import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const ActionItemOutSchema = z.object({
  id: z.string(),
  client_id: z.string(),
  session_id: z.string().nullable(),
  hc_user_id: z.string(),
  description: z.string(),
  due_date: z.string().nullable(),
  status: z.string(),
  completed_at: z.string().nullable(),
  created_at: z.string(),
});

const PaginatedActionItemsSchema = z.object({
  items: z.array(ActionItemOutSchema),
  next_cursor: z.string().nullable(),
});

export type ActionItemOut = z.infer<typeof ActionItemOutSchema>;

// ── api wrappers ─────────────────────────────────────────────────────────────

export async function createActionItem(input: {
  client_id: string;
  session_id?: string;
  description: string;
  due_date?: string;
}): Promise<ActionItemOut> {
  const res = await fetchWithAuth(`${API_URL}/api/action-items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Create action item failed: ${res.status}`);
  return ActionItemOutSchema.parse(await res.json());
}

export async function listActionItems(params?: {
  client_id?: string;
  status?: string;
  limit?: number;
  cursor?: string;
}): Promise<{ items: ActionItemOut[]; next_cursor: string | null }> {
  const url = new URL(`${API_URL}/api/action-items`);
  if (params?.client_id) url.searchParams.set("client_id", params.client_id);
  if (params?.status) url.searchParams.set("status", params.status);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  if (params?.cursor) url.searchParams.set("cursor", params.cursor);

  const res = await fetchWithAuth(url.toString());
  if (!res.ok) throw new Error(`List action items failed: ${res.status}`);
  return PaginatedActionItemsSchema.parse(await res.json());
}

export async function patchActionItem(
  itemId: string,
  input: { status?: string; due_date?: string },
): Promise<ActionItemOut> {
  const res = await fetchWithAuth(`${API_URL}/api/action-items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Patch action item failed: ${res.status}`);
  return ActionItemOutSchema.parse(await res.json());
}
