"use client";

import { useState } from "react";
import Link from "next/link";
import type { FailedState, PausedState } from "@/hooks/useRunStream";

export interface RunStatusBannersProps {
  status: "idle" | "running" | "paused" | "failed" | "completed";
  pausedState?: PausedState | null;
  failedState?: FailedState | null;
  workflowId?: string | null;
  onResume?: () => Promise<void> | void;
  onAbort?: () => Promise<void> | void;
  className?: string;
}

export function RunStatusBanners({
  status,
  pausedState,
  failedState,
  workflowId,
  onResume,
  onAbort,
  className = "",
}: RunStatusBannersProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleResume = async () => {
    if (!onResume || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onResume();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAbort = async () => {
    if (!onAbort || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onAbort();
    } finally {
      setIsSubmitting(false);
    }
  };

  if (status === "paused") {
    return (
      <div
        role="alert"
        data-testid="paused-banner"
        className={`flex flex-col gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 shadow-sm dark:border-amber-900/60 dark:bg-amber-950/40 ${className}`}
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-800 dark:bg-amber-900/80 dark:text-amber-200">
            <svg
              className="size-5"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="2"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
              />
            </svg>
          </div>

          <div className="flex-1 space-y-1">
            <h3 className="text-sm font-bold text-amber-900 dark:text-amber-100">
              Execution Paused: Action requires manual approval / bot barrier detected
            </h3>
            <p className="text-xs text-amber-800 dark:text-amber-200 leading-relaxed">
              {pausedState?.message || "Execution paused for safety policy review."}
            </p>
            {pausedState?.triggerContext && (
              <p className="text-[11px] font-medium text-amber-700 dark:text-amber-300">
                Context: <span className="font-semibold">{pausedState.triggerContext}</span>
                {pausedState.stepSeq ? ` at Step ${pausedState.stepSeq}` : ""}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2.5 pt-1 border-t border-amber-200/60 dark:border-amber-900/40">
          <button
            type="button"
            data-testid="abort-run-button"
            disabled={isSubmitting}
            onClick={handleAbort}
            className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100/60 focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:opacity-50 dark:border-amber-800 dark:bg-zinc-900 dark:text-amber-200 dark:hover:bg-amber-950/60"
          >
            {isSubmitting ? "Processing…" : "Abort Run"}
          </button>

          <button
            type="button"
            data-testid="allow-resume-button"
            disabled={isSubmitting}
            onClick={handleResume}
            className="rounded-lg bg-amber-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:opacity-50 dark:bg-amber-500 dark:hover:bg-amber-400"
          >
            {isSubmitting ? "Resuming…" : "Allow & Resume"}
          </button>
        </div>
      </div>
    );
  }

  if (status === "failed") {
    const errorMsg = failedState?.error || "Workflow execution halted unexpectedly";
    const stepIndex = failedState?.stepSeq ?? "?";

    return (
      <div
        role="alert"
        data-testid="failed-banner"
        className={`flex flex-col gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 shadow-sm dark:border-rose-900/60 dark:bg-rose-950/40 ${className}`}
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-rose-100 text-rose-700 dark:bg-rose-900/80 dark:text-rose-200">
            <svg
              className="size-5"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="2"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
              />
            </svg>
          </div>

          <div className="flex-1 space-y-1">
            <h3 className="text-sm font-bold text-rose-900 dark:text-rose-100">
              Execution Failed at Step {stepIndex}: {errorMsg}
            </h3>
            <p className="text-xs text-rose-800 dark:text-rose-200">
              The agent stopped because the observed environment did not match expectations or encountered a policy restriction.
            </p>
          </div>
        </div>

        {/* Expected vs Observed Difference Card */}
        {(failedState?.expected || failedState?.observed) && (
          <div
            data-testid="expected-observed-card"
            className="rounded-xl border border-rose-200 bg-white p-3 dark:border-rose-900/80 dark:bg-zinc-900"
          >
            <h4 className="text-[11px] font-bold uppercase tracking-wider text-rose-900 dark:text-rose-200 mb-2">
              State Verification Mismatch
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
              <div className="rounded-lg bg-zinc-50 p-2.5 dark:bg-zinc-950">
                <span className="block text-[10px] uppercase font-bold text-zinc-500 dark:text-zinc-400 mb-1">
                  Expected
                </span>
                <pre className="whitespace-pre-wrap text-zinc-800 dark:text-zinc-200 text-[11px]">
                  {typeof failedState.expected === "object"
                    ? JSON.stringify(failedState.expected, null, 2)
                    : String(failedState.expected)}
                </pre>
              </div>

              <div className="rounded-lg bg-zinc-50 p-2.5 dark:bg-zinc-950">
                <span className="block text-[10px] uppercase font-bold text-zinc-500 dark:text-zinc-400 mb-1">
                  Observed
                </span>
                <pre className="whitespace-pre-wrap text-zinc-800 dark:text-zinc-200 text-[11px]">
                  {typeof failedState.observed === "object"
                    ? JSON.stringify(failedState.observed, null, 2)
                    : String(failedState.observed)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (status === "completed") {
    return (
      <div
        data-testid="completed-banner"
        className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 shadow-sm dark:border-emerald-900/60 dark:bg-emerald-950/40 ${className}`}
      >
        <div className="flex items-center gap-3">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700 dark:bg-emerald-900/80 dark:text-emerald-200">
            <svg
              className="size-5"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="2.5"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4.5 12.75l6 6 9-13.5"
              />
            </svg>
          </div>

          <div>
            <h3 className="text-sm font-bold text-emerald-900 dark:text-emerald-100">
              Workflow Execution Complete
            </h3>
            <p className="text-xs text-emerald-800 dark:text-emerald-200">
              All planned steps have been successfully executed and verified.
            </p>
          </div>
        </div>

        {workflowId && (
          <Link
            href={`/tutorials/${workflowId}`}
            data-testid="open-tutorial-btn"
            className="inline-flex items-center justify-center rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 dark:bg-emerald-500 dark:hover:bg-emerald-400"
          >
            Open Interactive Tutorial
          </Link>
        )}
      </div>
    );
  }

  return null;
}
