import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ShareTutorialModal } from "@/components/share";
import { MockApiClient } from "@/lib/api";

describe("ShareTutorialModal", () => {
  const mockWorkflowId = "wf-test-share-123";

  beforeEach(() => {
    vi.restoreAllMocks();
    (MockApiClient as unknown as { globalShares: Map<string, unknown> }).globalShares?.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders when open and displays empty state when no share links exist", async () => {
    render(
      <ShareTutorialModal
        isOpen={true}
        onClose={vi.fn()}
        workflowId={mockWorkflowId}
        tutorialTitle="Test Tutorial"
      />
    );

    expect(screen.getByTestId("share-tutorial-modal")).toBeInTheDocument();
    expect(screen.getByText("Share tutorial")).toBeInTheDocument();
    expect(screen.getByText("Test Tutorial")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/No active share links for this tutorial yet/i)).toBeInTheDocument();
    });
    expect(screen.getByTestId("create-share-link-btn")).toBeInTheDocument();
  });

  it("creates a share link and allows copying the secret URL", async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    render(
      <ShareTutorialModal
        isOpen={true}
        onClose={vi.fn()}
        workflowId={mockWorkflowId}
        tutorialTitle="Test Tutorial"
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("create-share-link-btn")).toBeInTheDocument();
    });

    const createBtn = screen.getByTestId("create-share-link-btn");
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(screen.getByTestId("share-url-input")).toBeInTheDocument();
    });

    const input = screen.getByTestId("share-url-input") as HTMLInputElement;
    expect(input.value).toMatch(/\/share\/mock-token-/);

    const copyBtn = screen.getByTestId("copy-share-url-btn");
    fireEvent.click(copyBtn);

    expect(writeTextMock).toHaveBeenCalledWith(input.value);
    await waitFor(() => {
      expect(screen.getByText(/Copied!/i)).toBeInTheDocument();
    });
  });

  it("revokes an active share link", async () => {
    render(
      <ShareTutorialModal
        isOpen={true}
        onClose={vi.fn()}
        workflowId={mockWorkflowId}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("create-share-link-btn")).toBeInTheDocument();
    });

    // Create a link first
    fireEvent.click(screen.getByTestId("create-share-link-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("revoke-share-link-btn")).toBeInTheDocument();
    });

    const revokeBtn = screen.getByTestId("revoke-share-link-btn");
    fireEvent.click(revokeBtn);

    await waitFor(() => {
      expect(screen.getAllByText("Revoked").length).toBeGreaterThan(0);
    });
    expect(screen.queryByTestId("share-url-input")).toBeNull();
  });

  it("does not render when isOpen is false", () => {
    render(
      <ShareTutorialModal
        isOpen={false}
        onClose={vi.fn()}
        workflowId={mockWorkflowId}
      />
    );

    expect(screen.queryByTestId("share-tutorial-modal")).toBeNull();
  });
});
