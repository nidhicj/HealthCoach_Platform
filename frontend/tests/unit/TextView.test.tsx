/**
 * PHASE-02c Task 5 fix — TextView (Chat tab's Text sub-view) error handling.
 * A failed send must surface an error message and must NOT clear the
 * draft body/attachment, so the coach can retry without retyping.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TextView } from "@/app/(app)/clients/[clientId]/page";
import { listClientMessages, sendClientMessage } from "@/lib/api/messages";

vi.mock("@/lib/api/messages", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api/messages")>();
  return {
    ...actual,
    listClientMessages: vi.fn(),
    sendClientMessage: vi.fn(),
  };
});

describe("TextView", () => {
  beforeEach(() => {
    vi.mocked(listClientMessages).mockReset();
    vi.mocked(sendClientMessage).mockReset();
    vi.mocked(listClientMessages).mockResolvedValue({ items: [], next_cursor: null });
  });

  it("shows an error and keeps the draft body when sending fails", async () => {
    vi.mocked(sendClientMessage).mockRejectedValue(new Error("Send message failed: 422"));
    const user = userEvent.setup();

    render(<TextView clientId="client-1" />);
    await waitFor(() => screen.getByText(/no messages yet/i));

    const input = screen.getByPlaceholderText(/type a message/i);
    await user.type(input, "Great job this week!");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => screen.getByText(/message failed to send/i));

    // Draft body is preserved — the coach can retry without retyping.
    expect(input).toHaveValue("Great job this week!");
    // No optimistic message was added to the (still-empty) thread.
    expect(screen.getByText(/no messages yet/i)).toBeInTheDocument();
  });

  it("keeps a selected attachment after a failed send", async () => {
    vi.mocked(sendClientMessage).mockRejectedValue(new Error("Send message failed: 400"));
    const user = userEvent.setup();

    render(<TextView clientId="client-1" />);
    await waitFor(() => screen.getByText(/no messages yet/i));

    const input = screen.getByPlaceholderText(/type a message/i);
    await user.type(input, "Photo attached");

    const file = new File(["fake-image-bytes"], "progress.png", { type: "image/png" });
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    await user.upload(fileInput, file);
    expect(fileInput.files?.[0]?.name).toBe("progress.png");

    await user.click(screen.getByRole("button", { name: /^send$/i }));
    await waitFor(() => screen.getByText(/message failed to send/i));

    // Attachment selection survives the failed send.
    expect(fileInput.files?.[0]?.name).toBe("progress.png");
  });

  it("clears the draft and error on a successful send", async () => {
    vi.mocked(sendClientMessage).mockResolvedValue({
      id: "msg-1",
      client_id: "client-1",
      hc_user_id: "hc-1",
      direction: "coach",
      body: "Great job this week!",
      has_attachment: false,
      attachment_original_filename: null,
      attachment_mime_type: null,
      sent_at: new Date().toISOString(),
    });
    const user = userEvent.setup();

    render(<TextView clientId="client-1" />);
    await waitFor(() => screen.getByText(/no messages yet/i));

    const input = screen.getByPlaceholderText(/type a message/i);
    await user.type(input, "Great job this week!");
    await user.click(screen.getByRole("button", { name: /^send$/i }));

    await waitFor(() => screen.getByText("Great job this week!"));
    expect(input).toHaveValue("");
    expect(screen.queryByText(/message failed to send/i)).not.toBeInTheDocument();
  });
});
