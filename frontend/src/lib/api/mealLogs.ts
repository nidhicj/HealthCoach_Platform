import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

export const MEAL_SLOTS = ["breakfast", "morning_snack", "lunch", "evening_snack", "dinner"] as const;
export type MealSlot = (typeof MEAL_SLOTS)[number];

export const MEAL_SLOT_LABELS: Record<MealSlot, string> = {
  breakfast: "Breakfast",
  morning_snack: "Morning Snack",
  lunch: "Lunch",
  evening_snack: "Evening Snack",
  dinner: "Dinner",
};

export const MealLogOutSchema = z.object({
  id: z.string(),
  client_id: z.string(),
  hc_user_id: z.string(),
  meal_slot: z.enum(MEAL_SLOTS),
  description: z.string().nullable(),
  photo_original_filename: z.string(),
  photo_mime_type: z.string(),
  captured_at: z.string().nullable(),
  logged_at: z.string(),
  hc_reaction: z.enum(["happy", "neutral", "sad"]).nullable(),
  reacted_at: z.string().nullable(),
});
export type MealLogOut = z.infer<typeof MealLogOutSchema>;

const PaginatedMealLogsSchema = z.object({
  items: z.array(MealLogOutSchema),
  next_cursor: z.string().nullable(),
});

// ── HC-side ──────────────────────────────────────────────────────────────────

export async function listClientMealLogs(clientId: string): Promise<{ items: MealLogOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/meal-logs`);
  if (!res.ok) throw new Error(`List meal logs failed: ${res.status}`);
  return PaginatedMealLogsSchema.parse(await res.json());
}

export async function reactToMealLog(
  clientId: string, mealLogId: string, reaction: "happy" | "neutral" | "sad",
): Promise<MealLogOut> {
  const res = await fetchWithAuth(`${API_URL}/api/clients/${clientId}/meal-logs/${mealLogId}/react`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reaction }),
  });
  if (!res.ok) throw new Error(`React to meal log failed: ${res.status}`);
  return MealLogOutSchema.parse(await res.json());
}

export function mealLogPhotoUrl(clientId: string, mealLogId: string): string {
  return `${API_URL}/api/clients/${clientId}/meal-logs/${mealLogId}/photo`;
}

// ── client-side ──────────────────────────────────────────────────────────────

export async function listMyMealLogs(): Promise<{ items: MealLogOut[]; next_cursor: string | null }> {
  const res = await fetchWithAuth(`${API_URL}/api/me/meal-logs`);
  if (!res.ok) throw new Error(`List my meal logs failed: ${res.status}`);
  return PaginatedMealLogsSchema.parse(await res.json());
}

export async function submitMyMealLog(input: { mealSlot: MealSlot; description?: string; photo: File }): Promise<MealLogOut> {
  const form = new FormData();
  form.append("meal_slot", input.mealSlot);
  if (input.description) form.append("description", input.description);
  form.append("photo", input.photo);

  const res = await fetchWithAuth(`${API_URL}/api/me/meal-logs`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Submit meal log failed: ${res.status}`);
  return MealLogOutSchema.parse(await res.json());
}

export function myMealLogPhotoUrl(mealLogId: string): string {
  return `${API_URL}/api/me/meal-logs/${mealLogId}/photo`;
}
