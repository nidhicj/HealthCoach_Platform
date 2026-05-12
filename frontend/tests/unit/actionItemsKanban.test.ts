import { describe, it, expect } from "vitest";
import { groupByClient, MOVE_FORWARD, MOVE_BACK } from "@/lib/actionItemsKanban";
import type { ClientOut } from "@/lib/api/clients";
import type { ActionItemOut } from "@/lib/api/actionItems";

const NOW = new Date().toISOString();

function makeClient(id: string): ClientOut {
  return {
    id,
    hc_user_id: "hc-1",
    full_name: `Client ${id}`,
    code: null,
    email: null,
    phone: null,
    timezone: null,
    journey_stage: "active",
    course_start_date: null,
    course_end_date: null,
    course_goal: null,
    created_at: NOW,
    updated_at: NOW,
  };
}

function makeItem(id: string, clientId: string, status: string): ActionItemOut {
  return {
    id,
    client_id: clientId,
    session_id: null,
    hc_user_id: "hc-1",
    description: `Item ${id}`,
    due_date: null,
    status,
    completed_at: null,
    created_at: NOW,
  };
}

describe("groupByClient", () => {
  it("routes open/in_progress/completed items to correct columns", () => {
    const clients = [makeClient("c1"), makeClient("c2")];
    const items = [
      makeItem("i1", "c1", "open"),
      makeItem("i2", "c1", "in_progress"),
      makeItem("i3", "c1", "completed"),
      makeItem("i4", "c2", "missed"),
    ];
    const rows = groupByClient(clients, items);

    expect(rows).toHaveLength(2);
    const c1 = rows.find((r) => r.client.id === "c1")!;
    expect(c1.open.map((i) => i.id)).toEqual(["i1"]);
    expect(c1.in_progress.map((i) => i.id)).toEqual(["i2"]);
    expect(c1.done.map((i) => i.id)).toEqual(["i3"]);

    const c2 = rows.find((r) => r.client.id === "c2")!;
    expect(c2.open.map((i) => i.id)).toEqual(["i4"]);
    expect(c2.in_progress).toHaveLength(0);
    expect(c2.done).toHaveLength(0);
  });

  it("places missed items in the open column", () => {
    const rows = groupByClient(
      [makeClient("c1")],
      [makeItem("i1", "c1", "missed")],
    );
    expect(rows[0].open).toHaveLength(1);
    expect(rows[0].open[0].status).toBe("missed");
  });

  it("omits clients with zero items across all columns", () => {
    const rows = groupByClient(
      [makeClient("c1"), makeClient("c2")],
      [makeItem("i1", "c1", "open")],
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].client.id).toBe("c1");
  });

  it("returns empty array when items list is empty", () => {
    expect(groupByClient([makeClient("c1")], [])).toHaveLength(0);
  });
});

describe("MOVE_FORWARD", () => {
  it("open → in_progress", () => expect(MOVE_FORWARD["open"]).toBe("in_progress"));
  it("missed → in_progress", () => expect(MOVE_FORWARD["missed"]).toBe("in_progress"));
  it("in_progress → completed", () => expect(MOVE_FORWARD["in_progress"]).toBe("completed"));
  it("completed has no forward target", () => expect(MOVE_FORWARD["completed"]).toBeUndefined());
});

describe("MOVE_BACK", () => {
  it("in_progress → open", () => expect(MOVE_BACK["in_progress"]).toBe("open"));
  it("completed → in_progress", () => expect(MOVE_BACK["completed"]).toBe("in_progress"));
  it("open has no back target", () => expect(MOVE_BACK["open"]).toBeUndefined());
});
