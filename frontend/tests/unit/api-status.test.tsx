import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiStatus, ApiStatusBadge } from "@/components/api-status";
import { MockApiClient } from "@/lib/api";

describe("ApiStatus", () => {
  it("renders discreet operational badge when the API is healthy without raw dev text", async () => {
    class HealthyClient extends MockApiClient {
      override async health() {
        return { status: "ok" as const, version: "1.2.3" };
      }
    }

    render(<ApiStatus client={new HealthyClient()} />);

    // Discreet status indicator is present
    expect(await screen.findByText("Systems Operational")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "System Status");

    // Raw dev text is completely removed
    expect(screen.queryByText(/API ok/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/version 1\.2\.3/i)).not.toBeInTheDocument();
  });

  it("shows an unobtrusive offline banner and degraded badge when the API is unreachable", async () => {
    class FailingClient extends MockApiClient {
      override async health(): Promise<never> {
        throw new Error("connection refused");
      }
    }

    render(<ApiStatus client={new FailingClient()} />);

    // Shows subtle offline alert banner without crashing
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByText(/Backend service offline\. Cached workflows and mock mode remain available\./i),
    ).toBeInTheDocument();

    // Degraded status badge
    expect(screen.getByText("API Offline")).toBeInTheDocument();

    // No raw error tracebacks or old dev strings
    expect(screen.queryByText(/API unreachable: connection refused/i)).not.toBeInTheDocument();
  });

  it("renders ApiStatusBadge in all states with appropriate aria labels and dots", () => {
    const { rerender } = render(<ApiStatusBadge status="online" />);
    expect(screen.getByText("Systems Operational")).toBeInTheDocument();

    rerender(<ApiStatusBadge status="checking" />);
    expect(screen.getByText("Connecting...")).toBeInTheDocument();

    rerender(<ApiStatusBadge status="offline" />);
    expect(screen.getByText("API Offline")).toBeInTheDocument();
  });
});
