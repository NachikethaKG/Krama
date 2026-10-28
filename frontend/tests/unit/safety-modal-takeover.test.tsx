import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  AutomationRestrictedScreen,
  PolicyConfirmationModal,
} from "@/components/safety";

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
    expect(riskBadge).toHaveTextContent("Changes or deletes");

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
    expect(riskBadge).toHaveTextContent("Creates something");
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

  it("does NOT deny when Escape is pressed (a stray key must not send a decision)", () => {
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
    expect(onDeny).not.toHaveBeenCalled();
    expect(onAllow).not.toHaveBeenCalled();
    expect(screen.getByTestId("policy-confirmation-modal")).toBeInTheDocument();
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
    render(
      <AutomationRestrictedScreen
        barrierType="cloudflare_turnstile"
        message="Cloudflare Turnstile challenge detected on target page"
        targetUrl="http://localhost:3001/login"
        stepSeq={2}
        runHref="/runs/run-1"
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

    // The run already failed (policy stop): no Resume / Abort, only ways forward
    expect(screen.queryByTestId("takeover-resume-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("takeover-abort-btn")).not.toBeInTheDocument();
    expect(screen.getByTestId("takeover-new-task-link")).toHaveAttribute("href", "/");
    expect(screen.getByTestId("takeover-run-link")).toHaveAttribute("href", "/runs/run-1");
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

  it("hides the target card when no target URL is known", () => {
    render(<AutomationRestrictedScreen barrierType="captcha" />);
    expect(screen.queryByTestId("open-target-url-btn")).not.toBeInTheDocument();
  });
});
