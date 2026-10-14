import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApprovalScreen } from "@/components/approval-screen";
import { MockApiClient } from "@/lib/api";
import { giteaWorkflowFixture } from "@/lib/fixtures";

describe("ApprovalScreen", () => {
  it("renders workflow task header, step list, and approval controls from client", async () => {
    const client = new MockApiClient();
    render(<ApprovalScreen initialWorkflowId="default" client={client} />);

    await waitFor(() => {
      expect(screen.getByTestId("approval-screen")).toBeInTheDocument();
    });

    expect(screen.getByTestId("task-prompt")).toHaveTextContent(
      /Create a repository.*in local Gitea/i
    );
    expect(screen.getByTestId("target-url")).toHaveTextContent("http://localhost:3001");
    expect(screen.getAllByTestId("step-item")).toHaveLength(5);
    expect(screen.getByTestId("approve-btn")).toBeInTheDocument();
    expect(screen.getByTestId("reject-btn")).toBeInTheDocument();
  });

  it("handles approve flow and updates status to approved", async () => {
    render(<ApprovalScreen initialWorkflow={giteaWorkflowFixture} />);

    expect(screen.getByTestId("approve-btn")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("approve-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("approval-success-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("workflow-status-badge")).toHaveTextContent("approved");
  });

  it("handles reject flow and updates status to rejected", async () => {
    render(<ApprovalScreen initialWorkflow={giteaWorkflowFixture} />);

    expect(screen.getByTestId("reject-btn")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("reject-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("approval-rejected-banner")).toBeInTheDocument();
    });
    expect(screen.getByTestId("workflow-status-badge")).toHaveTextContent("rejected");
  });

  it("toggles inline edit mode and updates instruction text", async () => {
    render(<ApprovalScreen initialWorkflow={giteaWorkflowFixture} />);

    const editBtn = screen.getByTestId("edit-btn");
    expect(editBtn).toHaveTextContent("Edit Plan");
    fireEvent.click(editBtn);

    expect(editBtn).toHaveTextContent("Done Editing");
    const input1 = screen.getByTestId("step-input-1");
    expect(input1).toBeInTheDocument();

    fireEvent.change(input1, { target: { value: "New edited instruction text" } });
    expect(input1).toHaveValue("New edited instruction text");

    fireEvent.click(editBtn);
    await waitFor(() => {
      expect(editBtn).toHaveTextContent("Edit Plan");
    });
    expect(screen.getByText("New edited instruction text")).toBeInTheDocument();
  });

  it("allows reordering steps up and down in edit mode", async () => {
    render(<ApprovalScreen initialWorkflow={giteaWorkflowFixture} />);

    // Enter edit mode
    fireEvent.click(screen.getByTestId("edit-btn"));

    // Move step 1 down
    const moveDownBtn1 = screen.getByTestId("move-step-down-1");
    fireEvent.click(moveDownBtn1);

    // Now step 1 input has the previous step 2 instruction
    const input1 = screen.getByTestId("step-input-1") as HTMLInputElement;
    expect(input1.value).toBe(giteaWorkflowFixture.steps[1].instruction_text);

    // Move step 2 up
    const moveUpBtn2 = screen.getByTestId("move-step-up-2");
    fireEvent.click(moveUpBtn2);

    const restoredInput1 = screen.getByTestId("step-input-1") as HTMLInputElement;
    expect(restoredInput1.value).toBe(giteaWorkflowFixture.steps[0].instruction_text);
  });

  it("allows deleting steps in edit mode", async () => {
    render(<ApprovalScreen initialWorkflow={giteaWorkflowFixture} />);

    // Enter edit mode
    fireEvent.click(screen.getByTestId("edit-btn"));

    expect(screen.getAllByTestId("step-item")).toHaveLength(5);

    // Delete step 2
    const deleteBtn = screen.getByTestId("delete-step-2");
    fireEvent.click(deleteBtn);

    expect(screen.getAllByTestId("step-item")).toHaveLength(4);
  });

  it("displays 409 conflict banner on revision conflict and allows reloading latest plan", async () => {
    const conflictClient = new MockApiClient();
    conflictClient.updatePlan = async () => {
      throw new Error(
        "Request to /plans/default failed with status 409: Plan revision 1 is stale; the current one is 2"
      );
    };

    render(<ApprovalScreen initialWorkflowId="default" client={conflictClient} />);

    await waitFor(() => {
      expect(screen.getByTestId("approval-screen")).toBeInTheDocument();
    });

    // Enter edit mode
    fireEvent.click(screen.getByTestId("edit-btn"));
    // Click Done Editing to trigger updatePlan which throws 409
    fireEvent.click(screen.getByTestId("edit-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("plan-conflict-banner")).toBeInTheDocument();
    });
    expect(screen.getByText(/Plan revision 1 is stale/i)).toBeInTheDocument();

    // Click reload button
    const reloadBtn = screen.getByTestId("reload-plan-btn");
    fireEvent.click(reloadBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("plan-conflict-banner")).not.toBeInTheDocument();
    });
  });

  it("displays error view when workflow is not found", async () => {
    const client = new MockApiClient();
    render(<ApprovalScreen initialWorkflowId="unknown-404-id" client={client} />);

    await waitFor(() => {
      expect(screen.getByTestId("approval-screen-error")).toBeInTheDocument();
    });
    expect(screen.getByText("Workflow Not Found")).toBeInTheDocument();
  });
});
