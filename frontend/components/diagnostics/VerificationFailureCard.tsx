"use client";

import { useState } from "react";
import { artifactUrl } from "@/lib/artifacts";
import type { ElementRef, ExpectedState, FieldValue, ObservedSummary } from "@krama/contracts-ts";

export interface VerificationFailureCardProps {
  stepSeq?: number;
  instructionText?: string;
  failureReason?: string;
  failedLayer?: "url" | "dom" | "aria" | "network" | "vision" | "effect" | string;
  expected?: ExpectedState | {
    url_matches?: string;
    title_contains?: string;
    visible?: ElementRef[];
    absent?: ElementRef[];
    field_values?: FieldValue[];
    targetRole?: string | null;
    targetName?: string | null;
    targetSelector?: string | null;
  } | null;
  observed?: (ObservedSummary & { error?: string | null; missingSelector?: string | null; details?: string | null }) | {
    url?: string | null;
    title?: string | null;
    error?: string | null;
    missingSelector?: string | null;
    details?: string | null;
  } | null;
  /**
   * The screenshot taken before this step (the previous step's last one). The contract has no "expected"
   * screenshot, so the expected side is the expected STATE (shown as text) plus this "before" image.
   * Pass a loadable URL (resolve API references with `artifactUrl`).
   */
  previousScreenshotUrl?: string | null;
  observedScreenshotUrl?: string | null;
  onRetryReplan?: () => void;
  className?: string;
}

function resolveFailedLayer(
  explicitLayer?: string,
  expected?: VerificationFailureCardProps["expected"],
  observed?: VerificationFailureCardProps["observed"],
): string {
  if (explicitLayer) {
    const formatted = explicitLayer.toLowerCase();
    if (formatted.includes("url")) return "URL Verifier";
    if (formatted.includes("aria")) return "ARIA Verifier";
    if (formatted.includes("dom")) return "DOM Verifier";
    if (formatted.includes("vision")) return "Vision Verifier";
    if (formatted.includes("network")) return "Network Verifier";
    if (formatted.includes("effect")) return "Effect Signal";
    return explicitLayer;
  }

  if (expected?.url_matches && observed?.url && !observed.url.match(new RegExp(expected.url_matches))) {
    return "URL Verifier";
  }
  if (expected?.visible && expected.visible.length > 0) {
    return "ARIA Verifier";
  }
  if (expected?.absent && expected.absent.length > 0) {
    return "ARIA Verifier";
  }
  if (expected?.field_values && expected.field_values.length > 0) {
    return "DOM Verifier";
  }
  return "State Assertion Verifier";
}

