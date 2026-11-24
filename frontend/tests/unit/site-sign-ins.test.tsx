import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn(), back: vi.fn() }),
  usePathname: () => "/sites",
  useSearchParams: () => new URLSearchParams(),
}));

import { SiteSignIns, siteLabel } from "@/components/sites/SiteSignIns";
import { MockApiClient } from "@/lib/api";

describe("SiteSignIns (ADR 0012, #479)", () => {
  it("lists the sites Krama is signed in to and forgets one", async () => {
    const client = new MockApiClient();
    vi.spyOn(client, "listSiteProfiles").mockResolvedValue({
      items: [
        { site: "github", account: "octo-demo", captured_at: "2026-11-24T10:00:00Z", sign_in_hosts: [] },
        {
          site: "https://www.openstreetmap.org",
          account: "your account on www.openstreetmap.org",
          captured_at: "2026-11-24T10:00:00Z",
          sign_in_hosts: ["accounts.example"],
        },
      ],
    });
    const forget = vi.spyOn(client, "forgetSiteProfile").mockResolvedValue();
    render(<SiteSignIns client={client} />);

    await waitFor(() => expect(screen.getAllByTestId("site-profile")).toHaveLength(2));
    expect(screen.getByText("www.openstreetmap.org")).toBeInTheDocument();

    fireEvent.click(screen.getAllByTestId("forget-site")[1]);
    await waitFor(() => expect(screen.getAllByTestId("site-profile")).toHaveLength(1));
    expect(forget).toHaveBeenCalledWith("https://www.openstreetmap.org");
  });

  it("signs in only after the owner confirms the site's terms, then opens the live view", async () => {
    push.mockClear();
    const client = new MockApiClient();
    const start = vi.spyOn(client, "startSignInAt");
    render(<SiteSignIns client={client} initialUrl="https://example.com/login" />);

    const button = screen.getByTestId("sign-in-btn");
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByTestId("sign-in-terms"));
    expect(button).toBeEnabled();
    fireEvent.click(button);

    await waitFor(() => expect(push).toHaveBeenCalled());
    expect(start).toHaveBeenCalledWith("https://example.com/login");
    expect(push.mock.calls[0][0]).toMatch(/^\/runs\/.+\/live\?back=%2Fsites$/);
  });

  it("says why a sensitive site is refused", async () => {
    render(<SiteSignIns client={new MockApiClient()} initialUrl="https://www.paypal.com/signin" />);

    fireEvent.click(screen.getByTestId("sign-in-terms"));
    fireEvent.click(screen.getByTestId("sign-in-btn"));

    await waitFor(() => expect(screen.getByTestId("sign-in-error")).toHaveTextContent(/banking, payment/i));
  });

  it("shows an origin by its host", () => {
    expect(siteLabel("https://docs.python.org")).toBe("docs.python.org");
    expect(siteLabel("github")).toBe("github");
  });
});
