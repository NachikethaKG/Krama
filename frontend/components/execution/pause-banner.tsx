import type { PauseReason } from "@krama/contracts-ts";

export interface PauseBannerProps {
  reason: PauseReason;
  stepSeq: number;
  message?: string;
  onResume?: () => void;
  className?: string;
}

const REASON_DESCRIPTIONS: Record<PauseReason, string> = {
  destructive_action: "A destructive action requires human confirmation before proceeding.",
  captcha: "A bot detection or CAPTCHA was encountered and requires human intervention.",
  auth_wall: "An authentication barrier was reached and requires manual sign-in.",
  rate_limited: "A rate limit was triggered; execution is temporarily held.",
};

export function PauseBanner({
  reason,
  stepSeq,
  message,
  onResume,
  className = "",
}: PauseBannerProps) {
  const reasonText = REASON_DESCRIPTIONS[reason] || "Execution has been paused for safety.";

  return (
    <div
      role="alert"
      data-testid="pause-banner"
      data-pause-reason={reason}
      className={`rounded-xl border border-amber-300 bg-amber-50 p-4 shadow-xs sm:p-5 dark:border-amber-800/80 dark:bg-amber-950/40 ${className}`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3.5">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-900/60 dark:text-amber-300">
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
                d="M15.75 5.25v13.5m-7.5-13.5v13.5"
              />
            </svg>
          </div>

          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-amber-950 dark:text-amber-100">
                Execution Paused at Step {stepSeq}
              </h3>
              <span className="rounded-md border border-amber-300 bg-amber-100/70 px-2 py-0.5 font-mono text-[11px] font-semibold text-amber-800 uppercase dark:border-amber-700 dark:bg-amber-900/70 dark:text-amber-200">
                {reason.replace("_", " ")}
              </span>
            </div>

            <p className="text-xs text-amber-900/90 sm:text-sm dark:text-amber-200/90">
              {message || reasonText}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex shrink-0 items-center gap-2 pl-12 sm:pl-0">
          <button
            type="button"
            data-testid="resume-run-btn"
            onClick={onResume}
            className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-xs font-semibold text-white shadow-xs transition hover:bg-amber-500 focus:outline-hidden focus:ring-2 focus:ring-amber-500/50 dark:bg-amber-500 dark:hover:bg-amber-400"
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
                d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z"
              />
            </svg>
            Resume Execution
          </button>
        </div>
      </div>
    </div>
  );
}
