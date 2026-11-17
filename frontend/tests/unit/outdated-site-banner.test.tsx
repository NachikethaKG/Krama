import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OutdatedSiteBanner } from "@/components/share/OutdatedSiteBanner";

describe("OutdatedSiteBanner Component Suite", () => {
  it("renders with alert role, Site Changed title, and default warning copy", () => {
    render(<OutdatedSiteBanner />);

    const banner = screen.getByRole("alert");
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveAttribute("data-testid", "outdated-site-banner");
    expect(screen.getByText("Site Changed")).toBeInTheDocument();
    expect(
      screen.getByText(/The target website has changed since this tutorial was recorded/i)
    ).toBeInTheDocument();
  });

  it("renders custom message when provided", () => {
    render(
      <OutdatedSiteBanner message="Button layout has moved. Please follow updated instructions." />
    );

    expect(
      screen.getByText("Button layout has moved. Please follow updated instructions.")
    ).toBeInTheDocument();
  });
});
