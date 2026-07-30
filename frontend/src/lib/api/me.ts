import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";
import { ActionItemOutSchema, type ActionItemOut } from "@/lib/api/actionItems";
import { CheckInOutSchema, type CheckInOut } from "@/lib/api/checkIns";
import { z } from "zod";

const PaginatedActionItemsSchema = z.object({
  items: z.array(ActionItemOutSchema),
  next_cursor: z.string().nullable(),
});

const PaginatedCheckInsSchema = z.object({
  items: z.array(CheckInOutSchema),
  next_cursor: z.string().nullable(),
});

export async function listMyActionItems(): Promise<{ items: ActionItemOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/me/action-items`);
  if (!res.ok) throw new Error(`List my action items failed: ${res.status}`);
  return PaginatedActionItemsSchema.parse(await res.json());
}

export async function patchMyActionItem(
  itemId: string,
  input: { status: string },
): Promise<ActionItemOut> {
  const res = await fetchWithAuth(`${API_URL}/api/me/action-items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Patch my action item failed: ${res.status}`);
  return ActionItemOutSchema.parse(await res.json());
}

export async function listMyCheckIns(): Promise<{ items: CheckInOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/me/check-ins`);
  if (!res.ok) throw new Error(`List my check-ins failed: ${res.status}`);
  return PaginatedCheckInsSchema.parse(await res.json());
}

export async function submitMyCheckIn(payload: Record<string, unknown>): Promise<CheckInOut> {
  const res = await fetchWithAuth(`${API_URL}/api/me/check-ins`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ payload }),
  });
  if (!res.ok) throw new Error(`Submit check-in failed: ${res.status}`);
  return CheckInOutSchema.parse(await res.json());
}
