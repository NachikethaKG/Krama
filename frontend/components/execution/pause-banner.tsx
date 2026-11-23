import type { ReactNode } from "react";
import type { PauseReason } from "@krama/contracts-ts";
import { useTranslations } from "next-intl";

export interface PauseBannerProps {
  reason: PauseReason;
  stepSeq: number;
  message?: string;
  onResume?: () => void;
  onDeny?: () => void;
  isConfirming?: boolean;
  /** Disables "allow" (e.g. the proposed steps of a replan_review are not loaded). Deny stays available. */
  allowDisabled?: boolean;
  /** No allow/deny buttons (#451): a sign-in pause is answered by taking over and signing in. */
  hideAnswers?: boolean;
  /** Extra content, e.g. the proposed steps of a replan_review pause. */
  children?: ReactNode;
  className?: string;
}

/*
 * Per reason, in the "execution" namespace: pauseBanner.allow.<reason> is what "allow" means
 * (POST /runs/{id}/confirm; "Deny" always cancels the run), pauseBanner.description.<reason> explains the stop
 * and pauseBanner.reason.<reason> names it.
 */

/** Each pause reason wears its own spectrum tone, so the kind of stop reads at a glance. */
const REASON_TONES: Record<PauseReason, string> = {
  destructive_action: "var(--danger)",
  captcha: "var(--plan)",
  auth_wall: "var(--plan)",
  rate_limited: "var(--plan)",
  verification_unclear: "var(--run)",
  replan_review: "var(--approve)",
  recovery_exhausted: "var(--learn)",
  no_progress: "var(--learn)",
  step_budget: "var(--plan)",
  sensitive_data: "var(--ask)",
  prompt_injection: "var(--danger)",
};

export function PauseBanner({
  reason,
  stepSeq,
  message,
  onResume,
  onDeny,
  isConfirming = false,
  allowDisabled = false,
  hideAnswers = false,
  children,
  className = "",
}: PauseBannerProps) {
  const t = useTranslations("execution");
  const known = reason in REASON_TONES;
  const reasonText = known ? t(`pauseBanner.description.${reason}`) : t("pauseBanner.defaultDescription");

  return (
    <div
      role="alert"
      data-testid="pause-banner"
      data-pause-reason={reason}
      style={{ ["--kr-tone" as string]: REASON_TONES[reason] ?? "var(--plan)" }}
      className={`kr-tone-card relative overflow-hidden rounded-3xl p-4 sm:p-5 ${className}`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3.5">
          <div className="kr-dot-live flex size-11 shrink-0 items-center justify-center rounded-2xl text-oncolor"
            style={{ background: "var(--kr-tone)", boxShadow: "0 0 26px -4px var(--kr-tone)" }}>
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
              <h3 className="kr-display text-lg font-bold text-white">
                {t("pauseBanner.title", { seq: stepSeq })}
              </h3>
              <span className="kr-chip font-mono uppercase">
                {known ? t(`pauseBanner.reason.${reason}`) : reason.replace(/_/g, " ")}
              </span>
            </div>

            <p className="text-xs text-ink-300 sm:text-sm">
              {message || reasonText}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        {hideAnswers ? null : (
        <div className="flex shrink-0 items-center gap-2 pl-12 sm:pl-0">
          {onDeny && (
            <button
              type="button"
              data-testid="deny-run-btn"
              disabled={isConfirming}
              onClick={onDeny}
              className="kr-btn kr-btn-ghost kr-danger px-3.5 py-2 text-xs"
            >
              <svg aria-hidden="true" className="size-3.5 text-danger" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              {isConfirming ? t("pauseBanner.processing") : t("pauseBanner.deny")}
            </button>
          )}

          <button
            type="button"
            data-testid="resume-run-btn"
            disabled={isConfirming || allowDisabled}
            onClick={onResume}
            className="kr-btn kr-btn-tone px-4 py-2 text-xs"
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
            {isConfirming
              ? t("pauseBanner.processing")
              : known
                ? t(`pauseBanner.allow.${reason}`)
                : t("pauseBanner.defaultAllow")}
          </button>
        </div>
        )}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}
