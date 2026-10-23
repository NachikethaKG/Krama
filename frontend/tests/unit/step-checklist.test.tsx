import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StepChecklist } from "@/components/runs/StepChecklist";
import type { StreamStep } from "@/hooks/useRunStream";

describe("StepChecklist Component", () => {
  const sampleSteps: StreamStep[] = [
    { seq: 1, instructionText: "Navigate to repository dashboard", status: "completed", durationMs: 1200 },
    { seq: 2, instructionText: "Click on New Issue button", status: "running" },
    { seq: 3, instructionText: "Fill in issue title and body", status: "pending" },
    { seq: 4, instructionText: "Submit issue form", status: "pending" },
  ];

  it("renders all planned steps with sequential ordering and descriptions", () => {
    render(<StepChecklist steps={sampleSteps} currentStepSeq={2} />);

    expect(screen.getByTestId("step-checklist")).toBeInTheDocument();
    expect(screen.getByText("Execution Steps")).toBeInTheDocument();
    expect(screen.getByTestId("step-count-badge")).toHaveTextContent("4");
    expect(screen.getByText("Current: Step 2")).toBeInTheDocument();

    expect(screen.getByText("Navigate to repository dashboard")).toBeInTheDocument();
    expect(screen.getByText("Click on New Issue button")).toBeInTheDocument();
    expect(screen.getByText("Fill in issue title and body")).toBeInTheDocument();
    expect(screen.getByText("Submit issue form")).toBeInTheDocument();
  });

  it("displays correct status indicators: pending, running, completed", () => {
    render(<StepChecklist steps={sampleSteps} currentStepSeq={2} />);

    // Step 1: Completed checkmark and duration
    const completedBadge = screen.getByTestId("step-completed");
    expect(completedBadge).toBeInTheDocument();
    expect(screen.getByText("1.2s")).toBeInTheDocument();

    // Step 2: Running spinner
    const runningSpinner = screen.getByTestId("step-running");
    expect(runningSpinner).toBeInTheDocument();

    // Steps 3 & 4: Pending circles
    const pendingBadges = screen.getAllByTestId("step-pending");
    expect(pendingBadges.length).toBe(2);
  });

  it("renders failed step with rose badge and error message", () => {
    const failedSteps: StreamStep[] = [
      {
        seq: 1,
        instructionText: "Find Submit button",
        status: "failed",
        error: "Element button[type='submit'] was not found within 10000ms",
      },
    ];

    render(<StepChecklist steps={failedSteps} currentStepSeq={1} />);

    expect(screen.getByTestId("step-failed")).toBeInTheDocument();
    expect(screen.getByTestId("step-error-message")).toHaveTextContent(
      "Element button[type='submit'] was not found within 10000ms",
    );
  });

  it("renders paused step with amber badge", () => {
    const pausedSteps: StreamStep[] = [
      {
        seq: 1,
        instructionText: "Delete branch production",
        status: "paused",
      },
    ];

    render(<StepChecklist steps={pausedSteps} currentStepSeq={1} />);

    expect(screen.getByTestId("step-paused")).toBeInTheDocument();
    expect(screen.getByText("paused")).toBeInTheDocument();
  });

  it("displays empty state when steps list is empty", () => {
    render(<StepChecklist steps={[]} />);

    expect(screen.getByText(/Waiting for execution plan/i)).toBeInTheDocument();
  });
});
