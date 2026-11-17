import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ExportVideoModal } from "@/components/export";
import { MockApiClient } from "@/lib/api";
import type { Export } from "@krama/contracts-ts";

describe("ExportVideoModal", () => {
  const mockWorkflowId = "wf-test-export-123";

  beforeEach(() => {
    vi.restoreAllMocks();
    (MockApiClient as unknown as { globalExports: Map<string, unknown> }).globalExports?.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not render when isOpen is false", () => {
    render(
      <ExportVideoModal
        isOpen={false}
        onClose={vi.fn()}
        workflowId={mockWorkflowId}
      />
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders preset selection options when open", () => {
    render(
      <ExportVideoModal
        isOpen={true}
        onClose={vi.fn()}
        workflowId={mockWorkflowId}
        tutorialTitle="Test Checkout Tutorial"
        stepCount={4}
      />
    );

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Export Tutorial as Video")).toBeInTheDocument();
    expect(screen.getByText("Test Checkout Tutorial")).toBeInTheDocument();
    expect(screen.getByTestId("preset-landscape-btn")).toBeInTheDocument();
    expect(screen.getByTestId("preset-portrait-btn")).toBeInTheDocument();
    expect(screen.getByTestId("start-export-btn")).toBeInTheDocument();
  });

  it("allows switching presets between landscape and portrait", () => {
    render(
      <ExportVideoModal
        isOpen={true}
        onClose={vi.fn()}
        workflowId={mockWorkflowId}
      />
    );

    const landscapeBtn = screen.getByTestId("preset-landscape-btn");
    const portraitBtn = screen.getByTestId("preset-portrait-btn");

    expect(landscapeBtn).toHaveAttribute("aria-checked", "true");
    expect(portraitBtn).toHaveAttribute("aria-checked", "false");

    fireEvent.click(portraitBtn);
    expect(landscapeBtn).toHaveAttribute("aria-checked", "false");
    expect(portraitBtn).toHaveAttribute("aria-checked", "true");
  });

  it("calls onClose when close or cancel button is clicked", () => {
    const onClose = vi.fn();
    render(
      <ExportVideoModal
        isOpen={true}
        onClose={onClose}
        workflowId={mockWorkflowId}
      />
    );

    fireEvent.click(screen.getByTestId("close-export-modal-btn"));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId("cancel-export-btn"));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("starts export, displays progress, and renders download links on completion", async () => {
    const createSpy = vi.spyOn(MockApiClient.prototype, "createExport");
    const expQueued: Export = {
      id: "exp-test-1",
      workflow_id: mockWorkflowId,
      revision: 1,
      title: "Test Tutorial",
      preset: "landscape",
      voice: "en_US-ljspeech-medium",
      status: "rendering",
      progress: 65,
      created_at: new Date().toISOString(),
      download_url: "/api/v1/exports/exp-test-1/download",
      captions_url: "/api/v1/exports/exp-test-1/captions.vtt",
    };

    const expReady: Export = {
      ...expQueued,
      status: "ready",
      progress: 100,
      duration_ms: 15400,
      size_bytes: 3500000,
      finished_at: new Date().toISOString(),
    };

    createSpy.mockResolvedValueOnce(expQueued);
    vi.spyOn(MockApiClient.prototype, "getExport").mockResolvedValue(expReady);

    render(
      <ExportVideoModal
        isOpen={true}
        onClose={vi.fn()}
        workflowId={mockWorkflowId}
      />
    );

    // Click start export
    fireEvent.click(screen.getByTestId("start-export-btn"));

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(mockWorkflowId, "landscape");
    });

    // Rendering container should appear with progress
    expect(screen.getByTestId("export-rendering-container")).toBeInTheDocument();
    expect(screen.getByTestId("export-progress-percent")).toHaveTextContent("65%");

    // Next poll resolves ready (poll interval is 2s)
    await waitFor(
      () => {
        expect(screen.getByTestId("export-ready-container")).toBeInTheDocument();
      },
      { timeout: 4000 }
    );

    expect(screen.getByText("Export Complete")).toBeInTheDocument();
    expect(screen.getByTestId("download-video-btn")).toBeInTheDocument();
    expect(screen.getByTestId("download-captions-btn")).toBeInTheDocument();

    const downloadLink = screen.getByTestId("download-video-btn") as HTMLAnchorElement;
    expect(downloadLink.getAttribute("href")).toContain("/download");

    const captionsLink = screen.getByTestId("download-captions-btn") as HTMLAnchorElement;
    expect(captionsLink.getAttribute("href")).toContain("/captions.vtt");

    // Click export another preset to reset
    fireEvent.click(screen.getByTestId("export-another-btn"));
    expect(screen.getByTestId("start-export-btn")).toBeInTheDocument();
  });

  it("displays error message if export creation fails", async () => {
    vi.spyOn(MockApiClient.prototype, "createExport").mockRejectedValueOnce(
      new Error("Queue is currently full")
    );

    render(
      <ExportVideoModal
        isOpen={true}
        onClose={vi.fn()}
        workflowId={mockWorkflowId}
      />
    );

    fireEvent.click(screen.getByTestId("start-export-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("export-error-banner")).toBeInTheDocument();
    });

    expect(screen.getByText("Queue is currently full")).toBeInTheDocument();
  });

  it("displays failure screen if export job failed", async () => {
    const failedExport: Export = {
      id: "exp-failed-123",
      workflow_id: mockWorkflowId,
      revision: 1,
      title: "Failed export",
      preset: "landscape",
      voice: "en_US-ljspeech-medium",
      status: "failed",
      progress: 40,
      created_at: new Date().toISOString(),
      error: {
        code: "render_failed",
        message: "Node Remotion process crashed with SIGKILL",
      },
    };

    vi.spyOn(MockApiClient.prototype, "createExport").mockResolvedValueOnce(failedExport);

    render(
      <ExportVideoModal
        isOpen={true}
        onClose={vi.fn()}
        workflowId={mockWorkflowId}
      />
    );

    fireEvent.click(screen.getByTestId("start-export-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("export-failed-container")).toBeInTheDocument();
    });

    expect(screen.getByText("Export Failed")).toBeInTheDocument();
    expect(screen.getByText("Node Remotion process crashed with SIGKILL")).toBeInTheDocument();

    // Click try again
    fireEvent.click(screen.getByTestId("retry-export-btn"));
    expect(screen.getByTestId("start-export-btn")).toBeInTheDocument();
  });
});
