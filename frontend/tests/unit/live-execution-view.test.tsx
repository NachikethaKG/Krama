import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LiveExecutionView } from "@/components/execution/live-execution-view";
import { ApiRequestError, MockApiClient } from "@/lib/api";

const FAST = 1000;
const T = { timeout: 4000 };

function view(runId: string, client = new MockApiClient()) {
  render(<LiveExecutionView runId={runId} client={client} speed={FAST} />);
  return client;
}

describe("LiveExecutionView", () => {
  it("streams a run to completion and links to its verified workflow", async () => {
    view("default");
    await waitFor(() => expect(screen.getByTestId("execution-header")).toBeInTheDocument());
    expect(screen.getByTestId("elapsed-timer")).toBeInTheDocument();
    expect(screen.getByTestId("execution-step-list")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/Create a repository in local Gitea/i)).toBeInTheDocument());

    await waitFor(() => expect(screen.getByTestId("completion-banner")).toBeInTheDocument(), T);
    expect(screen.getByTestId("view-workflow-link")).toHaveAttribute("href", "/runs/default");
    // The verified run's tutorial is one click away.
    await waitFor(() =>
      expect(screen.getByTestId("watch-tutorial-link").getAttribute("href")).toMatch(/^\/tutorials\/[0-9a-f-]{36}$/),
    );
  });

  it("a destructive pause shows ONE control: the modal, not the banner", async () => {
    view("paused");
    await waitFor(() => expect(screen.getByTestId("policy-confirmation-modal")).toBeInTheDocument(), T);
    expect(screen.queryByTestId("pause-banner")).not.toBeInTheDocument();
  });

  it("Escape does not deny a paused step", async () => {
    view("paused");
    await waitFor(() => expect(screen.getByTestId("policy-confirmation-modal")).toBeInTheDocument(), T);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByTestId("policy-confirmation-modal")).toBeInTheDocument();
    expect(screen.queryByTestId("cancelled-banner")).not.toBeInTheDocument();
  });

  it("deny in the modal cancels the run", async () => {
    view("paused");
    await waitFor(() => expect(screen.getByTestId("modal-deny-btn")).toBeInTheDocument(), T);
    fireEvent.click(screen.getByTestId("modal-deny-btn"));
    await waitFor(() => expect(screen.getByTestId("cancelled-banner")).toBeInTheDocument(), T);
    expect(screen.getByTestId("back-to-plan-btn")).toHaveAttribute("href", "/workflows/paused/approval");
    expect(screen.queryByTestId("retry-run-btn")).not.toBeInTheDocument();
  });

  it("recovery_exhausted uses the pause banner; the replan indicator has no buttons of its own", async () => {
    view("replan");
    await waitFor(() => expect(screen.getByTestId("pause-banner")).toBeInTheDocument(), T);
    expect(screen.queryByTestId("policy-confirmation-modal")).not.toBeInTheDocument();
    expect(screen.getByTestId("resume-run-btn")).toHaveTextContent(/once more/i);
    expect(screen.getByTestId("replan-badge-exhausted")).toBeInTheDocument();
    expect(screen.queryByTestId("replan-takeover-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("replan-abort-btn")).not.toBeInTheDocument();
  });

  it("replan_review shows the proposed steps with Allow / Deny", async () => {
    view("replan-review");
    await waitFor(() => expect(screen.getByTestId("proposed-steps")).toBeInTheDocument(), T);
    expect(screen.getByTestId("pause-banner")).toHaveAttribute("data-pause-reason", "replan_review");
    expect(screen.getAllByTestId("proposed-step-item")[0]).toHaveTextContent("Open the New Repository page directly.");
    expect(screen.queryByTestId("replan-badge-exhausted")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("resume-run-btn"));
    await waitFor(() => expect(screen.getByTestId("completion-banner")).toBeInTheDocument(), T);
  });

  it("a policy stop (run.failed, policy_stop) shows the takeover screen without Resume", async () => {
    view("blocked");
    await waitFor(() => expect(screen.getByTestId("automation-restricted-screen")).toBeInTheDocument(), T);
    expect(screen.getByTestId("barrier-type-badge")).toHaveTextContent(/CAPTCHA/i);
    expect(screen.queryByTestId("takeover-resume-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("failure-banner")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pause-banner")).not.toBeInTheDocument();
  });

  it("a failed run shows the failure banner and the before/after screenshots, without Retry", async () => {
    view("failed");
    await waitFor(() => expect(screen.getByTestId("failure-banner")).toBeInTheDocument(), T);
    expect(screen.getByTestId("failure-code-badge")).toHaveTextContent("validation_error");
    expect(screen.getByTestId("failed-step-details")).toBeInTheDocument();
    expect(screen.queryByTestId("retry-run-btn")).not.toBeInTheDocument();
    expect(screen.getByTestId("diagnostic-step-seq")).toHaveTextContent("Step #2");
    expect(screen.getByTestId("previous-screenshot-img")).toHaveAttribute("src", "/screenshots/step-1.png");
    expect(screen.getByTestId("observed-screenshot-img")).toHaveAttribute("src", "/mock-observed.png");
  });

  it("cancel goes through the API and ends with the cancelled banner", async () => {
    view("paused");
    await waitFor(() => expect(screen.getByTestId("cancel-run-btn")).toBeInTheDocument(), T);
    fireEvent.click(screen.getByTestId("cancel-run-btn"));
    await waitFor(() => expect(screen.getByTestId("cancelled-banner")).toBeInTheDocument(), T);
  });

  it("shows API errors in a banner even after the run loaded", async () => {
    const client = new MockApiClient();
    client.confirmRun = async () => {
      throw new ApiRequestError("Run is running, not paused at step 2", 409, {
        code: "run_not_active",
        message: "Run is running, not paused at step 2",
      });
    };
    view("paused", client);
    await waitFor(() => expect(screen.getByTestId("modal-allow-btn")).toBeInTheDocument(), T);
    fireEvent.click(screen.getByTestId("modal-allow-btn"));
    await waitFor(() => expect(screen.getByTestId("execution-error-banner")).toHaveTextContent(/no longer waiting/i));
    expect(screen.getByTestId("policy-confirmation-modal")).toBeInTheDocument();
  });

  it("shows the not-found view for an unknown run id", async () => {
    view("invalid-non-existent-run");
    await waitFor(() => expect(screen.getByTestId("live-execution-error")).toBeInTheDocument());
    expect(screen.getByText("Run Not Found")).toBeInTheDocument();
  });
});
