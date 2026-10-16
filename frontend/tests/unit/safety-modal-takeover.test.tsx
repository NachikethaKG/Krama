import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  AutomationRestrictedScreen,
  PolicyConfirmationModal,
} from "@/components/safety";
import { MockApiClient } from "@/lib/api";

describe("PolicyConfirmationModal Component", () => {
  it("does not render into the DOM when isOpen is false", () => {
    const onAllow = vi.fn();
    const onDeny = vi.fn();

    render(
      <PolicyConfirmationModal
        isOpen={false}
        stepSeq={2}
        stepInstruction="Delete repository demo-repo permanently"
        onAllow={onAllow}
        onDeny={onDeny}
      />
    );

    expect(screen.queryByTestId("policy-confirmation-modal")).toBeNull();
  });

  it("renders accessible modal with step details, high risk badge, and explicit rationale", () => {
    const onAllow = vi.fn();
    const onDeny = vi.fn();

    render(
      <PolicyConfirmationModal
        isOpen={true}
        stepSeq={2}
        stepInstruction="Delete repository demo-repo permanently"
        actionType="click"
        targetRole="button"
        targetName="Delete Repository"
        risk="high"
        reason="destructive_action"
        rationale="Destructive action requires confirmation before proceeding"
        onAllow={onAllow}
        onDeny={onDeny}
      />
    );

    // Accessible dialog semantics
    const modal = screen.getByTestId("policy-confirmation-modal");
    expect(modal).toBeInTheDocument();
    expect(modal).toHaveAttribute("role", "dialog");
    expect(modal).toHaveAttribute("aria-modal", "true");

    // Title & step content
    expect(screen.getByText(/Policy Confirmation Required/i)).toBeInTheDocument();
    expect(screen.getByText(/Step 2/i)).toBeInTheDocument();
    expect(screen.getByText("Delete repository demo-repo permanently")).toBeInTheDocument();
    expect(screen.getByText(/action: click/i)).toBeInTheDocument();
    expect(screen.getByText(/target: “Delete Repository”/i)).toBeInTheDocument();

    // Risk badge
    const riskBadge = screen.getByTestId("risk-badge");
    expect(riskBadge).toHaveAttribute("data-risk-level", "high");
    expect(riskBadge).toHaveTextContent("High Risk");

    // Explicit rationale callout
    expect(
      screen.getByText("Destructive action requires confirmation before proceeding")
    ).toBeInTheDocument();
    expect(screen.getByText("DESTRUCTIVE ACTION")).toBeInTheDocument();

    // Controls
    expect(screen.getByTestId("modal-allow-btn")).toBeInTheDocument();
    expect(screen.getByTestId("modal-deny-btn")).toBeInTheDocument();
  });

  it("renders medium risk badge when risk level is medium", () => {
    render(
      <PolicyConfirmationModal
        isOpen={true}
        stepSeq={3}
        stepInstruction="Modify user security permissions"
        risk="medium"
        reason="sensitive_data"
        onAllow={vi.fn()}
        onDeny={vi.fn()}
      />
    );

    const riskBadge = screen.getByTestId("risk-badge");
    expect(riskBadge).toHaveAttribute("data-risk-level", "medium");
    expect(riskBadge).toHaveTextContent("Medium Risk");
  });

  it("dispatches onAllow callback when Allow button is clicked", () => {
    const onAllow = vi.fn();
    const onDeny = vi.fn();

    render(
      <PolicyConfirmationModal
        isOpen={true}
        stepSeq={2}
        onAllow={onAllow}
        onDeny={onDeny}
      />
    );

    const allowBtn = screen.getByTestId("modal-allow-btn");
    fireEvent.click(allowBtn);

    expect(onAllow).toHaveBeenCalledTimes(1);
    expect(onDeny).not.toHaveBeenCalled();
  });

  it("dispatches onDeny callback when Deny button is clicked", () => {
    const onAllow = vi.fn();
    const onDeny = vi.fn();

    render(
      <PolicyConfirmationModal
        isOpen={true}
        stepSeq={2}
        onAllow={onAllow}
        onDeny={onDeny}
      />
    );

    const denyBtn = screen.getByTestId("modal-deny-btn");
    fireEvent.click(denyBtn);

    expect(onDeny).toHaveBeenCalledTimes(1);
    expect(onAllow).not.toHaveBeenCalled();
  });

  it("dispatches onDeny callback when Escape key is pressed", () => {
    const onAllow = vi.fn();
    const onDeny = vi.fn();

    render(
      <PolicyConfirmationModal
        isOpen={true}
        stepSeq={2}
        onAllow={onAllow}
        onDeny={onDeny}
      />
    );

    fireEvent.keyDown(window, { key: "Escape" });
    expect(onDeny).toHaveBeenCalledTimes(1);
  });

  it("disables Allow and Deny buttons when isConfirming is true", () => {
    render(
      <PolicyConfirmationModal
        isOpen={true}
        stepSeq={2}
        isConfirming={true}
        onAllow={vi.fn()}
        onDeny={vi.fn()}
      />
    );

    expect(screen.getByTestId("modal-allow-btn")).toBeDisabled();
    expect(screen.getByTestId("modal-deny-btn")).toBeDisabled();
  });
});

