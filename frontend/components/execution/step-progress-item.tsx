import type { VerificationMethod } from "@krama/contracts-ts";

import { RiskBadge } from "@/components/risk-badge";

export type StepExecutionStatus = "pending" | "started" | "verified" | "failed";

export interface StepProgressItemProps {
  seq: number;
  instructionText: string;
  actionType?: string;
  targetRole?: string | null;
  targetName?: string | null;
  risk?: string | null;
  status: StepExecutionStatus;
  methods?: (VerificationMethod | string)[];
  confidence?: number | null;
  error?: string | null;
  observedUrl?: string | null;
  observedTitle?: string | null;
  className?: string;
}

export function StepProgressItem({
  seq,
  instructionText,
  actionType = "action",
  targetRole,
  targetName,
  risk = "low",
  status = "pending",
  methods,
  confidence,
  error,
  observedUrl,
  observedTitle,
  className = "",
}: StepProgressItemProps) {
  const hasTarget = Boolean(targetRole || targetName);

  return (
    <li
      data-testid="step-progress-item"
      data-step-seq={seq}
      data-step-status={status}
      aria-live="polite"
      className={`group flex flex-col gap-3 rounded-xl border p-4 transition-all sm:flex-row sm:items-start sm:justify-between ${
        status === "started"
          ? "border-indigo-400 bg-indigo-50/30 shadow-xs dark:border-indigo-500/60 dark:bg-indigo-950/20"
          : status === "verified"
            ? "border-emerald-200 bg-emerald-50/15 dark:border-emerald-900/50 dark:bg-emerald-950/10"
            : status === "failed"
              ? "border-rose-300 bg-rose-50/30 shadow-xs dark:border-rose-900/60 dark:bg-rose-950/20"
              : "border-zinc-200 bg-white opacity-70 dark:border-zinc-800 dark:bg-zinc-900"
      } ${className}`}
    >
      <div className="flex flex-1 items-start gap-3.5">
        {/* Dynamic Status Icon / Sequence badge */}
        <div
          data-testid="step-status-indicator"
          data-status={status}
          className="flex size-7 shrink-0 items-center justify-center pt-0.5"
        >
          {status === "started" && (
            <div
              data-testid="step-spinner"
              aria-label={`Step ${seq} executing`}
              className="size-5 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent dark:border-indigo-400"
            />
          )}

          {status === "verified" && (
            <span
              data-testid="step-verified-icon"
              aria-label={`Step ${seq} verified`}
              className="flex size-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400"
            >
              <svg className="size-4" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </span>
          )}

          {status === "failed" && (
            <span
              data-testid="step-failed-icon"
              aria-label={`Step ${seq} failed`}
              className="flex size-6 items-center justify-center rounded-full bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-400"
            >
              <svg className="size-4" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </span>
          )}

          {status === "pending" && (
            <div
              data-testid="step-pending-icon"
              aria-label={`Step ${seq} pending`}
              className="flex size-6 items-center justify-center rounded-full bg-zinc-100 text-xs font-semibold text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
            >
              {seq}
            </div>
          )}
        </div>

        {/* Step details */}
        <div className="flex flex-1 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold text-zinc-500 dark:text-zinc-400">
              #{seq}
            </span>
            <span className="rounded-md bg-zinc-100 px-2 py-0.5 font-mono text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
              {actionType}
            </span>
            {hasTarget && (
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                on {targetRole && <span className="font-medium text-zinc-700 dark:text-zinc-300">{targetRole}</span>}
                {targetName && <span> &quot;{targetName}&quot;</span>}
              </span>
            )}

            {/* Status pills */}
            {status === "started" && (
              <span
                data-testid="step-running-badge"
                className="inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
              >
                <span className="size-1.5 animate-pulse rounded-full bg-indigo-600 dark:bg-indigo-400" />
                Executing…
              </span>
            )}

            {status === "verified" && (
              <span
                data-testid="step-verified-badge"
                className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
              >
                Verified
                {typeof confidence === "number" && (
                  <span className="text-[10px] opacity-80">({Math.round(confidence * 100)}%)</span>
                )}
              </span>
            )}

            {status === "failed" && (
              <span
                data-testid="step-failed-badge"
                className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 text-xs font-medium text-rose-700 dark:bg-rose-950 dark:text-rose-300"
              >
                Failed
              </span>
            )}
          </div>

          <p
            data-testid="step-instruction"
            className="text-sm font-medium leading-relaxed text-zinc-900 dark:text-zinc-100"
          >
            {instructionText}
          </p>

          {/* Verification methods badges */}
          {status === "verified" && methods && methods.length > 0 && (
            <div data-testid="step-methods" className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-xs text-zinc-500 dark:text-zinc-400">Verified via:</span>
              {methods.map((method) => (
                <span
                  key={method}
                  className="rounded-md border border-emerald-200 bg-white px-1.5 py-0.5 font-mono text-[11px] font-medium text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
                >
                  {method}
                </span>
              ))}
            </div>
          )}

          {/* Error Callout */}
          {status === "failed" && (
            <div
              data-testid="step-error-callout"
              className="mt-1 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
            >
              <div className="flex items-center gap-1.5 font-semibold text-rose-900 dark:text-rose-100">
                <svg className="size-4 shrink-0 text-rose-600 dark:text-rose-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <span>Verification Failed</span>
              </div>
              <p className="mt-1 leading-normal">{error || "Observed state did not match expected preconditions."}</p>
              {(observedUrl || observedTitle) && (
                <div className="mt-2 font-mono text-[11px] text-rose-700/90 dark:text-rose-300/90">
                  {observedUrl && <div>Observed URL: {observedUrl}</div>}
                  {observedTitle && <div>Observed Title: {observedTitle}</div>}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Risk Badge */}
      <div className="flex shrink-0 items-center self-start pt-0.5 sm:self-center">
        <RiskBadge level={risk} size="sm" />
      </div>
    </li>
  );
}
