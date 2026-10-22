import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Page from "@/app/page";
import { HomePage, LandingPage } from "@/components/landing-page";
import { MockApiClient } from "@/lib/api";

class HealthyClient extends MockApiClient {
  override async health() {
    return { status: "ok" as const, version: "0.1.0" };
  }
}

class FailingClient extends MockApiClient {
  override async health(): Promise<never> {
    throw new Error("Failed to fetch health check from http://localhost:8000/api/v1/health: Connection Refused");
  }
}

describe("LandingPage", () => {
  it("renders product headlines and navigation without raw dev health check text", async () => {
    render(<LandingPage client={new HealthyClient()} />);

    // 1. Raw development health check string must be completely removed
    expect(screen.queryByText(/API ok/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/version 0\.1\.0/i)).not.toBeInTheDocument();

    // 2. Product headlines and description are present
    expect(
      screen.getByRole("heading", {
        name: /Interactive Tutorials Recorded From Real UI Actions/i,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByText((content) =>
        content.includes("Krama plans, executes, and verifies workflows headlessly"),
      ),
    ).toBeInTheDocument();

    // 3. Primary action CTAs and navigation buttons are visible
    const dashboardCta = screen.getByRole("link", { name: /^Go to Dashboard$/i });
    expect(dashboardCta).toBeInTheDocument();
    expect(dashboardCta).toHaveAttribute("href", "/dashboard");

    const tutorialsCta = screen.getByRole("link", { name: /^Explore Tutorials$/i });
    expect(tutorialsCta).toBeInTheDocument();
    expect(tutorialsCta).toHaveAttribute("href", "/tutorials");

    const createWorkflowLinks = screen.getAllByRole("link", { name: /Create Workflow/i });
    expect(createWorkflowLinks.length).toBeGreaterThanOrEqual(1);
    expect(createWorkflowLinks.some((l) => l.getAttribute("href") === "/runs/new")).toBe(true);

    // 4. Discreet status indicator in footer
    expect(await screen.findByText("Systems Operational")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveAttribute("aria-label", "System Status");
  });

  it("handles offline or erroring backend API gracefully without crashing or showing raw tracebacks", async () => {
    render(<HomePage client={new FailingClient()} />);

    // 1. Page layout remains intact
    expect(
      screen.getByRole("heading", {
        name: /Interactive Tutorials Recorded From Real UI Actions/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Go to Dashboard$/i })).toBeInTheDocument();

    // 2. Subtle offline alert banner appears
    const alert = await screen.findByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(
      screen.getByText(/Backend service offline\. Cached workflows and mock mode remain available\./i),
    ).toBeInTheDocument();

    // 3. Status indicator shows degraded state
    expect(screen.getByText("API Offline")).toBeInTheDocument();

    // 4. Never displays raw exception tracebacks or connection refused strings
    expect(screen.queryByText(/Connection Refused/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Failed to fetch health check/i)).not.toBeInTheDocument();
  });

  it("renders page default export without errors", () => {
    render(<Page />);
    expect(
      screen.getByRole("heading", {
        name: /Interactive Tutorials Recorded From Real UI Actions/i,
      }),
    ).toBeInTheDocument();
  });
});
