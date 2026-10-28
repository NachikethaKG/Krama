import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StepEvidenceCard, getConfidenceDetails } from "@/components/runs/StepEvidenceCard";
import type { StepEvidenceDetail } from "@/lib/types";
import { mockRunDetails } from "@/lib/fixtures";

describe("StepEvidenceCard", () => {
  const sampleSteps = mockRunDetails["run-1"].steps;

  it("renders step instruction, sequence number, action type, and status badge", () => {
    const step = sampleSteps[0];
    render(<StepEvidenceCard step={step} />);

    expect(screen.getByTestId("step-seq-badge")).toHaveTextContent("1");
    expect(screen.getByTestId("step-instruction")).toHaveTextContent(step.instructionText);
    expect(screen.getByTestId("step-action-target")).toHaveTextContent("Clicked");
    expect(screen.getByTestId("step-status")).toHaveTextContent("Verified");
  });

  it("renders distinct verification method badges correctly", () => {
    // Step 1: aria
    const { rerender } = render(<StepEvidenceCard step={sampleSteps[0]} />);
    expect(screen.getByTestId("verification-method-badge")).toHaveAttribute("data-method", "aria");
    expect(screen.getByTestId("verification-method-badge")).toHaveTextContent("Page content");

    // Step 2: url_dom
    rerender(<StepEvidenceCard step={sampleSteps[1]} />);
    expect(screen.getByTestId("verification-method-badge")).toHaveAttribute("data-method", "url_dom");
    expect(screen.getByTestId("verification-method-badge")).toHaveTextContent("Page address");

    // Step 4: network
    rerender(<StepEvidenceCard step={sampleSteps[3]} />);
    expect(screen.getByTestId("verification-method-badge")).toHaveAttribute("data-method", "network");
    expect(screen.getByTestId("verification-method-badge")).toHaveTextContent("Site's answer");

    // Step 5: vision
    rerender(<StepEvidenceCard step={sampleSteps[4]} />);
    expect(screen.getByTestId("verification-method-badge")).toHaveAttribute("data-method", "vision");
    expect(screen.getByTestId("verification-method-badge")).toHaveTextContent("Screenshot");
  });

  it("renders confidence scores with accurate percentage and rating", () => {
    // 1.0 -> 100%, "Sure"
    const { rerender } = render(<StepEvidenceCard step={sampleSteps[0]} />);
    expect(screen.getByTestId("confidence-score")).toHaveTextContent("100%");
    expect(screen.getByText("Sure")).toBeInTheDocument();

    // 0.85 -> 85%, "Fairly sure"
    rerender(<StepEvidenceCard step={sampleSteps[3]} />);
    expect(screen.getByTestId("confidence-score")).toHaveTextContent("85%");
    expect(screen.getByText("Fairly sure")).toBeInTheDocument();

    // Low confidence in failed step
    const failedStep = mockRunDetails["run-2"].steps[1];
    rerender(<StepEvidenceCard step={failedStep} />);
    expect(screen.getByTestId("confidence-score")).toHaveTextContent("45%");
    expect(screen.getByText("Unsure")).toBeInTheDocument();
  });

  it("renders screenshot image when available", () => {
    const step = sampleSteps[0];
    render(<StepEvidenceCard step={step} />);

    const img = screen.getByTestId("step-screenshot");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", step.screenshotUrl);
  });

  it("handles broken image loading by displaying fallback placeholder", () => {
    const step = sampleSteps[0];
    render(<StepEvidenceCard step={step} />);

    const img = screen.getByTestId("step-screenshot");
    fireEvent.error(img);

    expect(screen.queryByTestId("step-screenshot")).not.toBeInTheDocument();
    const placeholder = screen.getByTestId("step-screenshot-placeholder");
    expect(placeholder).toBeInTheDocument();
    expect(placeholder).toHaveTextContent("Screenshot failed to load from artifact store");
  });

  it("immediately displays placeholder when screenshot is missing/undefined", () => {
    const missingScreenshotStep: StepEvidenceDetail = {
      ...sampleSteps[0],
      screenshotUrl: undefined,
      evidence: {
        ...sampleSteps[0].evidence,
        screenshotUrl: undefined,
      },
    };
    render(<StepEvidenceCard step={missingScreenshotStep} />);

    expect(screen.queryByTestId("step-screenshot")).not.toBeInTheDocument();
    const placeholder = screen.getByTestId("step-screenshot-placeholder");
    expect(placeholder).toBeInTheDocument();
    expect(placeholder).toHaveTextContent("No screenshot captured for this step");
  });

  it("toggles expected vs observed state details", () => {
    const step = sampleSteps[0];
    render(<StepEvidenceCard step={step} />);

    expect(screen.queryByTestId("step-state-details")).not.toBeInTheDocument();
    const toggleButton = screen.getByTestId("toggle-state-details-button");
    fireEvent.click(toggleButton);

    expect(screen.getByTestId("step-state-details")).toBeInTheDocument();
    expect(screen.getByText("Expected State")).toBeInTheDocument();
    expect(screen.getByText("Observed State")).toBeInTheDocument();
  });

  describe("getConfidenceDetails helper", () => {
    it("handles 0..1 scale and 0..100 scale", () => {
      expect(getConfidenceDetails(0.95).percentage).toBe(95);
      expect(getConfidenceDetails(95).percentage).toBe(95);
      expect(getConfidenceDetails(0.75).percentage).toBe(75);
      expect(getConfidenceDetails(0.40).percentage).toBe(40);
    });
  });
});
