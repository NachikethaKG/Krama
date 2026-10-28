import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RiskBadge } from "@/components/risk-badge";

describe("RiskBadge", () => {
  it("renders default low risk badge when no level is specified", () => {
    render(<RiskBadge />);
    const badge = screen.getByTestId("risk-badge");
    expect(badge).toHaveAttribute("data-risk-level", "low");
    expect(badge).toHaveTextContent("Safe");
    expect(badge).toHaveAttribute("aria-label", "Risk level: low");
  });

  it("renders medium risk badge with correct label and attributes", () => {
    render(<RiskBadge level="medium" />);
    const badge = screen.getByTestId("risk-badge");
    expect(badge).toHaveAttribute("data-risk-level", "medium");
    expect(badge).toHaveTextContent("Creates something");
    expect(badge).toHaveAttribute("aria-label", "Risk level: medium");
  });

  it("renders high risk badge with correct label and attributes", () => {
    render(<RiskBadge level="high" />);
    const badge = screen.getByTestId("risk-badge");
    expect(badge).toHaveAttribute("data-risk-level", "high");
    expect(badge).toHaveTextContent("Changes or deletes");
    expect(badge).toHaveAttribute("aria-label", "Risk level: high");
  });

  it("renders critical risk badge with correct label and attributes", () => {
    render(<RiskBadge level="critical" />);
    const badge = screen.getByTestId("risk-badge");
    expect(badge).toHaveAttribute("data-risk-level", "critical");
    expect(badge).toHaveTextContent("Dangerous");
    expect(badge).toHaveAttribute("aria-label", "Risk level: critical");
  });

  it("gracefully falls back to low risk config for unknown risk values", () => {
    render(<RiskBadge level="unknown-level" />);
    const badge = screen.getByTestId("risk-badge");
    expect(badge).toHaveTextContent("Safe");
  });
});
