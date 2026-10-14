import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  type ReplanStatus,
  ReplanStatusIndicator,
} from "@/components/execution/ReplanStatusIndicator";

describe("ReplanStatusIndicator", () => {
  it("returns null when status is idle", () => {
    const { container } = render(<ReplanStatusIndicator status="idle" />);
    expect(container.firstChild).toBeNull();
  });

  const statuses: ReplanStatus[] = [
    "re-locating",
    "retrying",
    "replanning",
    "exhausted",
    "succeeded",
  ];

  statuses.forEach((status) => {
    it(`renders badge and indicator properly for status "${status}"`, () => {
      render(
        <ReplanStatusIndicator
          status={status}
          attempt={2}
          maxAttempts={3}
          reason="Locating target DOM element"
        />
      );

      expect(screen.getByTestId("replan-status-indicator")).toBeInTheDocument();
      expect(screen.getByTestId(`replan-badge-${status}`)).toHaveTextContent(status);
      expect(screen.getByTestId("replan-attempt-counter")).toHaveTextContent("Attempt 2 of 3");
      expect(screen.getByTestId("replan-reason")).toHaveTextContent("Locating target DOM element");
    });
  });

  it("displays custom strategy and timeout seconds", () => {
    render(
      <ReplanStatusIndicator
        status="replanning"
        attempt={1}
        maxAttempts={3}
        strategy="Alternative role/aria heuristic matching"
        timeoutSeconds={25}
      />
    );

    expect(screen.getByTestId("replan-strategy")).toHaveTextContent(
      "Alternative role/aria heuristic matching"
    );
    expect(screen.getByTestId("replan-timeout")).toHaveTextContent("Timeout in 25s");
  });

  it("renders takeover and abort action buttons when status is exhausted and fires handlers", () => {
    const onTakeover = vi.fn();
    const onAbort = vi.fn();

    render(
      <ReplanStatusIndicator
        status="exhausted"
        attempt={3}
        maxAttempts={3}
        onTakeover={onTakeover}
        onAbort={onAbort}
      />
    );

    expect(screen.getByText("Automatic Recovery Exhausted")).toBeInTheDocument();

    const takeoverBtn = screen.getByTestId("replan-takeover-btn");
    const abortBtn = screen.getByTestId("replan-abort-btn");

    expect(takeoverBtn).toBeInTheDocument();
    expect(abortBtn).toBeInTheDocument();

    fireEvent.click(takeoverBtn);
    expect(onTakeover).toHaveBeenCalledTimes(1);

    fireEvent.click(abortBtn);
    expect(onAbort).toHaveBeenCalledTimes(1);
  });

  it("renders cancel replan button when actively replanning and fires onAbort", () => {
    const onAbort = vi.fn();

    render(
      <ReplanStatusIndicator
        status="retrying"
        attempt={1}
        maxAttempts={3}
        onAbort={onAbort}
      />
    );

    const cancelBtn = screen.getByTestId("replan-cancel-btn");
    expect(cancelBtn).toBeInTheDocument();
    fireEvent.click(cancelBtn);
    expect(onAbort).toHaveBeenCalledTimes(1);
  });
});
