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
  const allowBtnRef = useRef<HTMLButtonElement>(null);

  // Focus Allow button when modal opens
  useEffect(() => {
    if (isOpen) {
      const timer = setTimeout(() => {
        allowBtnRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Handle escape key to safely deny/dismiss
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !isConfirming) {
        e.preventDefault();
        onDeny();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isConfirming, onDeny]);

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
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-zinc-950/60 backdrop-blur-xs pointer-events-none transition-opacity animate-in fade-in duration-200"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="policy-modal-title"
        aria-describedby="policy-modal-desc"
        data-testid="policy-confirmation-modal"
        className={`pointer-events-auto relative w-full max-w-lg rounded-2xl border border-amber-300/80 bg-white p-6 shadow-2xl transition-all sm:p-7 dark:border-amber-700/80 dark:bg-zinc-900 ${className}`}
      >
        {/* Header Icon & Title */}
        <div className="flex items-start gap-4">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-xl border border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-700 dark:bg-amber-950/70 dark:text-amber-300">
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
                className="text-lg font-bold tracking-tight text-zinc-900 dark:text-zinc-50"
              >
                Policy Confirmation Required
              </h2>
            </div>
            <p
              id="policy-modal-desc"
              className="mt-1 text-xs text-zinc-600 dark:text-zinc-400"
            >
              Execution paused at <span className="font-semibold text-zinc-900 dark:text-zinc-200">Step {stepSeq}</span> awaiting explicit human authorization.
            </p>
          </div>
        </div>

        {/* Step Details & Risk Card */}
        <div className="mt-5 rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-950/60">
          <div className="flex items-center justify-between gap-3 border-b border-zinc-200/80 pb-3 dark:border-zinc-800/80">
            <div className="flex items-center gap-2">
              <span className="flex size-6 items-center justify-center rounded-full bg-indigo-100 font-mono text-xs font-bold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                {stepSeq}
              </span>
              <span className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                Target Step
              </span>
            </div>

            <RiskBadge level={effectiveRisk} size="md" />
          </div>

          <div className="mt-3">
            <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 leading-snug">
              {stepInstruction}
            </p>

            {(actionType || targetRole || targetName) && (
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5 font-mono text-[11px] text-zinc-600 dark:text-zinc-400">
                {actionType && (
                  <span className="rounded bg-zinc-200/80 px-1.5 py-0.5 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300">
                    action: {actionType}
                  </span>
                )}
                {targetRole && (
                  <span className="rounded bg-zinc-200/80 px-1.5 py-0.5 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300">
                    role: {targetRole}
                  </span>
                )}
                {targetName && (
                  <span className="rounded bg-zinc-200/80 px-1.5 py-0.5 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300">
                    target: &ldquo;{targetName}&rdquo;
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Explicit Policy Rationale & Safety Flag Callout */}
        <div className="mt-4 rounded-xl border border-amber-200/80 bg-amber-50/80 p-3.5 dark:border-amber-900/60 dark:bg-amber-950/30">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-amber-950 dark:text-amber-200">
              Safety Policy Flag
            </span>
            <span
              data-testid="policy-flag-badge"
              className="rounded-md border border-amber-300 bg-amber-200/60 px-2 py-0.5 font-mono text-[10px] font-bold tracking-wide text-amber-900 dark:border-amber-700 dark:bg-amber-900/60 dark:text-amber-200"
            >
              {formattedReason}
            </span>
          </div>
          <p className="mt-1 text-xs text-amber-900/90 leading-relaxed dark:text-amber-300/90">
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
            className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-4 py-2.5 text-xs font-semibold text-zinc-700 shadow-xs transition hover:bg-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-rose-500/50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
          >
            <svg
              aria-hidden="true"
              className="size-3.5 text-rose-500"
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
            ref={allowBtnRef}
            type="button"
            data-testid="modal-allow-btn"
            disabled={isConfirming}
            onClick={onAllow}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-xs font-semibold text-white shadow-xs transition hover:bg-emerald-500 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/50 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-emerald-600 dark:hover:bg-emerald-500"
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
