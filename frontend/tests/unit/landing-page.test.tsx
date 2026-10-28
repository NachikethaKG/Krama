import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LandingPage } from "@/components/landing-page";
import { MockApiClient } from "@/lib/api";

describe("Landing page", () => {
  it("invites signed-out visitors to sign in and explains how it works", () => {
    render(<LandingPage client={new MockApiClient()} />);

    expect(
      screen.getByRole("heading", { level: 1, name: /Interactive Tutorials Recorded From Real UI Actions/i }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("landing-primary-cta")).toHaveAttribute("href", "/login");
    expect(screen.getByRole("heading", { name: "How it works" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
    // No testing targets or internal labels for visitors
    expect(screen.queryByText(/Gitea|Phase 3|Quick Workflow Generator/)).not.toBeInTheDocument();
  });

  it("sends signed-in users into the app", () => {
    render(<LandingPage signedIn client={new MockApiClient()} />);
    expect(screen.getByTestId("landing-primary-cta")).toHaveAttribute("href", "/");
    expect(screen.getByTestId("landing-primary-cta")).toHaveTextContent("Open Krama");
  });
});
