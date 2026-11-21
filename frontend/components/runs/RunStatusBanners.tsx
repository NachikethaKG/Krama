"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
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
  const t = useTranslations("runs");
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
        className={`kr-plan kr-tone-card flex flex-col gap-3 rounded-3xl p-5 ${className}`}
      >
        <div className="flex items-start gap-3">
          <div className="kr-dot-live mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-2xl bg-plan text-oncolor shadow-[0_0_24px_-4px_var(--plan)]">
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
            <h3 className="kr-display text-lg font-bold text-white">
              {t("banners.pausedTitle")}
            </h3>
            <p className="text-xs leading-relaxed text-ink-300">
              {pausedState?.message || t("banners.pausedDefault")}
            </p>
            {pausedState?.triggerContext && (
              <p className="text-[11px] font-medium text-plan">
                {t("banners.context")} <span className="font-semibold">{pausedState.triggerContext}</span>
                {pausedState.stepSeq ? t("banners.atStep", { seq: pausedState.stepSeq }) : ""}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center justify-end gap-2.5 pt-1 border-t border-plan/40">
          <button
            type="button"
            data-testid="abort-run-button"
            disabled={isSubmitting}
            onClick={handleAbort}
            className="kr-btn kr-btn-ghost kr-danger px-3.5 py-1.5 text-xs"
          >
            {isSubmitting ? t("banners.processing") : t("banners.abort")}
          </button>

          <button
            type="button"
            data-testid="allow-resume-button"
            disabled={isSubmitting}
            onClick={handleResume}
            className="kr-btn kr-btn-tone px-4 py-1.5 text-xs"
          >
            {isSubmitting ? t("banners.resuming") : t("banners.allowResume")}
          </button>
        </div>
      </div>
    );
  }

  if (status === "failed") {
    const errorMsg = failedState?.error || t("banners.failedDefault");
    const stepIndex = failedState?.stepSeq ?? "?";

    return (
      <div
        role="alert"
        data-testid="failed-banner"
        className={`kr-danger kr-tone-card flex flex-col gap-3 rounded-3xl p-5 ${className}`}
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-2xl bg-danger text-oncolor shadow-[0_0_24px_-4px_var(--danger)]">
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
            <h3 className="kr-display text-lg font-bold text-white">
              {t("banners.failedTitle", { step: String(stepIndex), error: errorMsg })}
            </h3>
            <p className="text-xs text-ink-300">
              {t("banners.failedBody")}
            </p>
          </div>
        </div>

        {/* Expected vs Observed Difference Card */}
        {(failedState?.expected || failedState?.observed) && (
          <div
            data-testid="expected-observed-card"
            className="rounded-2xl border border-danger/30 bg-ink-950/60 p-3"
          >
            <h4 className="text-[11px] font-bold uppercase tracking-wider text-danger mb-2">
              {t("banners.mismatch")}
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs font-mono">
              <div className="rounded-lg p-2.5 bg-ink-950">
                <span className="block text-[10px] uppercase font-bold text-ink-400 mb-1">
                  {t("banners.expected")}
                </span>
                <pre className="whitespace-pre-wrap text-ink-300 text-[11px]">
                  {typeof failedState.expected === "object"
                    ? JSON.stringify(failedState.expected, null, 2)
                    : String(failedState.expected)}
                </pre>
              </div>

              <div className="rounded-lg p-2.5 bg-ink-950">
                <span className="block text-[10px] uppercase font-bold text-ink-400 mb-1">
                  {t("banners.observed")}
                </span>
                <pre className="whitespace-pre-wrap text-ink-300 text-[11px]">
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
        className={`kr-spectrum-border kr-verify flex flex-col justify-between gap-3 rounded-3xl bg-ink-900/85 p-5 sm:flex-row sm:items-center ${className}`}
      >
        <div className="flex items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-verify text-oncolor shadow-[0_0_24px_-4px_var(--verify)]">
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
            <h3 className="kr-display text-lg font-bold text-white">
              {t("banners.completeTitle")}
            </h3>
            <p className="text-xs text-ink-300">
              {t("banners.completeBody")}
            </p>
          </div>
        </div>

        {workflowId && (
          <Link
            href={`/tutorials/${workflowId}`}
            data-testid="open-tutorial-btn"
            className="kr-btn kr-btn-primary px-4 py-1.5 text-xs"
          >
            {t("banners.openTutorial")}
          </Link>
        )}
      </div>
    );
  }

  return null;
}
