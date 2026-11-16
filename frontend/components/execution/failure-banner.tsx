import type { ApiError } from "@krama/contracts-ts";

export interface FailureBannerProps {
  error?: ApiError | null;
  failedStep?: { seq: number; instructionText?: string } | null;
  /** The plan this run executed; "Back to plan" links to its approval page. */
  planId?: string;
  onRetry?: () => void;
  onBackToPlan?: () => void;
  className?: string;
}

export function FailureBanner({
  error,
  failedStep,
  planId,
  onRetry,
  onBackToPlan,
  className = "",
}: FailureBannerProps) {
  const errorCode = error?.code || "validation_error";
  const errorMessage =
    error?.message ||
    "An unrecoverable failure occurred during workflow execution.";

  return (
    <div
      role="alert"
      data-testid="failure-banner"
      className={`kr-danger kr-tone-card relative overflow-hidden rounded-3xl p-4 sm:p-5 ${className}`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3.5">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-danger text-ink-950 shadow-[0_0_26px_-4px_var(--danger)]">
            <svg
              className="size-5"
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

          <div className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="kr-display text-lg font-bold text-white">
                Workflow Execution Failed
              </h3>
              <span
                data-testid="failure-code-badge"
                className="kr-chip font-mono uppercase"
              >
                {errorCode}
              </span>
            </div>

            {failedStep && (
              <div
                data-testid="failed-step-details"
                className="flex items-center gap-1.5 text-xs font-medium text-white"
              >
                <span className="rounded-md bg-danger/25 px-1.5 py-0.5 font-mono text-[10px] text-danger">
                  Step {failedStep.seq}
                </span>
                <span className="truncate">{failedStep.instructionText}</span>
              </div>
            )}

            <p data-testid="failure-message" className="text-xs text-ink-300 sm:text-sm">
              {errorMessage}
            </p>

            <div className="mt-1 flex items-start gap-1.5 text-xs text-ink-400">
              <span className="font-bold text-plan">Remediation:</span>
              <span>
                Verify target system state and inspect the failed step verification assertions.
              </span>
            </div>
          </div>
        </div>

        {/* Post-failure action controls */}
        <div className="flex shrink-0 flex-wrap items-center gap-2 pl-12 sm:pl-0 sm:pt-0.5">
          {onBackToPlan ? (
            <button
              type="button"
              data-testid="back-to-plan-btn"
              onClick={onBackToPlan}
              className="kr-btn kr-btn-ghost kr-approve px-3.5 py-2 text-xs"
            >
              Back to Plan
            </button>
          ) : (
            <a
              href={planId ? `/workflows/${planId}/approval` : "/"}
              data-testid="back-to-plan-btn"
              className="kr-btn kr-btn-ghost kr-approve px-3.5 py-2 text-xs"
            >
              Back to Plan
            </a>
          )}

          {onRetry && (
            <button
              type="button"
              data-testid="retry-run-btn"
              onClick={onRetry}
              className="kr-btn kr-btn-tone px-3.5 py-2 text-xs"
            >
              <svg
                className="size-3.5"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2.5}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
                />
              </svg>
              Retry Workflow
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
