import { describe, it, expect } from "vitest";
import {
  buildLastSessionMap,
  buildFlaggedSet,
  findMilestone,
  formatRelativeDate,
} from "@/lib/rosterUtils";
import type { SessionOut } from "@/lib/api/sessions";
import type { ActionItemOut } from "@/lib/api/actionItems";
import type { ClientOut } from "@/lib/api/clients";

const baseSession = (overrides: Partial<SessionOut>): SessionOut => ({
  id: "s1",
  hc_user_id: "hc1",
  client_id: "c1",
  session_number: 1,
  scheduled_at: new Date(Date.now() - 86400000).toISOString(), // yesterday
  started_at: null,
  ended_at: null,
  zoom_meeting_id: null,
  notes_internal: null,
  session_notes: null,
  created_at: new Date().toISOString(),
  ...overrides,
});

const baseClient = (overrides: Partial<ClientOut>): ClientOut => ({
  id: "c1",
  hc_user_id: "hc1",
  full_name: "Priya S",
  code: "CP0001",
  email: null,
  phone: null,
  timezone: null,
  journey_stage: "active",
  course_start_date: null,
  course_end_date: null,
  course_goal: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

const baseItem = (overrides: Partial<ActionItemOut>): ActionItemOut => ({
  id: "i1",
  client_id: "c1",
  session_id: null,
  hc_user_id: "hc1",
  description: "item",
  due_date: null,
  status: "missed",
  completed_at: null,
  created_at: new Date().toISOString(),
  ...overrides,
});

describe("buildLastSessionMap", () => {
  it("maps client_id to most recent past session date", () => {
    const older = baseSession({ id: "s1", scheduled_at: new Date(Date.now() - 172800000).toISOString() });
    const newer = baseSession({ id: "s2", scheduled_at: new Date(Date.now() - 86400000).toISOString() });
    const map = buildLastSessionMap([older, newer]);
    expect(map.get("c1")?.toISOString()).toBe(new Date(newer.scheduled_at).toISOString());
  });

  it("ignores future sessions", () => {
    const future = baseSession({ scheduled_at: new Date(Date.now() + 86400000).toISOString() });
    const map = buildLastSessionMap([future]);
    expect(map.has("c1")).toBe(false);
  });

  it("returns empty map for empty input", () => {
    expect(buildLastSessionMap([]).size).toBe(0);
  });
});

describe("buildFlaggedSet", () => {
  it("returns set of client_ids from missed items", () => {
    const set = buildFlaggedSet([baseItem({ client_id: "c1" }), baseItem({ id: "i2", client_id: "c2" })]);
    expect(set.has("c1")).toBe(true);
    expect(set.has("c2")).toBe(true);
    expect(set.has("c3")).toBe(false);
  });
});

describe("findMilestone", () => {
  it("finds a milestone session within last 7 days", () => {
    const s = baseSession({ session_number: 10, scheduled_at: new Date(Date.now() - 86400000).toISOString() });
    const result = findMilestone([s], [baseClient({})]);
    expect(result).toEqual({ clientName: "Priya S", sessionNumber: 10 });
  });

  it("ignores non-milestone session numbers", () => {
    const s = baseSession({ session_number: 3 });
    expect(findMilestone([s], [baseClient({})])).toBeNull();
  });

  it("ignores milestone sessions older than 7 days", () => {
    const s = baseSession({ session_number: 10, scheduled_at: new Date(Date.now() - 8 * 86400000).toISOString() });
    expect(findMilestone([s], [baseClient({})])).toBeNull();
  });
});

describe("formatRelativeDate", () => {
  it("returns — for null", () => expect(formatRelativeDate(null)).toBe("—"));
  it("returns Today for today", () => expect(formatRelativeDate(new Date())).toBe("Today"));
  it("returns Yesterday for 1 day ago", () => {
    const d = new Date(Date.now() - 86400000);
    expect(formatRelativeDate(d)).toBe("Yesterday");
  });
  it("returns N days ago for 3 days", () => {
    const d = new Date(Date.now() - 3 * 86400000);
    expect(formatRelativeDate(d)).toBe("3 days ago");
  });
});
