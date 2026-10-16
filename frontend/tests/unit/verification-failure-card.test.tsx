import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { VerificationFailureCard } from "@/components/diagnostics/VerificationFailureCard";

describe("VerificationFailureCard", () => {
  it("renders header with step sequence, instruction text, and resolved failed layer badge", () => {
    render(
      <VerificationFailureCard
        stepSeq={2}
        instructionText="Click New Repository in the menu."
        failureReason="Element not found: button 'Create Repository'"
        failedLayer="dom"
        expected={{
          url_matches: "^/repo/create$",
          visible: [{ role: "button", name: "Create Repository" }],
        }}
        observed={{
          url: "/repo/error",
          title: "500 Internal Server Error",
          error: "Element button not present in DOM",
        }}
      />
    );

    expect(screen.getByTestId("verification-failure-card")).toBeInTheDocument();
    expect(screen.getByTestId("diagnostic-step-seq")).toHaveTextContent("Step #2");
    expect(screen.getByTestId("diagnostic-instruction")).toHaveTextContent("Click New Repository in the menu.");
    expect(screen.getByTestId("failed-layer-badge")).toHaveTextContent("DOM Verifier");
    expect(screen.getByTestId("diagnostic-reason")).toHaveTextContent("Element not found: button 'Create Repository'");
  });

  it("resolves URL Verifier layer when expected URL pattern does not match observed URL", () => {
    render(
      <VerificationFailureCard
        stepSeq={1}
        expected={{
          url_matches: "^/repo/create$",
        }}
        observed={{
          url: "/repo/different",
        }}
      />
    );

    expect(screen.getByTestId("failed-layer-badge")).toHaveTextContent("URL Verifier");
  });

  it("displays Expected (X) vs. Observed (Y) textual breakdown", () => {
    render(
      <VerificationFailureCard
        stepSeq={3}
        expected={{
          url_matches: "^/repo/new$",
          title_contains: "New Repository",
          visible: [{ role: "button", name: "Submit" }],
          absent: [{ role: "alert", name: "Error" }],
          field_values: [{ role: "textbox", name: "Repository Name", value: "demo-repo" }],
        }}
        observed={{
          url: "/repo/login",
          title: "Sign In Required",
          error: "Session expired or redirected unexpectedly",
        }}
      />
    );

    expect(screen.getByTestId("expected-state-box")).toBeInTheDocument();
    expect(screen.getByTestId("expected-url")).toHaveTextContent("^/repo/new$");
    expect(screen.getByTestId("expected-title")).toHaveTextContent('contains "New Repository"');
    expect(screen.getByTestId("expected-visible-elements")).toHaveTextContent('button "Submit"');
    expect(screen.getByTestId("expected-absent-elements")).toHaveTextContent('absent: alert "Error"');
    expect(screen.getByTestId("expected-field-values")).toHaveTextContent('Repository Name = "demo-repo"');

    expect(screen.getByTestId("observed-state-box")).toBeInTheDocument();
    expect(screen.getByTestId("observed-url")).toHaveTextContent("/repo/login");
    expect(screen.getByTestId("observed-title")).toHaveTextContent("Sign In Required");
    expect(screen.getByTestId("observed-error")).toHaveTextContent("Session expired or redirected unexpectedly");
  });

  it("renders side-by-side screenshot images when both URLs are provided", () => {
    render(
      <VerificationFailureCard
        stepSeq={2}
        previousScreenshotUrl="/screenshots/step-1.png"
        observedScreenshotUrl="/mock-observed.png"
      />
    );

    const expectedImg = screen.getByTestId("previous-screenshot-img");
    const observedImg = screen.getByTestId("observed-screenshot-img");

    expect(expectedImg).toBeInTheDocument();
    expect(expectedImg).toHaveAttribute("src", "/screenshots/step-1.png");
    expect(expectedImg).toHaveAttribute("alt", "Page before this step");

    expect(observedImg).toBeInTheDocument();
    expect(observedImg).toHaveAttribute("src", "/mock-observed.png");
    expect(observedImg).toHaveAttribute("alt", "Observed state capture");
  });

  it("gracefully falls back to placeholder when screenshots are missing", () => {
    render(
      <VerificationFailureCard
        stepSeq={2}
        previousScreenshotUrl={null}
        observedScreenshotUrl={undefined}
      />
    );

    expect(screen.getByTestId("previous-screenshot-placeholder")).toHaveTextContent(
      "No earlier screenshot"
    );
    expect(screen.getByTestId("observed-screenshot-placeholder")).toHaveTextContent(
      "Screenshot not captured or failed to load"
    );
  });

  it("handles image load errors by swapping to broken-image fallback placeholder", () => {
    render(
      <VerificationFailureCard
        stepSeq={2}
        previousScreenshotUrl="/broken-previous.png"
        observedScreenshotUrl="/broken-observed.png"
      />
    );

    const expectedImg = screen.getByTestId("previous-screenshot-img");
    const observedImg = screen.getByTestId("observed-screenshot-img");

    fireEvent.error(expectedImg);
    fireEvent.error(observedImg);

    expect(screen.getByTestId("previous-screenshot-placeholder")).toBeInTheDocument();
    expect(screen.getByTestId("observed-screenshot-placeholder")).toBeInTheDocument();
  });

  it("calls onRetryReplan when Retry Replan button is clicked", () => {
    const onRetryReplan = vi.fn();
    render(
      <VerificationFailureCard
        stepSeq={2}
        onRetryReplan={onRetryReplan}
      />
    );

    const retryBtn = screen.getByTestId("diagnostic-retry-btn");
    expect(retryBtn).toBeInTheDocument();
    fireEvent.click(retryBtn);
    expect(onRetryReplan).toHaveBeenCalledTimes(1);
  });
});
