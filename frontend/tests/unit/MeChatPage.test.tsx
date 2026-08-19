/**
 * PHASE-02c final-review fix (Finding 5) — direct mirror of TextView.test.tsx
 * (the HC-side Chat/Text coverage) for the client-side /me/chat page, which
 * had zero automated coverage. The e2e tests intended to cover this flow
 * (chat.spec.ts) are non-functional in this environment (see the
 * test.fixme() comments there), so this gives Task 6 real, working coverage
 * today without waiting on the e2e infra fix.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatPage from "@/app/me/chat/page";
import { listMyMessages, sendMyMessage } from "@/lib/api/me";

vi.mock("@/lib/api/me", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/me")>();
  return {
    ...actual,
    listMyMessages: vi.fn(),
    sendMyMessage: vi.fn(),
  };
});

describe("ChatPage (/me/chat)", () => {
  beforeEach(() => {
    vi.mocked(listMyMessages).mockReset();
    vi.mocked(sendMyMessage).mockReset();
  });

  it("shows a loading state before messages resolve", async () => {
    vi.mocked(listMyMessages).mockReturnValue(new Promise(() => {})); // never resolves

    render(<ChatPage />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no messages", async () => {
    vi.mocked(listMyMessages).mockResolvedValue({ items: [], next_cursor: null });

    render(<ChatPage />);

    await waitFor(() => screen.getByText(/no messages yet/i));
  });

  it("sends a text message successfully and clears the draft", async () => {
    vi.mocked(listMyMessages).mockResolvedValue({ items: [], next_cursor: null });
    vi.mocked(sendMyMessage).mockResolvedValue({
      id: "msg-1",
      client_id: "client-1",
      hc_user_id: "hc-1",
      direction: "client",
      body: "Quick question about my meal plan",
      has_attachment: false,
      attachment_original_filename: null,
      attachment_mime_type: null,
      sent_at: new Date().toISOString(),
    });
    const user = userEvent.setup();

    render(<ChatPage />);
    await waitFor(() => screen.getByText(/no messages yet/i));

    const input = screen.getByPlaceholderText(/type a message/i);
    await user.type(input, "Quick question about my meal plan");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => screen.getByText("Quick question about my meal plan"));
    expect(input).toHaveValue("");
    expect(screen.queryByText(/failed to send/i)).not.toBeInTheDocument();
  });

  it("shows an error and preserves the draft when sending fails", async () => {
    vi.mocked(listMyMessages).mockResolvedValue({ items: [], next_cursor: null });
    vi.mocked(sendMyMessage).mockRejectedValue(new Error("Send message failed: 422"));
    const user = userEvent.setup();

    render(<ChatPage />);
    await waitFor(() => screen.getByText(/no messages yet/i));

    const input = screen.getByPlaceholderText(/type a message/i);
    await user.type(input, "Hello coach!");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => screen.getByText(/message failed to send/i));

    // Draft body is preserved — the client can retry without retyping.
    expect(input).toHaveValue("Hello coach!");
    // No optimistic message was added to the (still-empty) thread.
    expect(screen.getByText(/no messages yet/i)).toBeInTheDocument();
  });
});
