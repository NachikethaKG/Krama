import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TutorialStatusBadge } from "@/components/tutorials/TutorialStatusBadge";

describe("TutorialStatusBadge Component Suite", () => {
  it("renders verified status badge with emerald pulse and accessible label", () => {
    render(<TutorialStatusBadge status="verified" />);

    const badge = screen.getByTestId("tutorial-status-badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("Verified");
    expect(badge).toHaveAttribute("data-status", "verified");
    expect(badge).toHaveAttribute("aria-label", "Freshness status: Verified");
    expect(badge).toHaveClass("text-emerald-700");
  });

  it("renders auto-updated badge with sync icon, text, and inspect diff trigger", () => {
    const onInspect = vi.fn();
    render(<TutorialStatusBadge status="auto-updated" onInspectDiff={onInspect} />);

    const badge = screen.getByTestId("tutorial-status-badge");
    expect(badge).toHaveTextContent("Auto-Updated");
    expect(badge).toHaveAttribute("data-status", "auto-updated");
    expect(badge).toHaveClass("text-sky-700");

    const diffBtn = screen.getByTestId("inspect-diff-button");
    expect(diffBtn).toBeInTheDocument();
    expect(diffBtn).toHaveTextContent("Diff");

    fireEvent.click(diffBtn);
    expect(onInspect).toHaveBeenCalledTimes(1);
  });

  it("renders auto-updated badge with diff link when diffHref is provided", () => {
    render(<TutorialStatusBadge status="auto-updated" diffHref="/tutorials/xyz?view=diff" />);

    const diffLink = screen.getByTestId("inspect-diff-button");
    expect(diffLink).toHaveAttribute("href", "/tutorials/xyz?view=diff");
  });

  it("renders outdated status badge with amber indicator", () => {
    render(<TutorialStatusBadge status="outdated" />);

    const badge = screen.getByTestId("tutorial-status-badge");
    expect(badge).toHaveTextContent("Outdated");
    expect(badge).toHaveAttribute("data-status", "outdated");
    expect(badge).toHaveClass("text-amber-700");
  });

  it("renders not_auto_checked status badge with neutral indicator", () => {
    render(<TutorialStatusBadge status="not_auto_checked" />);

    const badge = screen.getByTestId("tutorial-status-badge");
    expect(badge).toHaveTextContent("Not Auto-Checked");
    expect(badge).toHaveAttribute("data-status", "not_auto_checked");
    expect(badge).toHaveClass("text-zinc-700");
  });

  it("supports custom data-testid and sm size class", () => {
    render(
      <TutorialStatusBadge
        status="verified"
        data-testid="custom-status-badge"
        size="sm"
      />
    );

    const badge = screen.getByTestId("custom-status-badge");
    expect(badge).toHaveClass("text-[11px]");
  });
});