export function VerificationFailureCard({
  stepSeq,
  instructionText,
  failureReason,
  failedLayer,
  expected,
  observed,
  previousScreenshotUrl,
  observedScreenshotUrl,
  onRetryReplan,
  className = "",
}: VerificationFailureCardProps) {
  const [previousImgError, setPreviousImgError] = useState(false);
  const [observedImgError, setObservedImgError] = useState(false);

  const layerName = resolveFailedLayer(failedLayer, expected, observed);
  const reasonText =
    failureReason || "Verification failed: observed state did not match expected preconditions.";

  // API screenshot references resolve against the API origin, never the Next.js origin.
  const previousSrc = artifactUrl(previousScreenshotUrl);
  const observedSrc = artifactUrl(observedScreenshotUrl);
  const hasPreviousScreenshot = Boolean(previousSrc) && !previousImgError;
  const hasObservedScreenshot = Boolean(observedSrc) && !observedImgError;

  const obs = observed as
    | (ObservedSummary & { error?: string | null; missingSelector?: string | null; details?: string | null })
    | { url?: string | null; title?: string | null; error?: string | null; missingSelector?: string | null; details?: string | null }
    | null
    | undefined;
  const observerFinding = obs?.error || obs?.details;
  const missingSelector = obs?.missingSelector;

  return (
    <section
      role="region"
      aria-label="Verification Failure Diagnostic"
      data-testid="verification-failure-card"
      className={`overflow-hidden rounded-2xl border border-rose-300 bg-white shadow-sm dark:border-rose-900/80 dark:bg-zinc-900 ${className}`}
    >
      {/* 1. Diagnostic Header */}
      <div className="border-b border-rose-200 bg-gradient-to-r from-rose-50 to-orange-50/40 p-4 sm:p-5 dark:border-rose-950 dark:from-rose-950/60 dark:to-zinc-900">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-rose-600 text-white shadow-xs dark:bg-rose-600">
              <svg className="size-5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m0 3.75h.008v.008H12v-.008zM10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                />
              </svg>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                  Step Verification Failure Diagnostic
                </h3>
                {stepSeq !== undefined && (
                  <span
                    data-testid="diagnostic-step-seq"
                    className="rounded-md bg-rose-100 px-2 py-0.5 font-mono text-xs font-semibold text-rose-800 dark:bg-rose-900/60 dark:text-rose-200"
                  >
                    Step #{stepSeq}
                  </span>
                )}
                <span
                  data-testid="failed-layer-badge"
                  className="rounded-md border border-rose-200 bg-white px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wide text-rose-700 uppercase shadow-2xs dark:border-rose-800 dark:bg-zinc-800 dark:text-rose-300"
                >
                  {layerName}
                </span>
              </div>

              {instructionText && (
                <p data-testid="diagnostic-instruction" className="text-xs font-medium text-zinc-600 sm:text-sm dark:text-zinc-400">
                  Target action: <span className="font-semibold text-zinc-800 dark:text-zinc-200">{instructionText}</span>
                </p>
              )}

              <p data-testid="diagnostic-reason" className="mt-1 text-xs font-medium text-rose-800 dark:text-rose-300">
                {reasonText}
              </p>
            </div>
          </div>

          {onRetryReplan && (
            <button
              type="button"
              data-testid="diagnostic-retry-btn"
              onClick={onRetryReplan}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-xs font-semibold text-rose-800 shadow-2xs transition hover:bg-rose-50 dark:border-rose-800 dark:bg-zinc-800 dark:text-rose-200 dark:hover:bg-zinc-700"
            >
              <svg className="size-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              Retry Replan
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-6 p-4 sm:p-6">
        {/* 2. Expected X vs Observed Y Text Comparison */}
        <div data-testid="expected-vs-observed-section" className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold tracking-wider text-zinc-500 uppercase dark:text-zinc-400">
              Assertion Breakdown: Expected (X) vs. Observed (Y)
            </h4>
            <span className="font-mono text-[11px] text-zinc-400 dark:text-zinc-500">
              State Diff
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Expected Box (X) */}
            <div
              data-testid="expected-state-box"
              className="flex flex-col gap-2.5 rounded-xl border border-emerald-200/90 bg-emerald-50/30 p-3.5 text-xs dark:border-emerald-900/60 dark:bg-emerald-950/20"
            >
              <div className="flex items-center gap-1.5 font-semibold text-emerald-900 dark:text-emerald-200">
                <span className="flex size-4 items-center justify-center rounded-full bg-emerald-600 text-[10px] font-bold text-white">
                  ✓
                </span>
                <span className="text-xs font-bold uppercase tracking-wider">Expected State (X)</span>
              </div>

              <div className="flex flex-col gap-1.5 font-mono text-[11px]">
                {expected?.url_matches && (
                  <div data-testid="expected-url" className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-semibold text-zinc-500 uppercase dark:text-zinc-400">URL Pattern:</span>
                    <span className="rounded bg-white/80 px-2 py-1 text-emerald-900 shadow-2xs dark:bg-zinc-800 dark:text-emerald-300">
                      {expected.url_matches}
                    </span>
                  </div>
                )}

                {expected?.title_contains && (
                  <div data-testid="expected-title" className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-semibold text-zinc-500 uppercase dark:text-zinc-400">Page Title:</span>
                    <span className="rounded bg-white/80 px-2 py-1 text-emerald-900 shadow-2xs dark:bg-zinc-800 dark:text-emerald-300">
                      contains &quot;{expected.title_contains}&quot;
                    </span>
                  </div>
                )}

                {expected?.visible && expected.visible.length > 0 && (
                  <div data-testid="expected-visible-elements" className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-semibold text-zinc-500 uppercase dark:text-zinc-400">Visible Elements:</span>
                    <div className="flex flex-wrap gap-1">
                      {expected.visible.map((elem, idx) => (
                        <span
                          key={`${elem.role}-${elem.name}-${idx}`}
                          className="rounded bg-white/80 px-1.5 py-0.5 text-emerald-900 shadow-2xs dark:bg-zinc-800 dark:text-emerald-300"
                        >
                          {elem.role} &quot;{elem.name}&quot;
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {expected?.absent && expected.absent.length > 0 && (
                  <div data-testid="expected-absent-elements" className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-semibold text-zinc-500 uppercase dark:text-zinc-400">Absent Elements (Must Not Appear):</span>
                    <div className="flex flex-wrap gap-1">
                      {expected.absent.map((elem, idx) => (
                        <span
                          key={`${elem.role}-${elem.name}-${idx}`}
                          className="rounded bg-white/80 px-1.5 py-0.5 text-emerald-900 shadow-2xs dark:bg-zinc-800 dark:text-emerald-300"
                        >
                          absent: {elem.role} &quot;{elem.name}&quot;
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {expected?.field_values && expected.field_values.length > 0 && (
                  <div data-testid="expected-field-values" className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-semibold text-zinc-500 uppercase dark:text-zinc-400">Field Values:</span>
                    <div className="flex flex-col gap-1">
                      {expected.field_values.map((field, idx) => (
                        <span
                          key={`${field.role}-${field.name}-${idx}`}
                          className="rounded bg-white/80 px-2 py-0.5 text-emerald-900 shadow-2xs dark:bg-zinc-800 dark:text-emerald-300"
                        >
                          {field.name} = &quot;{field.value}&quot;
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {!expected?.url_matches &&
                  !expected?.title_contains &&
                  (!expected?.visible || expected.visible.length === 0) &&
                  (!expected?.field_values || expected.field_values.length === 0) && (
                    <span className="text-zinc-500 italic">Precondition state not explicitly specified.</span>
                  )}
              </div>
            </div>

            {/* Observed Box (Y) */}
            <div
              data-testid="observed-state-box"
              className="flex flex-col gap-2.5 rounded-xl border border-rose-200/90 bg-rose-50/30 p-3.5 text-xs dark:border-rose-900/60 dark:bg-rose-950/20"
            >
              <div className="flex items-center gap-1.5 font-semibold text-rose-900 dark:text-rose-200">
                <span className="flex size-4 items-center justify-center rounded-full bg-rose-600 text-[10px] font-bold text-white">
                  ✕
                </span>
                <span className="text-xs font-bold uppercase tracking-wider">Observed State (Y)</span>
              </div>

              <div className="flex flex-col gap-1.5 font-mono text-[11px]">
                <div data-testid="observed-url" className="flex flex-col gap-0.5">
                  <span className="text-[10px] font-semibold text-zinc-500 uppercase dark:text-zinc-400">Landed URL:</span>
                  <span className="rounded bg-white/80 px-2 py-1 font-semibold text-rose-900 shadow-2xs dark:bg-zinc-800 dark:text-rose-300">
                    {observed?.url || "URL state unavailable or unchanged"}
                  </span>
                </div>

                {observed?.title && (
                  <div data-testid="observed-title" className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-semibold text-zinc-500 uppercase dark:text-zinc-400">Landed Page Title:</span>
                    <span className="rounded bg-white/80 px-2 py-1 text-rose-900 shadow-2xs dark:bg-zinc-800 dark:text-rose-300">
                      {observed.title}
                    </span>
                  </div>
                )}

                {observerFinding && (
                  <div data-testid="observed-error" className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-semibold text-zinc-500 uppercase dark:text-zinc-400">Observer Finding:</span>
                    <span className="rounded bg-white/80 px-2 py-1 text-rose-900 shadow-2xs dark:bg-zinc-800 dark:text-rose-300">
                      {observerFinding}
                    </span>
                  </div>
                )}

                {missingSelector && (
                  <div data-testid="observed-missing-selector" className="flex flex-col gap-0.5">
                    <span className="text-[10px] font-semibold text-zinc-500 uppercase dark:text-zinc-400">Missing Selector:</span>
                    <span className="rounded bg-white/80 px-2 py-1 text-rose-900 shadow-2xs dark:bg-zinc-800 dark:text-rose-300">
                      {missingSelector}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* 3. Side-by-Side Screenshot Comparison (ScreenshotDiff) */}
        <div data-testid="screenshot-comparison-section" className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold tracking-wider text-zinc-500 uppercase dark:text-zinc-400">
              Screenshots: Before vs. After This Step
            </h4>
            <span className="text-xs text-zinc-500 dark:text-zinc-400">
              Expected state is listed above
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {/* Column 1: the page before this step (previous step's screenshot) */}
            <div
              data-testid="previous-screenshot-col"
              className="flex flex-col overflow-hidden rounded-xl border border-zinc-200 bg-zinc-50/50 shadow-2xs dark:border-zinc-800 dark:bg-zinc-900/50"
            >
              <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-100/70 px-3 py-2 text-xs font-medium text-zinc-700 dark:border-zinc-800 dark:bg-zinc-800/60 dark:text-zinc-300">
                <span className="flex items-center gap-1.5 font-semibold">
                  <span className="size-2 rounded-full bg-emerald-500" />
                  Before This Step
                </span>
                <span className="font-mono text-[10px] text-zinc-400">Previous Step</span>
              </div>

              <div className="relative flex aspect-16/10 w-full items-center justify-center bg-zinc-100 dark:bg-zinc-950/60">
                {hasPreviousScreenshot ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    data-testid="previous-screenshot-img"
                    src={previousSrc}
                    alt="Page before this step"
                    onError={() => setPreviousImgError(true)}
                    className="h-full w-full object-contain"
                  />
                ) : (
                  <div
                    data-testid="previous-screenshot-placeholder"
                    className="flex flex-col items-center justify-center gap-2 p-6 text-center text-zinc-400 dark:text-zinc-500"
                  >
                    <svg className="size-8 opacity-60" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"
                      />
                    </svg>
                    <span className="text-xs font-medium">No earlier screenshot</span>
                    <span className="text-[10px] opacity-70">Compare with the expected state listed above</span>
                  </div>
                )}
              </div>
            </div>

            {/* Column 2: Observed State Snapshot */}
            <div
              data-testid="observed-screenshot-col"
              className="flex flex-col overflow-hidden rounded-xl border border-zinc-200 bg-zinc-50/50 shadow-2xs dark:border-zinc-800 dark:bg-zinc-900/50"
            >
              <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-100/70 px-3 py-2 text-xs font-medium text-zinc-700 dark:border-zinc-800 dark:bg-zinc-800/60 dark:text-zinc-300">
                <span className="flex items-center gap-1.5 font-semibold">
                  <span className="size-2 rounded-full bg-rose-500" />
                  Observed State (Actual)
                </span>
                <span className="font-mono text-[10px] text-zinc-400">Captured at Failure</span>
              </div>

              <div className="relative flex aspect-16/10 w-full items-center justify-center bg-zinc-100 dark:bg-zinc-950/60">
                {hasObservedScreenshot ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    data-testid="observed-screenshot-img"
                    src={observedSrc}
                    alt="Observed state capture"
                    onError={() => setObservedImgError(true)}
                    className="h-full w-full object-contain"
                  />
                ) : (
                  <div
                    data-testid="observed-screenshot-placeholder"
                    className="flex flex-col items-center justify-center gap-2 p-6 text-center text-zinc-400 dark:text-zinc-500"
                  >
                    <svg className="size-8 opacity-60" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z"
                      />
                      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z" />
                    </svg>
                    <span className="text-xs font-medium">Screenshot not captured or failed to load</span>
                    <span className="text-[10px] opacity-70">Observer artifact unavailable</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
