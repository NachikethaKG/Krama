import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FailureBanner } from "@/components/execution/failure-banner";
import { PauseBanner } from "@/components/execution/pause-banner";

describe("PauseBanner", () => {
  it("renders pause alert with reason and step sequence", () => {
    const handleResume = vi.fn();
    render(
      <PauseBanner
        reason="destructive_action"
        stepSeq={2}
        message="Destructive action requires confirmation before proceeding"
        onResume={handleResume}
      />
    );

    const banner = screen.getByTestId("pause-banner");
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveAttribute("data-pause-reason", "destructive_action");
    expect(screen.getByText("Execution Paused at Step 2")).toBeInTheDocument();
    expect(
      screen.getByText("Destructive action requires confirmation before proceeding")
    ).toBeInTheDocument();

    const resumeBtn = screen.getByTestId("resume-run-btn");
    fireEvent.click(resumeBtn);
    expect(handleResume).toHaveBeenCalledTimes(1);
  });
});

describe("FailureBanner", () => {
  it("renders failure alert with error code, message and retry CTA", () => {
    const handleRetry = vi.fn();
    render(
      <FailureBanner
        error={{
          code: "validation_error",
          message: "Step 2 failed verification: target URL did not match expected path",
        }}
        onRetry={handleRetry}
      />
    );

    const banner = screen.getByTestId("failure-banner");
    expect(banner).toBeInTheDocument();
    expect(screen.getByText("Workflow Execution Failed")).toBeInTheDocument();
    expect(screen.getByTestId("failure-code-badge")).toHaveTextContent("validation_error");
    expect(screen.getByTestId("failure-message")).toHaveTextContent(
      "Step 2 failed verification: target URL did not match expected path"
    );

    const retryBtn = screen.getByTestId("retry-run-btn");
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledTimes(1);
  });
});
