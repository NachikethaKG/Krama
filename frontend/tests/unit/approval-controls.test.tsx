import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApprovalControls } from "@/components/approval-controls";

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

  it("links the success banner to the live view of the RUN, not the plan", () => {
    render(<ApprovalControls status="approved" runId="run-123" />);
    expect(screen.getByTestId("live-execution-link")).toHaveAttribute("href", "/runs/run-123/live");
  });

  it("disables Approve while the plan is being edited", () => {
    const onApprove = vi.fn();
    render(<ApprovalControls status="proposed" isEditing onToggleEdit={vi.fn()} onApprove={onApprove} />);
    const approve = screen.getByTestId("approve-btn");
    expect(approve).toBeDisabled();
    fireEvent.click(approve);
    expect(onApprove).not.toHaveBeenCalled();
  });
});
