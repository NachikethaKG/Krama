import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";

describe("RunStatusBadge", () => {
  it("renders verified status correctly", () => {
    render(<RunStatusBadge status="verified" />);
    const badge = screen.getByTestId("run-status-badge");
    expect(badge).toHaveAttribute("data-status", "verified");
    expect(badge).toHaveTextContent("Verified");
    expect(badge).toHaveAttribute("aria-label", "Run status: Verified");
  });

  it("renders failed status correctly", () => {
    render(<RunStatusBadge status="failed" />);
    const badge = screen.getByTestId("run-status-badge");
    expect(badge).toHaveAttribute("data-status", "failed");
    expect(badge).toHaveTextContent("Failed");
    expect(badge).toHaveAttribute("aria-label", "Run status: Failed");
  });

  it("renders paused status correctly", () => {
    render(<RunStatusBadge status="paused" />);
    const badge = screen.getByTestId("run-status-badge");
    expect(badge).toHaveAttribute("data-status", "paused");
    expect(badge).toHaveTextContent("Paused");
  });

  it("renders cancelled status correctly", () => {
    render(<RunStatusBadge status="cancelled" />);
    const badge = screen.getByTestId("run-status-badge");
    expect(badge).toHaveAttribute("data-status", "cancelled");
    expect(badge).toHaveTextContent("Cancelled");
  });

  it("renders running and queued statuses", () => {
    const { rerender } = render(<RunStatusBadge status="running" />);
    expect(screen.getByTestId("run-status-badge")).toHaveTextContent("Running");

    rerender(<RunStatusBadge status="queued" />);
    expect(screen.getByTestId("run-status-badge")).toHaveTextContent("Queued");
  });

  it("falls back gracefully for unknown status values", () => {
    // @ts-expect-error testing runtime fallback
    render(<RunStatusBadge status="some_unknown_status" />);
    const badge = screen.getByTestId("run-status-badge");
    expect(badge).toHaveTextContent("Some_unknown_status");
  });
});
