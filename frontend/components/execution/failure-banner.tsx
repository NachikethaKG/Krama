import type { ApiError } from "@krama/contracts-ts";

export interface FailureBannerProps {
  error?: ApiError | null;
  onRetry?: () => void;
  className?: string;
}

export function FailureBanner({ error, onRetry, className = "" }: FailureBannerProps) {
  const errorCode = error?.code || "internal";
  const errorMessage =
    error?.message ||
    "An unrecoverable failure occurred during workflow execution.";

  return (
    <div
      role="alert"
      data-testid="failure-banner"
      className={`rounded-xl border border-rose-300 bg-rose-50 p-4 shadow-xs sm:p-5 dark:border-rose-900/80 dark:bg-rose-950/40 ${className}`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3.5">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-rose-100 text-rose-700 dark:bg-rose-900/60 dark:text-rose-300">
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
              <h3 className="text-sm font-semibold text-rose-950 dark:text-rose-100">
                Workflow Execution Failed
              </h3>
              <span
                data-testid="failure-code-badge"
                className="rounded-md border border-rose-300 bg-rose-100/70 px-2 py-0.5 font-mono text-[11px] font-semibold text-rose-800 uppercase dark:border-rose-800 dark:bg-rose-900/70 dark:text-rose-200"
              >
                {errorCode}
              </span>
            </div>

            <p data-testid="failure-message" className="text-xs text-rose-900/90 sm:text-sm dark:text-rose-200/90">
              {errorMessage}
            </p>

            <div className="mt-1 flex items-start gap-1.5 text-xs text-rose-800/80 dark:text-rose-300/80">
              <span className="font-medium">Remediation:</span>
              <span>
                Verify target system state and inspect the failed step verification assertions.
              </span>
            </div>
          </div>
        </div>

        {/* Retry Button */}
        {onRetry && (
          <div className="flex shrink-0 items-center pl-12 sm:pl-0 sm:pt-0.5">
            <button
              type="button"
              data-testid="retry-run-btn"
              onClick={onRetry}
              className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-rose-500 focus:outline-hidden focus:ring-2 focus:ring-rose-500/50 dark:bg-rose-500 dark:hover:bg-rose-400"
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
          </div>
        )}
      </div>
    </div>
  );
}
