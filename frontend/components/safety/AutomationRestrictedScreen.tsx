"use client";

import React from "react";

export interface AutomationRestrictedScreenProps {
  barrierType: string;
  message?: string;
  targetUrl?: string;
  stepSeq?: number | null;
  onResume?: () => void | Promise<void>;
  onAbort?: () => void | Promise<void>;
  className?: string;
}

interface BarrierInfo {
  title: string;
  badge: string;
  explanation: string;
}

const BARRIER_CONFIG: Record<string, BarrierInfo> = {
  cloudflare_turnstile: {
    title: "Cloudflare Turnstile Detected",
    badge: "Cloudflare Turnstile",
    explanation:
      "A Cloudflare Turnstile challenge was encountered. Automated agents are strictly restricted from attempting to bypass or evade bot verification per Krama safety baseline rules.",
  },
  cloudflare_challenge: {
    title: "Cloudflare Challenge Interstitial",
    badge: "Cloudflare Challenge",
    explanation:
      "A Cloudflare security challenge or bot interstitial was detected. Automated bypass is strictly prevented per safety policy.",
  },
  recaptcha: {
    title: "Google reCAPTCHA Encountered",
    badge: "Google reCAPTCHA",
    explanation:
      "A Google reCAPTCHA challenge was detected on the page. Automated solving is disallowed; manual resolution is required.",
  },
  hcaptcha: {
    title: "hCaptcha Challenge Encountered",
    badge: "hCaptcha",
    explanation:
      "An hCaptcha challenge was detected on the page. Automated solving is disallowed; manual resolution is required.",
  },
  captcha: {
    title: "CAPTCHA Challenge Encountered",
    badge: "CAPTCHA Barrier",
    explanation:
      "A bot detection challenge (CAPTCHA) was encountered. Human intervention is required to complete the verification before automation can continue.",
  },
  auth_wall: {
    title: "Authentication / Login Gate Encountered",
    badge: "Login Barrier",
    explanation:
      "A login screen or authentication gate was reached that requires user authentication credentials. Manual sign-in is required before automation can proceed.",
  },
  login_wall: {
    title: "Login Wall Encountered",
    badge: "Login Barrier",
    explanation:
      "A login screen or authentication gate was reached that requires user authentication credentials. Manual sign-in is required before automation can proceed.",
  },
};

export function AutomationRestrictedScreen({
  barrierType = "cloudflare_turnstile",
  message,
  targetUrl = "http://localhost:3001",
  stepSeq,
  onResume,
  onAbort,
  className = "",
}: AutomationRestrictedScreenProps) {
  const normalizedKey = barrierType.toLowerCase().replace(/-/g, "_").trim();
  const barrier =
    BARRIER_CONFIG[normalizedKey] || {
      title: "Security Barrier Encountered",
      badge: barrierType.replace(/_/g, " ").toUpperCase(),
      explanation:
        "An anti-bot challenge or authentication restriction was encountered. Automated bypass is prohibited per safety baseline rules.",
    };

  return (
    <div
      role="alert"
      aria-live="assertive"
      data-testid="automation-restricted-screen"
      className={`rounded-2xl border-2 border-amber-400 bg-amber-50/90 p-6 shadow-lg sm:p-8 dark:border-amber-600 dark:bg-amber-950/40 ${className}`}
    >
      <div className="flex flex-col gap-6">
        {/* Header with Barrier Badge */}
        <div className="flex items-start gap-4">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-amber-200/80 text-amber-900 dark:bg-amber-900/80 dark:text-amber-200">
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
              <h2 className="text-xl font-bold tracking-tight text-amber-950 dark:text-amber-100">
                Automation restricted &rarr; Take over manually
              </h2>
              <span
                data-testid="barrier-type-badge"
                className="rounded-md border border-amber-300 bg-amber-100/90 px-2.5 py-0.5 font-mono text-xs font-semibold uppercase text-amber-900 dark:border-amber-700 dark:bg-amber-900/90 dark:text-amber-200"
              >
                {barrier.badge}
              </span>
            </div>
            <p className="mt-1 text-sm text-amber-900/80 dark:text-amber-300/80">
              {barrier.explanation}
            </p>
          </div>
        </div>

        {/* Detailed Message / Reason Banner */}
        {message && (
          <div className="rounded-xl border border-amber-300 bg-amber-100/60 p-3.5 text-xs text-amber-950 dark:border-amber-800/80 dark:bg-amber-900/40 dark:text-amber-200">
            <span className="font-semibold">Detection Detail: </span>
            {message}
          </div>
        )}

        {/* Target URL Reference Card */}
        <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-2xs dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                Target Location {stepSeq ? `(Step ${stepSeq})` : ""}
              </span>
              <p className="mt-0.5 font-mono text-xs font-medium text-zinc-900 dark:text-zinc-100 break-all">
                {targetUrl}
              </p>
            </div>

            <a
              href={targetUrl}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="open-target-url-btn"
              className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3.5 py-2 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-100 dark:border-indigo-800 dark:bg-indigo-950/60 dark:text-indigo-300 dark:hover:bg-indigo-900/60"
            >
              Open Target URL
              <svg aria-hidden="true" className="size-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
              </svg>
            </a>
          </div>
        </div>

        {/* Manual Takeover Instructions */}
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900/50 dark:bg-amber-950/20">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-amber-900 dark:text-amber-200">
            Manual Takeover Workflow
          </h3>
          <ol className="mt-2.5 list-decimal space-y-1.5 pl-4 text-xs text-amber-900/90 dark:text-amber-300/90 leading-relaxed">
            <li>
              Click <span className="font-semibold">&ldquo;Open Target URL&rdquo;</span> to view the blocked challenge page in your browser.
            </li>
            <li>
              Complete the CAPTCHA puzzle, check Turnstile verification, or sign into your account manually.
            </li>
            <li>
              Once passed, click <span className="font-semibold">&ldquo;Resume Execution&rdquo;</span> to continue automated workflow replay.
            </li>
          </ol>
        </div>

        {/* Action Controls */}
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-end">
          {onAbort && (
            <button
              type="button"
              data-testid="takeover-abort-btn"
              onClick={onAbort}
              className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-4 py-2.5 text-xs font-semibold text-zinc-700 shadow-xs transition hover:bg-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-rose-500/50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
            >
              <svg aria-hidden="true" className="size-3.5 text-rose-500" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              Abort Run
            </button>
          )}

          {onResume && (
            <button
              type="button"
              data-testid="takeover-resume-btn"
              onClick={onResume}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-amber-600 px-5 py-2.5 text-xs font-semibold text-white shadow-xs transition hover:bg-amber-500 focus:outline-hidden focus:ring-2 focus:ring-amber-500/50 dark:bg-amber-500 dark:hover:bg-amber-400"
            >
              <svg aria-hidden="true" className="size-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
              </svg>
              Resume Execution
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
