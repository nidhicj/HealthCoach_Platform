import { z } from "zod";
import { API_URL } from "@/lib/config";
import { fetchWithAuth } from "@/lib/auth/client";

// ── schemas ──────────────────────────────────────────────────────────────────

export const CalendarStatusSchema = z.object({
  connected: z.boolean(),
  google_account_email: z.string().nullable(),
  connected_at: z.string().nullable(),
  needs_reauth: z.boolean(),
});

export const CalendarEventSchema = z.object({
  id: z.string(),
  summary: z.string(),
  start: z.string(),
  end: z.string(),
  hangout_link: z.string().nullable(),
  html_link: z.string(),
  location: z.string().nullable(),
});

const CalendarConnectUrlSchema = z.object({
  auth_url: z.string(),
});

export type CalendarStatus = z.infer<typeof CalendarStatusSchema>;
export type CalendarEvent = z.infer<typeof CalendarEventSchema>;

// ── api wrappers ─────────────────────────────────────────────────────────────

export async function getCalendarStatus(): Promise<CalendarStatus> {
  const res = await fetchWithAuth(`${API_URL}/api/calendar/status`);
  if (!res.ok) throw new Error(`Get calendar status failed: ${res.status}`);
  return CalendarStatusSchema.parse(await res.json());
}

export async function getCalendarConnectUrl(): Promise<string> {
  const res = await fetchWithAuth(`${API_URL}/api/auth/google/calendar/connect`);
  if (!res.ok) throw new Error(`Get calendar connect URL failed: ${res.status}`);
  return CalendarConnectUrlSchema.parse(await res.json()).auth_url;
}

export async function listCalendarEvents(
  timeMin: string,
  timeMax: string,
): Promise<CalendarEvent[]> {
  const qs = new URLSearchParams({ time_min: timeMin, time_max: timeMax });
  const res = await fetchWithAuth(`${API_URL}/api/calendar/events?${qs}`);
  if (!res.ok) throw new Error(`List calendar events failed: ${res.status}`);
  return z.array(CalendarEventSchema).parse(await res.json());
}

// NOTE: the backend endpoint this calls (POST /api/calendar/events) is not
// implemented yet — it lands in PHASE-01e Task 12. This wrapper is written
// now (per Task 8's brief) so Task 13's create-event form has it available;
// it will 404 until Task 12 ships.
export async function createCalendarEvent(input: {
  summary: string;
  start: string;
  end: string;
  add_meet?: boolean;
}): Promise<CalendarEvent> {
  const res = await fetchWithAuth(`${API_URL}/api/calendar/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Create calendar event failed: ${res.status}`);
  return CalendarEventSchema.parse(await res.json());
}
