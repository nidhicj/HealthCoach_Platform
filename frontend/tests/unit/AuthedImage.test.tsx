/**
 * PHASE-02c final-review fix (Finding 1) — AuthedImage fetches attachment
 * bytes via fetchWithAuth (Bearer-token auth) instead of a plain <img src>,
 * since the backend attachment endpoints require an Authorization header
 * that a browser-issued <img> GET cannot carry.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthedImage } from "@/components/authed-image";
import { fetchWithAuth } from "@/lib/auth/client";

vi.mock("@/lib/auth/client", () => ({
  fetchWithAuth: vi.fn(),
}));

describe("AuthedImage", () => {
  const FAKE_BLOB = new Blob(["fake-image-bytes"], { type: "image/png" });

  beforeEach(() => {
    vi.mocked(fetchWithAuth).mockReset();
    URL.createObjectURL = vi.fn().mockReturnValue("blob:fake-object-url");
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches the attachment via fetchWithAuth and renders it as an object URL", async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => FAKE_BLOB,
    } as Response);

    render(<AuthedImage url="/api/clients/c-1/messages/m-1/attachment" alt="progress photo" />);

    expect(fetchWithAuth).toHaveBeenCalledWith("/api/clients/c-1/messages/m-1/attachment");

    await waitFor(() => {
      const img = screen.getByAltText("progress photo") as HTMLImageElement;
      expect(img.src).toBe("blob:fake-object-url");
    });
  });

  it("renders nothing while loading", () => {
    vi.mocked(fetchWithAuth).mockReturnValue(new Promise(() => {})); // never resolves

    const { container } = render(<AuthedImage url="/api/me/messages/m-1/attachment" alt="loading" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows an unavailable note when the fetch fails", async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue({ ok: false, status: 404 } as Response);

    render(<AuthedImage url="/api/me/messages/m-1/attachment" alt="broken" />);

    await waitFor(() => screen.getByText(/attachment unavailable/i));
    expect(screen.queryByAltText("broken")).not.toBeInTheDocument();
  });

  it("revokes the previous object URL when the url prop changes", async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => FAKE_BLOB,
    } as Response);

    const { rerender } = render(<AuthedImage url="/api/me/messages/m-1/attachment" alt="one" />);
    await waitFor(() => screen.getByAltText("one"));

    rerender(<AuthedImage url="/api/me/messages/m-2/attachment" alt="two" />);
    await waitFor(() => screen.getByAltText("two"));

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:fake-object-url");
  });
});
