import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LiveExecutionView } from "@/components/execution/live-execution-view";
import { MockApiClient } from "@/lib/api";
import {
  giteaEventsFixture,
  giteaFailedEventsFixture,
  giteaPausedEventsFixture,
  giteaReplanEventsFixture,
  giteaWorkflowFixture,
} from "@/lib/fixtures";

describe("LiveExecutionView", () => {
  it("renders header, timer, progress bar, and steps list", async () => {
    const client = new MockApiClient(giteaEventsFixture);
    render(
      <LiveExecutionView
        workflowId="default"
        client={client}
        speed={1000}
        initialWorkflow={giteaWorkflowFixture}
      />
    );

    expect(screen.getByTestId("execution-header")).toBeInTheDocument();
    expect(screen.getByTestId("elapsed-timer")).toBeInTheDocument();
    expect(screen.getByTestId("execution-progress-bar")).toBeInTheDocument();
    expect(screen.getByTestId("execution-step-list")).toBeInTheDocument();

    await waitFor(
      () => {
        expect(screen.getByTestId("completion-banner")).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it("renders PauseBanner when execution is paused", async () => {
    const client = new MockApiClient(giteaPausedEventsFixture);
    render(
      <LiveExecutionView
        workflowId="paused"
        client={client}
        speed={1000}
        initialWorkflow={giteaWorkflowFixture}
      />
    );

    await waitFor(
      () => {
        expect(screen.getByTestId("pause-banner")).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    expect(screen.getByTestId("resume-run-btn")).toBeInTheDocument();
  });

  it("renders FailureBanner when execution fails", async () => {
    const client = new MockApiClient(giteaFailedEventsFixture);
    render(
      <LiveExecutionView
        workflowId="failed"
        client={client}
        speed={1000}
        initialWorkflow={giteaWorkflowFixture}
      />
    );

    await waitFor(
      () => {
        expect(screen.getByTestId("failure-banner")).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    expect(screen.getByTestId("failure-code-badge")).toHaveTextContent("validation_error");
  });

  it("allows cancelling an active run and displays cancelled banner", async () => {
    const client = new MockApiClient(giteaEventsFixture);
    render(
      <LiveExecutionView
        workflowId="default"
        client={client}
        speed={1} // normal speed so it doesn't immediately complete
        initialWorkflow={giteaWorkflowFixture}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("cancel-run-btn")).toBeInTheDocument();
    });
    const cancelBtn = screen.getByTestId("cancel-run-btn");
    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.getByTestId("cancelled-banner")).toBeInTheDocument();
    });
    expect(screen.getByText("Workflow Execution Cancelled")).toBeInTheDocument();
    expect(screen.getByTestId("back-to-plan-btn")).toBeInTheDocument();
  });

  it("handles deny action when paused and transitions to cancelled", async () => {
    const client = new MockApiClient(giteaPausedEventsFixture);
    render(
      <LiveExecutionView
        workflowId="paused"
        client={client}
        speed={1000}
        initialWorkflow={giteaWorkflowFixture}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("pause-banner")).toBeInTheDocument();
    });

    const denyBtn = screen.getByTestId("deny-run-btn");
    expect(denyBtn).toBeInTheDocument();
    fireEvent.click(denyBtn);

    await waitFor(() => {
      expect(screen.getByTestId("cancelled-banner")).toBeInTheDocument();
    });
  });

  it("renders failure banner with failed step details and back to plan link", async () => {
    const client = new MockApiClient(giteaFailedEventsFixture);
    render(
      <LiveExecutionView
        workflowId="failed"
        client={client}
        speed={1000}
        initialWorkflow={giteaWorkflowFixture}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("failure-banner")).toBeInTheDocument();
    });

    expect(screen.getByTestId("failed-step-details")).toBeInTheDocument();
    expect(screen.getByTestId("back-to-plan-btn")).toBeInTheDocument();
  });

  it("renders not found error view when workflow ID is invalid", async () => {
    render(<LiveExecutionView workflowId="invalid-non-existent-wf" speed={1000} />);

    await waitFor(() => {
      expect(screen.getByTestId("live-execution-error")).toBeInTheDocument();
    });
    expect(screen.getByText("Workflow Not Found")).toBeInTheDocument();
  });

  it("renders VerificationFailureCard with expected vs observed details when a step fails", async () => {
    const client = new MockApiClient(giteaFailedEventsFixture);
    render(
      <LiveExecutionView
        workflowId="failed"
        client={client}
        speed={1000}
        initialWorkflow={giteaWorkflowFixture}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("verification-failure-card")).toBeInTheDocument();
    });

    expect(screen.getByTestId("diagnostic-step-seq")).toHaveTextContent("Step #2");
    expect(screen.getByTestId("expected-state-box")).toBeInTheDocument();
    expect(screen.getByTestId("observed-state-box")).toBeInTheDocument();
    expect(screen.getByTestId("expected-screenshot-img")).toBeInTheDocument();
    expect(screen.getByTestId("observed-screenshot-img")).toBeInTheDocument();
  });

  it("renders ReplanStatusIndicator and updates through recovery stream to exhausted", async () => {
    const client = new MockApiClient(giteaReplanEventsFixture);
    render(
      <LiveExecutionView
        workflowId="replan"
        client={client}
        speed={1000}
        initialWorkflow={giteaWorkflowFixture}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("replan-status-indicator")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByTestId("replan-badge-exhausted")).toBeInTheDocument();
    });

    expect(screen.getByTestId("replan-takeover-btn")).toBeInTheDocument();
    expect(screen.getByTestId("replan-abort-btn")).toBeInTheDocument();
  });
});
