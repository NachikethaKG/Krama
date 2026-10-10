import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StepProgressItem } from "@/components/execution/step-progress-item";

describe("StepProgressItem", () => {
  it("renders pending state with sequence number and instruction", () => {
    render(
      <StepProgressItem
        seq={1}
        instructionText="Open the + menu at the top right."
        actionType="click"
        targetRole="button"
        targetName="Create"
        status="pending"
        risk="low"
      />
    );

    const item = screen.getByTestId("step-progress-item");
    expect(item).toHaveAttribute("data-step-seq", "1");
    expect(item).toHaveAttribute("data-step-status", "pending");
    expect(screen.getByTestId("step-pending-icon")).toBeInTheDocument();
    expect(screen.getByTestId("step-instruction")).toHaveTextContent("Open the + menu at the top right.");
    expect(screen.getByText("click")).toBeInTheDocument();
  });

  it("renders started state with spinner and executing badge", () => {
    render(
      <StepProgressItem
        seq={2}
        instructionText="Click New Repository in the menu."
        actionType="click"
        status="started"
        risk="medium"
      />
    );

    const item = screen.getByTestId("step-progress-item");
    expect(item).toHaveAttribute("data-step-status", "started");
    expect(screen.getByTestId("step-spinner")).toBeInTheDocument();
    expect(screen.getByTestId("step-running-badge")).toHaveTextContent("Executing…");
  });

  it("renders verified state with checkmark icon and verification methods", () => {
    render(
      <StepProgressItem
        seq={3}
        instructionText="Enter demo-repo as repository name."
        actionType="fill"
        status="verified"
        methods={["dom", "aria"]}
        confidence={1.0}
        risk="low"
      />
    );

    const item = screen.getByTestId("step-progress-item");
    expect(item).toHaveAttribute("data-step-status", "verified");
    expect(screen.getByTestId("step-verified-icon")).toBeInTheDocument();
    expect(screen.getByTestId("step-verified-badge")).toHaveTextContent("Verified(100%)");
    expect(screen.getByText("dom")).toBeInTheDocument();
    expect(screen.getByText("aria")).toBeInTheDocument();
  });

  it("renders failed state with error callout and observed details", () => {
    render(
      <StepProgressItem
        seq={4}
        instructionText="Click Create Repository button."
        actionType="click"
        status="failed"
        error="Button not clickable; modal backdrop intercepted click"
        observedUrl="/repo/create"
        observedTitle="Repository creation error"
        risk="high"
      />
    );

    const item = screen.getByTestId("step-progress-item");
    expect(item).toHaveAttribute("data-step-status", "failed");
    expect(screen.getByTestId("step-failed-icon")).toBeInTheDocument();
    expect(screen.getByTestId("step-failed-badge")).toHaveTextContent("Failed");
    expect(screen.getByTestId("step-error-callout")).toHaveTextContent(
      "Button not clickable; modal backdrop intercepted click"
    );
    expect(screen.getByText(/Observed URL: \/repo\/create/)).toBeInTheDocument();
    expect(screen.getByText(/Observed Title: Repository creation error/)).toBeInTheDocument();
  });
});