describe("AutomationRestrictedScreen Component", () => {
  it("renders container with barrier explanation, target URL, and takeover instructions", () => {
    const onResume = vi.fn();
    const onAbort = vi.fn();

    render(
      <AutomationRestrictedScreen
        barrierType="cloudflare_turnstile"
        message="Cloudflare Turnstile challenge detected on target page"
        targetUrl="http://localhost:3001/login"
        stepSeq={2}
        onResume={onResume}
        onAbort={onAbort}
      />
    );

    const container = screen.getByTestId("automation-restricted-screen");
    expect(container).toBeInTheDocument();

    // Title & badge
    expect(
      screen.getByText(/Automation restricted → Take over manually/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Cloudflare Turnstile")).toBeInTheDocument();
    expect(
      screen.getByText(/Cloudflare Turnstile challenge detected on target page/i)
    ).toBeInTheDocument();

    // Target URL link
    const targetLink = screen.getByTestId("open-target-url-btn");
    expect(targetLink).toHaveAttribute("href", "http://localhost:3001/login");
    expect(targetLink).toHaveAttribute("target", "_blank");

    // Action controls
    expect(screen.getByTestId("takeover-resume-btn")).toBeInTheDocument();
    expect(screen.getByTestId("takeover-abort-btn")).toBeInTheDocument();
  });

  it("adapts explanation for Google reCAPTCHA barrier type", () => {
    render(
      <AutomationRestrictedScreen
        barrierType="recaptcha"
        targetUrl="http://localhost:3001/register"
      />
    );

    expect(screen.getByText("Google reCAPTCHA")).toBeInTheDocument();
    expect(
      screen.getByText(/Google reCAPTCHA challenge was detected/i)
    ).toBeInTheDocument();
  });

  it("adapts explanation for auth wall / login gate barrier type", () => {
    render(
      <AutomationRestrictedScreen
        barrierType="auth_wall"
        targetUrl="http://localhost:3001/admin"
      />
    );

    expect(screen.getByText("Login Barrier")).toBeInTheDocument();
    expect(
      screen.getByText(/login screen or authentication gate was reached/i)
    ).toBeInTheDocument();
  });

  it("dispatches onResume callback when Resume Execution is clicked", () => {
    const onResume = vi.fn();
    const onAbort = vi.fn();

    render(
      <AutomationRestrictedScreen
        barrierType="cloudflare_turnstile"
        onResume={onResume}
        onAbort={onAbort}
      />
    );

    fireEvent.click(screen.getByTestId("takeover-resume-btn"));
    expect(onResume).toHaveBeenCalledTimes(1);
    expect(onAbort).not.toHaveBeenCalled();
  });

  it("dispatches onAbort callback when Abort Run is clicked", () => {
    const onResume = vi.fn();
    const onAbort = vi.fn();

    render(
      <AutomationRestrictedScreen
        barrierType="cloudflare_turnstile"
        onResume={onResume}
        onAbort={onAbort}
      />
    );

    fireEvent.click(screen.getByTestId("takeover-abort-btn"));
    expect(onAbort).toHaveBeenCalledTimes(1);
    expect(onResume).not.toHaveBeenCalled();
  });
});

describe("ApiClient confirmRunAction extension", () => {
  it("resolves confirmRunAction allow and deny on MockApiClient", async () => {
    const client = new MockApiClient();

    await expect(client.confirmRunAction("mock-run-id", "allow")).resolves.toBeUndefined();
    await expect(client.confirmRunAction("mock-run-id", "deny", 2)).resolves.toBeUndefined();
  });
});
