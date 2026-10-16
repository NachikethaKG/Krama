"use client";

import { useEffect, useState } from "react";

export type ReplanStatus =
  | "idle"
  | "re-locating"
  | "retrying"
  | "replanning"
  | "exhausted"
  | "succeeded";

export interface ReplanStatusIndicatorProps {
  status: ReplanStatus;
  attempt?: number;
  maxAttempts?: number;
  strategy?: string;
  timeoutSeconds?: number;
  reason?: string;
  onTakeover?: () => void;
  onAbort?: () => void;
  onResume?: () => void;
  className?: string;
}

export function ReplanStatusIndicator({
  status,
  attempt = 1,
  maxAttempts,
  strategy,
  timeoutSeconds,
  reason,
  onTakeover,
  onAbort,
  onResume,
  className = "",
}: ReplanStatusIndicatorProps) {
  const [countdown, setCountdown] = useState<number | undefined>(timeoutSeconds);
  const [prevTimeout, setPrevTimeout] = useState<number | undefined>(timeoutSeconds);

  if (timeoutSeconds !== prevTimeout) {
    setPrevTimeout(timeoutSeconds);
    setCountdown(timeoutSeconds);
  }

  useEffect(() => {
    if (countdown === undefined || countdown <= 0 || status === "exhausted" || status === "succeeded") {
      return;
    }
    const timer = setInterval(() => {
      setCountdown((prev) => (prev && prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [countdown, status]);

  if (status === "idle") {
    return null;
  }

  const isExhausted = status === "exhausted";
  const isSucceeded = status === "succeeded";

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="replan-status-indicator"
      data-replan-status={status}
      className={`rounded-xl border p-4 shadow-sm transition-all sm:p-5 ${
        isExhausted
          ? "border-rose-300 bg-rose-50/90 dark:border-rose-900/80 dark:bg-rose-950/40"
          : isSucceeded
            ? "border-emerald-300 bg-emerald-50/90 dark:border-emerald-900/80 dark:bg-emerald-950/40"
            : "border-indigo-300 bg-indigo-50/70 dark:border-indigo-900/80 dark:bg-indigo-950/40"
      } ${className}`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3.5">
          {/* Animated Status Icon */}
          <div
            className={`flex size-9 shrink-0 items-center justify-center rounded-xl text-white shadow-2xs ${
              isExhausted
                ? "bg-rose-600"
                : isSucceeded
                  ? "bg-emerald-600"
                  : "bg-indigo-600"
            }`}
          >
            {isExhausted ? (
              <svg className="size-5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0 3.75h.008v.008H12v-.008zM10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
            ) : isSucceeded ? (
              <svg className="size-5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            ) : (
              <svg className="size-5 animate-spin" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            {/* Badges row */}
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                {isExhausted
                  ? "Automatic Recovery Exhausted"
                  : isSucceeded
                    ? "Replan Recovery Succeeded"
                    : "Live Agent Recovery & Replanning"}
              </h3>

              {/* Status Badge */}
              <span
                data-testid={`replan-badge-${status}`}
                className={`rounded-md border px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wide uppercase ${
                  status === "re-locating"
                    ? "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-800 dark:bg-amber-950/80 dark:text-amber-200"
                    : status === "retrying"
                      ? "border-sky-300 bg-sky-100 text-sky-800 dark:border-sky-800 dark:bg-sky-950/80 dark:text-sky-200"
                      : status === "replanning"
                        ? "border-indigo-300 bg-indigo-100 text-indigo-800 dark:border-indigo-800 dark:bg-indigo-950/80 dark:text-indigo-200"
                        : status === "exhausted"
                          ? "border-rose-300 bg-rose-100 text-rose-800 dark:border-rose-800 dark:bg-rose-950/80 dark:text-rose-200"
                          : "border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-200"
                }`}
              >
                {status}
              </span>

              {/* Attempt Counter Badge */}
              <span
                data-testid="replan-attempt-counter"
                className="rounded-md border border-zinc-200 bg-white px-2 py-0.5 font-mono text-xs font-semibold text-zinc-700 shadow-2xs dark:border-zinc-800 dark:bg-zinc-800 dark:text-zinc-300"
              >
                {maxAttempts ? `Attempt ${attempt} of ${maxAttempts}` : `Attempt ${attempt}`}
              </span>
            </div>

            {/* Reason */}
            {reason && (
              <p data-testid="replan-reason" className="text-xs text-zinc-700 dark:text-zinc-300">
                <span className="font-semibold text-zinc-900 dark:text-zinc-100">Trigger:</span> {reason}
              </p>
            )}

            {/* Strategy & Timeout */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-600 dark:text-zinc-400">
              {strategy && (
                <span data-testid="replan-strategy">
                  <strong className="text-zinc-800 dark:text-zinc-200">Strategy:</strong> {strategy}
                </span>
              )}

              {countdown !== undefined && countdown > 0 && !isExhausted && !isSucceeded && (
                <span data-testid="replan-timeout" className="font-mono font-medium text-amber-700 dark:text-amber-400">
                  Timeout in {countdown}s
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Action Controls for Exhausted or Running State */}
        <div className="flex shrink-0 flex-wrap items-center gap-2 pl-12 sm:pl-0 sm:pt-0.5">
          {isExhausted && (
            <>
              {(onTakeover || onResume) && (
                <button
                  type="button"
                  data-testid="replan-takeover-btn"
                  onClick={onTakeover || onResume}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900 shadow-2xs transition hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/60 dark:text-amber-200 dark:hover:bg-amber-900/60"
                >
                  <svg className="size-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                  </svg>
                  Manual Takeover
                </button>
              )}

              {onAbort && (
                <button
                  type="button"
                  data-testid="replan-abort-btn"
                  onClick={onAbort}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-xs font-semibold text-rose-800 shadow-2xs transition hover:bg-rose-50 dark:border-rose-800 dark:bg-zinc-900 dark:text-rose-300 dark:hover:bg-rose-950/50"
                >
                  <svg className="size-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  Abort Run
                </button>
              )}
            </>
          )}

          {!isExhausted && !isSucceeded && onAbort && (
            <button
              type="button"
              data-testid="replan-cancel-btn"
              onClick={onAbort}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-2.5 py-1 text-xs font-medium text-zinc-700 transition hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
            >
              Cancel Replan
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
