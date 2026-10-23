import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { RunStatusBanners } from "@/components/runs/RunStatusBanners";

describe("RunStatusBanners Component", () => {
  it("renders null when status is running or idle", () => {
    const { container, rerender } = render(<RunStatusBanners status="running" />);
    expect(container.firstChild).toBeNull();

    rerender(<RunStatusBanners status="idle" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders paused banner with trigger context and dispatches resume callback", async () => {
    const handleResume = vi.fn();

    render(
      <RunStatusBanners
        status="paused"
        pausedState={{
          reason: "destructive_action",
          message: "Repository deletion requires explicit confirmation.",
          stepSeq: 4,
          triggerContext: "github_delete_repo",
        }}
        onResume={handleResume}
      />,
    );

    const banner = screen.getByRole("alert");
    expect(banner).toHaveAttribute("data-testid", "paused-banner");
    expect(
      screen.getByText(/Execution Paused: Action requires manual approval/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Repository deletion requires explicit confirmation."),
    ).toBeInTheDocument();
    expect(screen.getByText("github_delete_repo")).toBeInTheDocument();
    expect(screen.getByText(/at Step 4/i)).toBeInTheDocument();

    const resumeBtn = screen.getByTestId("allow-resume-button");
    fireEvent.click(resumeBtn);
    expect(handleResume).toHaveBeenCalledTimes(1);
  });

  it("dispatches abort callback when abort button is clicked in paused banner", () => {
    const handleAbort = vi.fn();

    render(
      <RunStatusBanners
        status="paused"
        pausedState={{
          reason: "destructive_action",
          message: "Repository deletion requires explicit confirmation.",
        }}
        onAbort={handleAbort}
      />,
    );

    const abortBtn = screen.getByTestId("abort-run-button");
    fireEvent.click(abortBtn);
    expect(handleAbort).toHaveBeenCalledTimes(1);
  });

  it("renders failed banner with error and expected vs observed diff card", () => {
    render(
      <RunStatusBanners
        status="failed"
        failedState={{
          stepSeq: 3,
          error: "Button with text 'Save changes' was not enabled",
          expected: { buttonState: "enabled", selector: "#submit-btn" },
          observed: { buttonState: "disabled", selector: "#submit-btn" },
        }}
      />,
    );

    const banner = screen.getByRole("alert");
    expect(banner).toHaveAttribute("data-testid", "failed-banner");
    expect(
      screen.getByText(/Execution Failed at Step 3: Button with text 'Save changes' was not enabled/i),
    ).toBeInTheDocument();

    const diffCard = screen.getByTestId("expected-observed-card");
    expect(diffCard).toBeInTheDocument();
    expect(screen.getByText("State Verification Mismatch")).toBeInTheDocument();
    expect(diffCard).toHaveTextContent("buttonState");
    expect(diffCard).toHaveTextContent("enabled");
    expect(diffCard).toHaveTextContent("disabled");
  });

  it("renders completed banner with link to interactive tutorial player", () => {
    render(
      <RunStatusBanners
        status="completed"
        workflowId="wf-demo-123"
      />,
    );

    expect(screen.getByTestId("completed-banner")).toBeInTheDocument();
    expect(screen.getByText("Workflow Execution Complete")).toBeInTheDocument();

    const tutorialBtn = screen.getByTestId("open-tutorial-btn");
    expect(tutorialBtn).toBeInTheDocument();
    expect(tutorialBtn).toHaveAttribute("href", "/tutorials/wf-demo-123");
  });
});
