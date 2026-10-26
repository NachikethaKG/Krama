import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { RunActionPanel } from "@/components/runs/RunActionPanel";

describe("RunActionPanel Component", () => {
  it("renders null when status is idle or running", () => {
    const { container, rerender } = render(<RunActionPanel status="running" />);
    expect(screen.getByTestId("run-action-panel")).toBeInTheDocument();
    expect(container.querySelector('[role="alert"]')).toBeNull();

    rerender(<RunActionPanel status="idle" />);
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it("renders paused state with context and triggers onResume", () => {
    const handleResume = vi.fn();
    render(
      <RunActionPanel
        status="paused"
        pausedState={{
          reason: "destructive_action",
          message: "Action requires manual approval",
          triggerContext: "github_danger_zone: delete branch",
          stepSeq: 2,
        }}
        onResume={handleResume}
      />,
    );

    expect(screen.getByTestId("paused-banner")).toBeInTheDocument();
    expect(
      screen.getByText(/Execution Paused: Action requires manual approval \/ bot barrier detected/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/github_danger_zone: delete branch/i)).toBeInTheDocument();

    const resumeBtn = screen.getByTestId("allow-resume-button");
    fireEvent.click(resumeBtn);
    expect(handleResume).toHaveBeenCalledTimes(1);
  });

  it("triggers onAbort when Abort Run button is clicked", () => {
    const handleAbort = vi.fn();
    render(
      <RunActionPanel
        status="paused"
        pausedState={{
          reason: "bot_barrier",
          message: "Cloudflare CAPTCHA challenge encountered",
        }}
        onAbort={handleAbort}
      />,
    );

    const abortBtn = screen.getByTestId("abort-run-button");
    fireEvent.click(abortBtn);
    expect(handleAbort).toHaveBeenCalledTimes(1);
  });

  it("renders completed state with CTA link to tutorial", () => {
    render(
      <RunActionPanel
        status="completed"
        workflowId="wf-action-panel-test"
      />,
    );

    expect(screen.getByTestId("completed-banner")).toBeInTheDocument();
    const btn = screen.getByTestId("open-tutorial-btn");
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("href", "/tutorials/wf-action-panel-test");
  });
});
