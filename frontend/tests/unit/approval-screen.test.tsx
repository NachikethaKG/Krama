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
    expect(editBtn).toHaveTextContent("Edit Plan");
    expect(screen.getByText("New edited instruction text")).toBeInTheDocument();
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
