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
      className={`group relative flex flex-col gap-3 rounded-2xl p-4 transition-all duration-500 sm:flex-row sm:items-start sm:justify-between ${
        status === "started"
          ? "kr-run kr-tone-card scale-[1.01]"
          : status === "verified"
            ? "kr-verify kr-tone-card"
            : status === "failed"
              ? "kr-danger kr-tone-card"
              : "border border-white/[0.07] bg-white/[0.02] opacity-60"
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
              className="size-6 animate-spin rounded-full border-[3px] border-run border-t-transparent shadow-[0_0_14px_var(--run)]"
            />
          )}

          {status === "verified" && (
            <span
              data-testid="step-verified-icon"
              aria-label={`Step ${seq} verified`}
              className="flex size-7 items-center justify-center rounded-full bg-verify text-ink-950 shadow-[0_0_18px_var(--verify)]"
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
              className="flex size-7 items-center justify-center rounded-full bg-danger text-ink-950 shadow-[0_0_18px_var(--danger)]"
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
              className="flex size-7 items-center justify-center rounded-full border border-white/15 bg-ink-850 font-mono text-xs font-bold text-ink-400"
            >
              {seq}
            </div>
          )}
        </div>

        {/* Step details */}
        <div className="flex flex-1 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-bold text-ink-400">
              #{seq}
            </span>
            <span className="rounded-md bg-approve/15 px-2 py-0.5 font-mono text-xs font-bold text-approve">
              {actionType}
            </span>
            {hasTarget && (
              <span className="text-xs text-ink-400">
                on {targetRole && <span className="font-semibold text-ink-300">{targetRole}</span>}
                {targetName && <span> &quot;{targetName}&quot;</span>}
              </span>
            )}

            {/* Status pills */}
            {status === "started" && (
              <span
                data-testid="step-running-badge"
                className="kr-chip kr-run"
              >
                <span className="kr-dot kr-dot-live !size-1.5" />
                Executing…
              </span>
            )}

            {status === "verified" && (
              <span
                data-testid="step-verified-badge"
                className="kr-chip kr-verify"
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
                className="kr-chip kr-danger"
              >
                Failed
              </span>
            )}
          </div>

          <p
            data-testid="step-instruction"
            className="text-[15px] font-semibold leading-relaxed text-white"
          >
            {instructionText}
          </p>

          {/* Verification methods badges */}
          {status === "verified" && methods && methods.length > 0 && (
            <div data-testid="step-methods" className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-xs text-ink-400">Verified via:</span>
              {methods.map((method) => (
                <span
                  key={method}
                  className="rounded-md border border-verify/40 bg-verify/10 px-1.5 py-0.5 font-mono text-[11px] font-bold text-verify"
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
              className="mt-1 rounded-xl border border-danger/40 bg-danger/10 p-3 text-xs text-ink-300"
            >
              <div className="flex items-center gap-1.5 font-bold text-danger">
                <svg className="size-4 shrink-0 text-danger" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <span>Verification Failed</span>
              </div>
              <p className="mt-1 leading-normal">{error || "Observed state did not match expected preconditions."}</p>
              {(observedUrl || observedTitle) && (
                <div className="mt-2 font-mono text-[11px] text-ink-300">
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
