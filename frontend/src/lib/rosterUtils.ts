import type { SessionOut } from "@/lib/api/sessions";
import type { ActionItemOut } from "@/lib/api/actionItems";
import type { ClientOut } from "@/lib/api/clients";

const MILESTONE_NUMBERS = new Set([5, 10, 25, 50]);
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

export function buildLastSessionMap(sessions: SessionOut[]): Map<string, Date> {
  const now = new Date();
  const map = new Map<string, Date>();
  for (const s of sessions) {
    const d = new Date(s.scheduled_at);
    if (d > now) continue;
    const existing = map.get(s.client_id);
    if (!existing || d > existing) map.set(s.client_id, d);
  }
  return map;
}

export function buildFlaggedSet(missedItems: ActionItemOut[]): Set<string> {
  return new Set(missedItems.map((i) => i.client_id));
}

export function findMilestone(
  sessions: SessionOut[],
  clients: ClientOut[],
): { clientName: string; sessionNumber: number } | null {
  const clientMap = new Map(clients.map((c) => [c.id, c]));
  const cutoff = new Date(Date.now() - SEVEN_DAYS_MS);
  for (const s of sessions) {
    const d = new Date(s.scheduled_at);
    if (MILESTONE_NUMBERS.has(s.session_number) && d >= cutoff && d <= new Date()) {
      const client = clientMap.get(s.client_id);
      if (client) return { clientName: client.full_name, sessionNumber: s.session_number };
    }
  }
  return null;
}

export function formatRelativeDate(date: Date | null): string {
  if (!date) return "—";
  const diffMs = new Date().getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} week${Math.floor(diffDays / 7) > 1 ? "s" : ""} ago`;
  return `${Math.floor(diffDays / 30)} month${Math.floor(diffDays / 30) > 1 ? "s" : ""} ago`;
}
