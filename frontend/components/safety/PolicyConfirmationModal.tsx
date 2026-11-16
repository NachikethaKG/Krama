"use client";

import React, { useEffect, useRef } from "react";
import type { Risk } from "@krama/contracts-ts";
import { RiskBadge } from "@/components/risk-badge";

export interface PolicyConfirmationModalProps {
  isOpen: boolean;
  stepSeq: number;
  stepInstruction?: string;
  actionType?: string;
  targetRole?: string | null;
  targetName?: string | null;
  risk?: Risk | string | null;
  reason?: string;
  rationale?: string;
  onAllow: () => void | Promise<void>;
  onDeny: () => void | Promise<void>;
  isConfirming?: boolean;
  className?: string;
}

export function PolicyConfirmationModal({
  isOpen,
  stepSeq,
  stepInstruction = "Execute proposed action",
  actionType,
  targetRole,
  targetName,
  risk = "high",
  reason = "destructive_action",
  rationale,
  onAllow,
  onDeny,
  isConfirming = false,
  className = "",
}: PolicyConfirmationModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Move focus into the dialog (not onto Allow: Enter must never approve a destructive step by accident).
  // Escape deliberately does nothing: the run stays paused until the user clicks Allow or Deny, and a stray
  // keypress must not send a decision to the backend.
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        dialogRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  // Format reason label
  const formattedReason = reason.replace(/_/g, " ").toUpperCase();
  const explicitRationale =
    rationale ||
    (reason === "destructive_action"
      ? "This action is flagged as destructive and may permanently modify or remove resources. Human approval is required to proceed."
      : reason === "sensitive_data"
        ? "This step involves sensitive data exposure or credentials entry and requires explicit confirmation."
        : reason === "prompt_injection"
          ? "Potential adversarial instructions were detected in the web page DOM. Automated execution is held for human confirmation."
          : "A safety policy rule requires manual verification before this step can execute.");

  const effectiveRisk = risk || "high";

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-950/75 backdrop-blur-md pointer-events-none transition-opacity animate-in fade-in duration-200"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="policy-modal-title"
        aria-describedby="policy-modal-desc"
        data-testid="policy-confirmation-modal"
        ref={dialogRef}
        tabIndex={-1}
        className={`kr-danger kr-tone-card kr-rise pointer-events-auto relative w-full max-w-lg overflow-hidden rounded-[2rem] bg-ink-900/95 p-6 pt-8 shadow-2xl backdrop-blur-2xl sm:p-8 sm:pt-9 ${className}`}
      >
        {/* hazard stripe */}
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-0 h-2"
          style={{ background: "repeating-linear-gradient(-45deg, var(--danger) 0 12px, var(--plan) 12px 24px)" }}
        />
        {/* Header Icon & Title */}
        <div className="flex items-start gap-4">
          <div className="kr-dot-live flex size-12 shrink-0 items-center justify-center rounded-2xl bg-danger text-oncolor">
            <svg
              aria-hidden="true"
              className="size-6"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
              />
            </svg>
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2
                id="policy-modal-title"
                className="kr-display text-2xl font-extrabold text-white"
              >
                Policy Confirmation Required
              </h2>
            </div>
            <p
              id="policy-modal-desc"
              className="mt-1 text-xs text-ink-300"
            >
              Execution paused at <span className="font-bold text-danger">Step {stepSeq}</span> awaiting explicit human authorization.
            </p>
          </div>
        </div>

        {/* Step Details & Risk Card */}
        <div className="mt-6 rounded-2xl border border-white/10 bg-ink-950/60 p-4">
          <div className="flex items-center justify-between gap-3 border-b border-white/10 pb-3">
            <div className="flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-full bg-danger font-mono text-xs font-extrabold text-oncolor">
                {stepSeq}
              </span>
              <span className="text-xs font-bold uppercase tracking-widest text-ink-400">
                Target Step
              </span>
            </div>

            <RiskBadge level={effectiveRisk} size="md" />
          </div>

          <div className="mt-3">
            <p className="text-base font-semibold leading-snug text-white">
              {stepInstruction}
            </p>

            {(actionType || targetRole || targetName) && (
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5 font-mono text-[11px] text-ink-300">
                {actionType && (
                  <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-ink-300">
                    action: {actionType}
                  </span>
                )}
                {targetRole && (
                  <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-ink-300">
                    role: {targetRole}
                  </span>
                )}
                {targetName && (
                  <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-ink-300">
                    target: &ldquo;{targetName}&rdquo;
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Explicit Policy Rationale & Safety Flag Callout */}
        <div className="kr-plan kr-tone-card mt-4 rounded-2xl p-3.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-plan">
              Safety Policy Flag
            </span>
            <span
              data-testid="policy-flag-badge"
              className="rounded-full bg-plan px-2.5 py-0.5 font-mono text-[10px] font-extrabold tracking-wide text-oncolor"
            >
              {formattedReason}
            </span>
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-ink-300">
            {explicitRationale}
          </p>
        </div>

        {/* Action Controls */}
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
          <button
            type="button"
            data-testid="modal-deny-btn"
            disabled={isConfirming}
            onClick={onDeny}
            className="kr-btn kr-btn-ghost kr-danger px-5 py-3 text-xs"
          >
            <svg
              aria-hidden="true"
              className="size-3.5 text-danger"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            Deny & Cancel Run
          </button>

          <button
            type="button"
            data-testid="modal-allow-btn"
            disabled={isConfirming}
            onClick={onAllow}
            className="kr-btn kr-btn-tone kr-danger px-6 py-3 text-xs"
          >
            <svg
              aria-hidden="true"
              className="size-3.5"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            {isConfirming ? "Allowing…" : "Allow & Proceed"}
          </button>
        </div>
      </div>
    </div>
  );
}
