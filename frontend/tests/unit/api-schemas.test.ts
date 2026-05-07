/**
 * Zod schema parse tests for every API client module.
 * Validates the boundary contract: golden inputs parse, bad inputs throw.
 */
import { describe, it, expect } from "vitest";
import { ClientOutSchema, ClientDetailOutSchema, AstOutSchema } from "@/lib/api/clients";
import { SessionOutSchema, MomOutSchema, BriefOutSchema } from "@/lib/api/sessions";
import { ClientFileOutSchema } from "@/lib/api/files";
import { ActionItemOutSchema } from "@/lib/api/actionItems";
import { CheckInOutSchema } from "@/lib/api/checkIns";

const NOW = new Date().toISOString();

// ── ClientOut ────────────────────────────────────────────────────────────────

describe("ClientOutSchema", () => {
  const valid = {
    id: "cli-1",
    hc_user_id: "hc-1",
    code: "CLI001",
    full_name: "Ananya Krishnan",
    email: "a@example.com",
    phone: null,
    timezone: null,
    journey_stage: "active",
    course_start_date: null,
    course_end_date: null,
    course_goal: null,
    created_at: NOW,
    updated_at: NOW,
  };

  it("parses a valid client", () => {
    expect(() => ClientOutSchema.parse(valid)).not.toThrow();
  });

  it("allows null email and phone", () => {
    const result = ClientOutSchema.parse({ ...valid, email: null, phone: null });
    expect(result.email).toBeNull();
  });

  it("throws when full_name is missing", () => {
    expect(() => ClientOutSchema.parse({ ...valid, full_name: undefined })).toThrow();
  });
});

describe("ClientDetailOutSchema", () => {
  const valid = {
    id: "cli-1",
    hc_user_id: "hc-1",
    code: "CLI001",
    full_name: "Ananya",
    email: null,
    phone: null,
    timezone: null,
    journey_stage: "onboarding",
    course_start_date: null,
    course_end_date: null,
    course_goal: null,
    created_at: NOW,
    updated_at: NOW,
    ast: null,
    open_action_items_count: 0,
    last_session_at: null,
  };

  it("parses a valid client detail", () => {
    expect(() => ClientDetailOutSchema.parse(valid)).not.toThrow();
  });

  it("throws when id is missing", () => {
    expect(() => ClientDetailOutSchema.parse({ ...valid, id: undefined })).toThrow();
  });
});

describe("AstOutSchema", () => {
  const valid = {
    triage_flags: ["missed_action_item"],
    status_summary: "Good progress.",
    trend_tags: [],
    open_items: [],
    missed_items: [],
  };

  it("parses a valid AST", () => {
    expect(() => AstOutSchema.parse(valid)).not.toThrow();
  });

  it("parses empty triage_flags", () => {
    const result = AstOutSchema.parse({ ...valid, triage_flags: [] });
    expect(result.triage_flags).toHaveLength(0);
  });

  it("throws when triage_flags is not an array", () => {
    expect(() => AstOutSchema.parse({ ...valid, triage_flags: "bad" })).toThrow();
  });
});

// ── SessionOut ───────────────────────────────────────────────────────────────

describe("SessionOutSchema", () => {
  const valid = {
    id: "sess-1",
    hc_user_id: "hc-1",
    client_id: "cli-1",
    session_number: 1,
    scheduled_at: NOW,
    started_at: null,
    ended_at: null,
    zoom_meeting_id: null,
    notes_internal: null,
    session_notes: null,
    created_at: NOW,
  };

  it("parses a valid session", () => {
    expect(() => SessionOutSchema.parse(valid)).not.toThrow();
  });

  it("allows non-null started_at and ended_at", () => {
    const result = SessionOutSchema.parse({
      ...valid,
      started_at: NOW,
      ended_at: NOW,
    });
    expect(result.ended_at).toBe(NOW);
  });

  it("throws when session_number is missing", () => {
    expect(() => SessionOutSchema.parse({ ...valid, session_number: undefined })).toThrow();
  });
});

