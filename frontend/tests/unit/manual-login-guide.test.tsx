import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ManualLoginGuide } from "@/components/session";
import { MockApiClient } from "@/lib/api";

describe("ManualLoginGuide", () => {
  it("renders the zero-password model explainer text", async () => {
    const client = new MockApiClient();
    render(<ManualLoginGuide client={client} />);

    await waitFor(() => {
      expect(screen.getByTestId("manual-login-explainer")).toBeInTheDocument();
    });

    expect(screen.getByTestId("manual-login-explainer")).toHaveTextContent(
      "You will log in directly in a separate browser window. Krama only saves an encrypted session cookie, never your password.",
    );
  });

  it("shows active badge immediately if session is already saved", async () => {
    const client = new MockApiClient();
    client.setMockSessionStatus("github", { active: true });
    const onActive = vi.fn();

    render(<ManualLoginGuide client={client} target="github" onSessionActive={onActive} />);

    await waitFor(() => {
      expect(screen.getByTestId("manual-login-active-badge")).toBeInTheDocument();
    });

    expect(screen.getByTestId("manual-login-active-badge")).toHaveTextContent(
      "Session Active (Encrypted Storage State Saved)",
    );
    expect(onActive).toHaveBeenCalled();
  });

  it("launches manual login and transitions into polling waiting state, then active badge", async () => {
    const client = new MockApiClient();
    // Do not auto-activate immediately so we can observe the pending state
    client.mockAutoActivateSession = false;
    const launchSpy = vi.spyOn(client, "launchManualLogin");
    const getStatusSpy = vi.spyOn(client, "getSessionStatus");
    const onActive = vi.fn();

    render(
      <ManualLoginGuide
        client={client}
        target="github"
        pollIntervalMs={10}
        onSessionActive={onActive}
      />,
    );

    // Initial state: idle with Launch button
    await waitFor(() => {
      expect(screen.getByTestId("launch-manual-login-btn")).toBeInTheDocument();
    });

    // Click Launch Manual Login
    fireEvent.click(screen.getByTestId("launch-manual-login-btn"));

    // Verify backend call initiated
    await waitFor(() => {
      expect(launchSpy).toHaveBeenCalledWith("github");
    });

    // Verify waiting/pending UI state
    await waitFor(() => {
      expect(screen.getByTestId("manual-login-pending")).toBeInTheDocument();
    });
    expect(screen.getByTestId("manual-login-pending")).toHaveTextContent(
      "Waiting for you to complete sign-in in the open browser...",
    );

    // Now simulate user finishing login in the browser
    client.setMockSessionStatus("github", { active: true });

    // Verify transition to active state badge
    await waitFor(() => {
      expect(screen.getByTestId("manual-login-active-badge")).toBeInTheDocument();
    });
    expect(screen.getByTestId("manual-login-active-badge")).toHaveTextContent(
      "Session Active (Encrypted Storage State Saved)",
    );
    expect(onActive).toHaveBeenCalled();
    expect(getStatusSpy).toHaveBeenCalled();
  });

  it("displays error banner and retry button on launch failure, and retries successfully", async () => {
    const client = new MockApiClient();
    let attempt = 0;
    client.launchManualLogin = vi.fn(async () => {
      attempt++;
      if (attempt === 1) {
        throw new Error("Browser window failed to open");
      }
      return { target: "github", status: "launched" as const };
    });

    render(<ManualLoginGuide client={client} target="github" pollIntervalMs={10} />);

    await waitFor(() => {
      expect(screen.getByTestId("launch-manual-login-btn")).toBeInTheDocument();
    });

    // First attempt fails
    fireEvent.click(screen.getByTestId("launch-manual-login-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("manual-login-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("manual-login-error")).toHaveTextContent(
      "Browser window failed to open",
    );
    expect(screen.getByTestId("retry-manual-login-btn")).toBeInTheDocument();

    // Second attempt via retry button succeeds
    fireEvent.click(screen.getByTestId("retry-manual-login-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("manual-login-pending")).toBeInTheDocument();
    });
  });

  it("transitions to error when polling times out", async () => {
    const client = new MockApiClient();
    client.mockAutoActivateSession = false;

    render(
      <ManualLoginGuide
        client={client}
        target="github"
        pollIntervalMs={10}
        timeoutMs={25}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("launch-manual-login-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("launch-manual-login-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("manual-login-error")).toBeInTheDocument();
    }, { timeout: 2000 });

    expect(screen.getByTestId("manual-login-error")).toHaveTextContent(
      "Login timed out or browser was closed before completing sign-in.",
    );
    expect(screen.getByTestId("retry-manual-login-btn")).toBeInTheDocument();
  });
});
