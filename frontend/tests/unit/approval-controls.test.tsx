import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  ApprovalControls,
  mockApproveWorkflow,
  mockRejectWorkflow,
} from "@/components/approval-controls";
import { MockApiClient } from "@/lib/api";

describe("ApprovalControls", () => {
  it("renders Approve, Reject, and Edit buttons", () => {
    const handleToggleEdit = vi.fn();
    render(
      <ApprovalControls
        onToggleEdit={handleToggleEdit}
        status="draft"
      />
    );

    expect(screen.getByTestId("approval-controls")).toBeInTheDocument();
    expect(screen.getByTestId("approve-btn")).toHaveTextContent("Approve & Execute");
    expect(screen.getByTestId("reject-btn")).toHaveTextContent("Reject Plan");
    expect(screen.getByTestId("edit-btn")).toHaveTextContent("Edit Plan");
  });

  it("calls onApprove when Approve button is clicked", async () => {
    const handleApprove = vi.fn().mockResolvedValue(undefined);
    render(<ApprovalControls onApprove={handleApprove} />);

    fireEvent.click(screen.getByTestId("approve-btn"));
    expect(handleApprove).toHaveBeenCalledTimes(1);
  });

  it("calls onReject when Reject button is clicked", async () => {
    const handleReject = vi.fn().mockResolvedValue(undefined);
    render(<ApprovalControls onReject={handleReject} />);

    fireEvent.click(screen.getByTestId("reject-btn"));
    expect(handleReject).toHaveBeenCalledTimes(1);
  });

  it("disables buttons when isPending is true", () => {
    render(<ApprovalControls isPending={true} onToggleEdit={vi.fn()} />);

    expect(screen.getByTestId("approve-btn")).toBeDisabled();
    expect(screen.getByTestId("reject-btn")).toBeDisabled();
    expect(screen.getByTestId("edit-btn")).toBeDisabled();
    expect(screen.getByTestId("approve-btn")).toHaveTextContent("Processing…");
  });

  it("displays error banner when error prop is provided", () => {
    render(<ApprovalControls error="API request failed unexpectedly" />);

    const banner = screen.getByTestId("approval-error-banner");
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent("API request failed unexpectedly");
  });

  it("displays success banner when status is approved", () => {
    render(<ApprovalControls status="approved" />);

    expect(screen.getByTestId("approval-success-banner")).toBeInTheDocument();
    expect(screen.getByTestId("approve-btn")).toBeDisabled();
    expect(screen.getByTestId("reject-btn")).toBeDisabled();
  });

  it("displays rejected banner when status is rejected", () => {
    render(<ApprovalControls status="rejected" />);

    expect(screen.getByTestId("approval-rejected-banner")).toBeInTheDocument();
    expect(screen.getByTestId("approve-btn")).toBeDisabled();
    expect(screen.getByTestId("reject-btn")).toBeDisabled();
  });

  describe("mockApproveWorkflow and mockRejectWorkflow helpers", () => {
    it("approves existing workflow successfully", async () => {
      const client = new MockApiClient();
      const res = await mockApproveWorkflow(client, "default");
      expect(res.status).toBe("approved");
      expect(res.workflowId).toBe("default");
    });

    it("rejects existing workflow successfully", async () => {
      const client = new MockApiClient();
      const res = await mockRejectWorkflow(client, "default", "User declined");
      expect(res.status).toBe("rejected");
      expect(res.workflowId).toBe("default");
    });

    it("throws error when approving non-existent workflow", async () => {
      const client = new MockApiClient();
      await expect(mockApproveWorkflow(client, "non-existent-wf")).rejects.toThrow(
        "Workflow not found"
      );
    });
  });
});