describe("MomOutSchema", () => {
  const valid = {
    id: "mom-1",
    session_id: "sess-1",
    client_id: "cli-1",
    draft_text: "Draft content",
    final_text: null,
    status: "draft",
    llm_call_id: null,
    sent_at: null,
    created_at: NOW,
    updated_at: NOW,
  };

  it("parses a valid MOM", () => {
    expect(() => MomOutSchema.parse(valid)).not.toThrow();
  });

  it("parses a sent MOM with final_text", () => {
    const result = MomOutSchema.parse({
      ...valid,
      final_text: "Final content",
      status: "sent",
      sent_at: NOW,
    });
    expect(result.status).toBe("sent");
    expect(result.final_text).toBe("Final content");
  });
});

describe("BriefOutSchema", () => {
  const valid = {
    id: "brief-1",
    session_id: "sess-1",
    client_id: "cli-1",
    brief_text: "Brief content",
    triage_flags: null,
    llm_call_id: "llm-1",
    generated_at: NOW,
  };

  it("parses a valid brief", () => {
    expect(() => BriefOutSchema.parse(valid)).not.toThrow();
  });

  it("allows null triage_flags", () => {
    const result = BriefOutSchema.parse({ ...valid, triage_flags: null });
    expect(result.triage_flags).toBeNull();
  });
});

// ── ClientFileOut ─────────────────────────────────────────────────────────────

describe("ClientFileOutSchema", () => {
  const valid = {
    id: "file-1",
    session_id: "sess-1",
    original_filename: "notes.txt",
    storage_path: "path/to/file",
    mime_type: "text/plain",
    size_bytes: 1024,
    uploaded_at: NOW,
    is_zoom_summary: false,
  };

  it("parses a valid file", () => {
    expect(() => ClientFileOutSchema.parse(valid)).not.toThrow();
  });

  it("throws when size_bytes is not a number", () => {
    expect(() =>
      ClientFileOutSchema.parse({ ...valid, size_bytes: "1024" }),
    ).toThrow();
  });
});

// ── ActionItemOut ─────────────────────────────────────────────────────────────

describe("ActionItemOutSchema", () => {
  const valid = {
    id: "ai-1",
    client_id: "cli-1",
    session_id: null,
    hc_user_id: "hc-1",
    description: "Walk 30 minutes daily",
    due_date: null,
    status: "open",
    completed_at: null,
    created_at: NOW,
  };

  it("parses a valid action item", () => {
    expect(() => ActionItemOutSchema.parse(valid)).not.toThrow();
  });

  it("parses with a due_date", () => {
    const result = ActionItemOutSchema.parse({ ...valid, due_date: "2026-06-01" });
    expect(result.due_date).toBe("2026-06-01");
  });

  it("throws when description is missing", () => {
    expect(() => ActionItemOutSchema.parse({ ...valid, description: undefined })).toThrow();
  });
});

// ── CheckInOut ─────────────────────────────────────────────────────────────────

describe("CheckInOutSchema", () => {
  const valid = {
    id: "ci-1",
    client_id: "cli-1",
    hc_user_id: "hc-1",
    payload: { mood: "good", energy: 7 },
    sentiment_flag: null,
    created_at: NOW,
  };

  it("parses a valid check-in", () => {
    expect(() => CheckInOutSchema.parse(valid)).not.toThrow();
  });

  it("parses arbitrary payload shapes", () => {
    const result = CheckInOutSchema.parse({
      ...valid,
      payload: { anything: true, nested: { deeply: 42 } },
    });
    expect(result.payload).toMatchObject({ anything: true });
  });

  it("throws when client_id is missing", () => {
    expect(() => CheckInOutSchema.parse({ ...valid, client_id: undefined })).toThrow();
  });

  it("allows non-null sentiment_flag", () => {
    const result = CheckInOutSchema.parse({ ...valid, sentiment_flag: "low_energy" });
    expect(result.sentiment_flag).toBe("low_energy");
  });
});
