import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import SharePage from "@/app/share/[token]/page";
import { giteaTutorialSpecFixture } from "@/lib/fixtures";

describe("Public Share Page (/share/[token])", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("mounts player in read-only mode for valid share token", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => giteaTutorialSpecFixture,
    });

    const page = await SharePage({
      params: Promise.resolve({ token: "valid-token" }),
    });

    render(page);

    // 1. Verify SharedPageHeader is present with "Viewing shared tutorial" branding
    expect(screen.getByTestId("shared-page-header")).toBeInTheDocument();
    expect(screen.getByTestId("shared-mode-indicator")).toHaveTextContent(/Viewing shared tutorial/i);

    // 2. Verify TutorialPlayer root and Step 1 are displayed
    expect(screen.getByTestId("tutorial-player-root")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /Interactive Tutorial Player/i })).toBeInTheDocument();
    expect(screen.getByTestId("readonly-badge")).toHaveTextContent("Read-Only");

    // 3. Verify step controls are present and active
    expect(screen.getByTestId("tutorial-controls")).toBeInTheDocument();
    expect(screen.getByTestId("control-play-pause")).toBeInTheDocument();
    expect(screen.getByTestId("control-next-step")).toBeInTheDocument();
    expect(screen.getByTestId("control-replay-step")).toBeInTheDocument();
    expect(screen.getByTestId("control-toggle-captions")).toBeInTheDocument();
    expect(screen.getByTestId("control-toggle-zoom")).toBeInTheDocument();

    // 4. Verify STRICT absence of Edit, Delete, Re-run, or Share Settings controls
    const editBtn = screen.queryByRole("button", { name: /edit/i });
    expect(editBtn).toBeNull();

    const deleteBtn = screen.queryByRole("button", { name: /delete/i });
    expect(deleteBtn).toBeNull();

    const rerunBtn = screen.queryByRole("button", { name: /re-run|rerun/i });
    expect(rerunBtn).toBeNull();

    const shareSettingsBtn = screen.queryByRole("button", { name: /share settings/i });
    expect(shareSettingsBtn).toBeNull();

    const signOutBtn = screen.queryByRole("button", { name: /sign out|logout/i });
    expect(signOutBtn).toBeNull();

    // 5. Verify instruction text and copy actions work
    expect(screen.getByTestId("instruction-text")).toBeInTheDocument();
    const copyBtns = screen.getAllByRole("button", { name: /copy/i });
    expect(copyBtns.length).toBeGreaterThan(0);
    fireEvent.click(copyBtns[0]);
  });

  it("renders RevokedLinkNotice when share token returns 404", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ error: "Not found" }),
    });

    const page = await SharePage({
      params: Promise.resolve({ token: "revoked-token" }),
    });

    render(page);

    expect(screen.getByTestId("revoked-link-notice")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Tutorial Link Unavailable/i })).toBeInTheDocument();
    expect(screen.getByText(/This tutorial link is invalid or has been revoked/i)).toBeInTheDocument();

    const homeLink = screen.getByTestId("revoked-home-link");
    expect(homeLink).toBeInTheDocument();
    expect(homeLink).toHaveAttribute("href", "/");

    // Player should NOT be in the DOM
    expect(screen.queryByTestId("tutorial-player-root")).toBeNull();
  });

  it("handles revoked or invalid tokens in fallback mock mode", async () => {
    const page = await SharePage({
      params: Promise.resolve({ token: "invalid-token" }),
    });

    render(page);

    expect(screen.getByTestId("revoked-link-notice")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Tutorial Link Unavailable/i })).toBeInTheDocument();
  });
});
