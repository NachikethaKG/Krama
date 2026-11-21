"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

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
  const t = useTranslations("execution");
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
      className={`kr-tone-card rounded-3xl p-4 transition-all sm:p-5 ${
        isExhausted ? "kr-danger" : isSucceeded ? "kr-verify" : "kr-approve"
      } ${className}`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3.5">
          {/* Animated Status Icon */}
          <div
            className={`flex size-11 shrink-0 items-center justify-center rounded-2xl text-oncolor ${
              isExhausted || isSucceeded ? "" : "kr-dot-live"
            }`}
            style={{ background: "var(--kr-tone)", boxShadow: "0 0 26px -4px var(--kr-tone)" }}
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
              <h3 className="kr-display text-lg font-bold text-white">
                {isExhausted
                  ? t("replan.exhaustedTitle")
                  : isSucceeded
                    ? t("replan.succeededTitle")
                    : t("replan.activeTitle")}
              </h3>

              {/* Status Badge */}
              <span
                data-testid={`replan-badge-${status}`}
                className={`kr-chip font-mono uppercase ${
                  status === "re-locating"
                    ? "kr-plan"
                    : status === "retrying"
                      ? "kr-run"
                      : status === "replanning"
                        ? "kr-approve"
                        : status === "exhausted"
                          ? "kr-danger"
                          : "kr-verify"
                }`}
              >
                {t(`replan.status.${status}`)}
              </span>

              {/* Attempt Counter Badge */}
              <span
                data-testid="replan-attempt-counter"
                className="rounded-full border border-white/15 bg-white/5 px-2.5 py-0.5 font-mono text-xs font-semibold text-ink-300"
              >
                {maxAttempts
                  ? t("replan.attemptOf", { attempt, max: maxAttempts })
                  : t("replan.attempt", { attempt })}
              </span>
            </div>

            {/* Reason */}
            {reason && (
              <p data-testid="replan-reason" className="text-xs text-ink-300">
                <span className="font-bold text-white">{t("replan.trigger")}</span> {reason}
              </p>
            )}

            {/* Strategy & Timeout */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-400">
              {strategy && (
                <span data-testid="replan-strategy">
                  <strong className="text-ink-300">{t("replan.strategy")}</strong> {strategy}
                </span>
              )}

              {countdown !== undefined && countdown > 0 && !isExhausted && !isSucceeded && (
                <span data-testid="replan-timeout" className="font-mono font-bold text-plan">
                  {t("replan.timeout", { seconds: countdown })}
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
                  className="kr-btn kr-btn-ghost kr-plan px-3 py-1.5 text-xs"
                >
                  <svg className="size-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
                  </svg>
                  {t("replan.takeover")}
                </button>
              )}

              {onAbort && (
                <button
                  type="button"
                  data-testid="replan-abort-btn"
                  onClick={onAbort}
                  className="kr-btn kr-btn-ghost kr-danger px-3 py-1.5 text-xs"
                >
                  <svg className="size-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  {t("replan.abort")}
                </button>
              )}
            </>
          )}

          {!isExhausted && !isSucceeded && onAbort && (
            <button
              type="button"
              data-testid="replan-cancel-btn"
              onClick={onAbort}
              className="kr-btn kr-btn-ghost px-2.5 py-1 text-xs"
            >
              {t("replan.cancel")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
