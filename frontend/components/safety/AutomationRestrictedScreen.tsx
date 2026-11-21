"use client";

import React from "react";
import { useTranslations } from "next-intl";

export interface AutomationRestrictedScreenProps {
  barrierType: string;
  message?: string;
  targetUrl?: string;
  stepSeq?: number | null;
  /** Where "Start a new task" goes (default: the home page). */
  newTaskHref?: string;
  /** Optional link to the run's evidence page. */
  runHref?: string;
  className?: string;
}

/**
 * Known barriers. Title, badge and explanation are messages under restricted.barrier.<key> in the "safety"
 * namespace; login_wall shares auth_wall's badge and explanation.
 */
const BARRIER_KEYS = new Set([
  "cloudflare_turnstile",
  "cloudflare_challenge",
  "recaptcha",
  "hcaptcha",
  "captcha",
  "auth_wall",
  "login_wall",
]);

export function AutomationRestrictedScreen({
  barrierType,
  message,
  targetUrl,
  stepSeq,
  newTaskHref = "/",
  runHref,
  className = "",
}: AutomationRestrictedScreenProps) {
  const t = useTranslations("safety");
  const normalizedKey = barrierType.toLowerCase().replace(/-/g, "_").trim();
  const barrier = BARRIER_KEYS.has(normalizedKey)
    ? {
        badge: t(`restricted.barrier.${normalizedKey}.badge`),
        explanation: t(`restricted.barrier.${normalizedKey}.explanation`),
      }
    : {
        // An unknown barrier type from the API is shown as-is.
        badge: barrierType.replace(/_/g, " ").toUpperCase(),
        explanation: t("restricted.unknownExplanation"),
      };

  return (
    <div
      role="alert"
      aria-live="assertive"
      data-testid="automation-restricted-screen"
      className={`kr-plan kr-tone-card relative overflow-hidden rounded-[2rem] p-6 pt-8 sm:p-8 sm:pt-10 ${className}`}
    >
      {/* caution tape */}
      <div
        aria-hidden="true"
        className="absolute inset-x-0 top-0 h-2.5"
        style={{ background: "repeating-linear-gradient(-45deg, var(--plan) 0 14px, var(--ink-950) 14px 28px)" }}
      />
      <div className="flex flex-col gap-6">
        {/* Header with Barrier Badge */}
        <div className="flex items-start gap-4">
          <div className="kr-float flex size-14 shrink-0 items-center justify-center rounded-2xl bg-plan text-oncolor shadow-[0_0_30px_-4px_var(--plan)]">
            <svg
              aria-hidden="true"
              className="size-7"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m0-10.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
              />
            </svg>
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2.5">
              <h2 className="kr-display text-2xl font-extrabold text-white">
                {t("restricted.title")} → {t("restricted.titleAction")}
              </h2>
              <span
                data-testid="barrier-type-badge"
                className="kr-chip kr-danger font-mono uppercase"
              >
                {barrier.badge}
              </span>
            </div>
            <p className="mt-2 text-sm text-ink-300">
              {barrier.explanation}
            </p>
          </div>
        </div>

        {/* Detailed Message / Reason Banner */}
        {message && (
          <div className="rounded-2xl border border-plan/40 bg-plan/10 p-3.5 text-xs text-plan">
            <span className="font-bold">{t("restricted.detectionDetail")} </span>
            {message}
          </div>
        )}

        {/* Target URL Reference Card */}
        {targetUrl && (
        <div className="rounded-2xl border border-white/10 bg-ink-950/60 p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-widest text-run">
                {t("restricted.targetLocation")} {stepSeq ? t("restricted.stepSuffix", { seq: stepSeq }) : ""}
              </span>
              <p className="mt-1 break-all font-mono text-xs font-medium text-white">
                {targetUrl}
              </p>
            </div>

            <a
              href={targetUrl}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="open-target-url-btn"
              className="kr-btn kr-btn-tone kr-run shrink-0 px-4 py-2 text-xs"
            >
              {t("restricted.openTarget")}
              <svg aria-hidden="true" className="size-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
            </a>
          </div>
        </div>
        )}

        {/* Manual Takeover Instructions */}
        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
          <h3 className="text-xs font-bold uppercase tracking-widest text-approve">
            {t("restricted.howTitle")}
          </h3>
          <ol className="mt-2.5 list-decimal space-y-1.5 pl-4 text-xs leading-relaxed text-ink-300 marker:font-bold marker:text-approve">
            <li>
              {t.rich("restricted.how1", {
                b: (chunks) => <span className="font-semibold text-white">{chunks}</span>,
              })}
            </li>
            <li>
              {t("restricted.how2")}
            </li>
            <li>
              {t("restricted.how3")}
            </li>
          </ol>
        </div>

        {/* The run already failed (policy stop): there is nothing to resume or abort, only ways forward. */}
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-end">
          {runHref && (
            <a
              href={runHref}
              data-testid="takeover-run-link"
              className="kr-btn kr-btn-ghost px-5 py-2.5 text-xs"
            >
              {t("restricted.viewRun")}
            </a>
          )}
          <a
            href={newTaskHref}
            data-testid="takeover-new-task-link"
            className="kr-btn kr-btn-primary px-6 py-2.5 text-xs"
          >
            {t("restricted.newTask")}
          </a>
        </div>
      </div>
    </div>
  );
}
