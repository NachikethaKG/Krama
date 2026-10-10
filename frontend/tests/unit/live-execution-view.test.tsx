import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LiveExecutionView } from "@/components/execution/live-execution-view";
import { MockApiClient } from "@/lib/api";
import {
  giteaEventsFixture,
  giteaFailedEventsFixture,
  giteaPausedEventsFixture,
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

  it("renders not found error view when workflow ID is invalid", async () => {
    render(<LiveExecutionView workflowId="invalid-non-existent-wf" speed={1000} />);

    await waitFor(() => {
      expect(screen.getByTestId("live-execution-error")).toBeInTheDocument();
    });
    expect(screen.getByText("Workflow Not Found")).toBeInTheDocument();
  });
});
