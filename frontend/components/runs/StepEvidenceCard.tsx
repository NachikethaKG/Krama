"use client";

import { useState } from "react";
import { artifactUrl } from "@/lib/artifacts";
import type { StepEvidenceDetail, VerificationEvidenceMethod } from "@/lib/types";
import { RiskBadge } from "@/components/risk-badge";

export interface StepEvidenceCardProps {
  step: StepEvidenceDetail;
  index?: number;
  className?: string;
}

const METHOD_CONFIG: Record<
  VerificationEvidenceMethod,
  { label: string; description: string; className: string }
> = {
  url_dom: {
    label: "Page address",
    description: "Krama checked the page it landed on after this step.",
    className:
      "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800",
  },
  aria: {
    label: "Page content",
    description: "Krama checked that the page shows the expected button, field or text.",
    className:
      "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-400 dark:border-purple-800",
  },
  network: {
    label: "Site's answer",
    description: "The website confirmed the change.",
    className:
      "bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-400 dark:border-teal-800",
  },
  vision: {
    label: "Screenshot",
    description: "A look at the screenshot confirmed the step.",
    className:
      "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400 dark:border-indigo-800",
  },
};

export function getConfidenceDetails(confidence: number): {
  percentage: number;
  label: string;
  badgeClass: string;
} {
  const percentage = Math.round(confidence <= 1 ? confidence * 100 : confidence);
  if (percentage >= 90) {
    return {
      percentage,
      label: "Sure",
      badgeClass:
        "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800",
    };
  }
  if (percentage >= 70) {
    return {
      percentage,
      label: "Fairly sure",
      badgeClass:
        "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800",
    };
  }
  return {
    percentage,
    label: "Unsure",
    badgeClass:
      "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800",
  };
}

export function StepEvidenceCard({
  step,
  index,
  className = "",
}: StepEvidenceCardProps) {
  const [imageError, setImageError] = useState(false);
  const [showStateDetails, setShowStateDetails] = useState(false);

  const method = step.evidence?.method ?? "url_dom";
  const methodConfig = METHOD_CONFIG[method] ?? METHOD_CONFIG.url_dom;
  // No invented score: a step without a verification result shows "n/a".
  const confidence = step.evidence?.confidence ?? null;
  const confidenceDetails = getConfidenceDetails(confidence ?? 0);

  const isVerified = step.status === "verified";
  const isFailed = step.status === "failed";

  // API references (bare artifact keys or /api/... paths) resolve against the API, never the Next.js origin.
  const effectiveScreenshotUrl = artifactUrl(step.screenshotUrl || step.evidence?.screenshotUrl);
  const hasScreenshot = Boolean(effectiveScreenshotUrl);

  return (
    <div
      data-testid={`step-evidence-card-${step.seq}`}
      className={`border rounded-xl bg-white dark:bg-zinc-900 overflow-hidden shadow-sm transition-all ${
        isFailed
          ? "border-rose-300 dark:border-rose-800/80"
          : "border-zinc-200 dark:border-zinc-800"
      } ${className}`}
    >
      {/* Top Header */}
      <div className="p-4 sm:p-5 border-b border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-850/50 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span
            data-testid="step-seq-badge"
            className="flex items-center justify-center size-7 rounded-lg bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 font-mono text-xs font-bold"
          >
            {step.seq ?? (index !== undefined ? index + 1 : 1)}
          </span>
          <div>
            <h4
              data-testid="step-instruction"
              className="text-sm font-semibold text-zinc-900 dark:text-zinc-100"
            >
              {step.instructionText}
            </h4>
            <div
              data-testid="step-action-target"
              className="text-xs text-zinc-500 dark:text-zinc-400 flex items-center gap-2 mt-0.5"
            >
              <span>{describeAction(step.actionType, step.targetRole, step.targetName)}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <RiskBadge level={step.risk} size="sm" />
          <span
            data-testid="step-status"
            data-status={step.status}
            className={`inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded-full border ${
              isVerified
                ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800"
                : isFailed
                  ? "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800"
                  : "bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-300"
            }`}
          >
            {isVerified ? (
              <>
                <svg className="size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
                Verified
              </>
            ) : isFailed ? (
              <>
                <svg className="size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                </svg>
                Failed
              </>
            ) : (
              "Pending"
            )}
          </span>
        </div>
      </div>

      {/* Verification Evidence Badges & Metrics */}
      <div className="p-4 sm:p-5 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Method badge */}
          <div className="p-3 rounded-lg border border-zinc-100 dark:border-zinc-800 bg-zinc-50/60 dark:bg-zinc-850/40">
            <span className="text-[11px] font-medium text-zinc-500 dark:text-zinc-400 block mb-1">
              How it was checked
            </span>
            <div className="flex items-center gap-2">
              <span
                data-testid="verification-method-badge"
                data-method={method}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md border ${methodConfig.className}`}
              >
                <svg className="size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                {methodConfig.label}
              </span>
            </div>
            <p className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-1">
              {methodConfig.description}
            </p>
          </div>

          {/* Confidence Score */}
          <div className="p-3 rounded-lg border border-zinc-100 dark:border-zinc-800 bg-zinc-50/60 dark:bg-zinc-850/40">
            <span className="text-[11px] font-medium text-zinc-500 dark:text-zinc-400 block mb-1">
              How sure
            </span>
            <div className="flex items-center gap-2">
              <span
                data-testid="confidence-score"
                data-confidence={confidence ?? ""}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold rounded-md border ${
                  confidence === null
                    ? "bg-zinc-100 text-zinc-600 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700"
                    : confidenceDetails.badgeClass
                }`}
              >
                {confidence === null ? "n/a" : `${confidenceDetails.percentage}%`}
              </span>
              <span className="text-xs text-zinc-600 dark:text-zinc-400">
                {confidence === null ? "Not verified yet" : confidenceDetails.label}
              </span>
            </div>
            <div className="w-full bg-zinc-200 dark:bg-zinc-700 h-1.5 rounded-full mt-2 overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  confidenceDetails.percentage >= 90
                    ? "bg-emerald-500"
                    : confidenceDetails.percentage >= 70
                      ? "bg-amber-500"
                      : "bg-rose-500"
                }`}
                style={{
                  width: confidence === null ? "0%" : `${Math.min(100, Math.max(5, confidenceDetails.percentage))}%`,
                }}
              />
            </div>
          </div>
        </div>

        {/* Screenshot Viewer */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-zinc-600 dark:text-zinc-400">
            <span className="font-semibold text-zinc-800 dark:text-zinc-200">
              Screenshot after this step
            </span>
            {step.timing?.durationMs && (
              <span className="text-zinc-500 text-[11px]">
                Duration: {step.timing.durationMs}ms
              </span>
            )}
          </div>

          <div className="relative rounded-lg border border-zinc-200 dark:border-zinc-750 bg-zinc-950 overflow-hidden flex items-center justify-center min-h-[180px]">
            {hasScreenshot && !imageError && effectiveScreenshotUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={effectiveScreenshotUrl}
                alt={`Verification screenshot for step ${step.seq}: ${step.instructionText}`}
                data-testid="step-screenshot"
                onError={() => setImageError(true)}
                className="max-h-[360px] w-auto max-w-full object-contain mx-auto"
              />
            ) : (
              <div
                data-testid="step-screenshot-placeholder"
                className="flex flex-col items-center justify-center p-8 text-center text-zinc-400"
              >
                <svg
                  className="size-10 text-zinc-500 mb-2"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
                <span className="text-xs font-medium text-zinc-300">
                  {imageError
                    ? "Screenshot failed to load from artifact store"
                    : "No screenshot captured for this step"}
                </span>
                <span className="text-[11px] text-zinc-500 mt-0.5">
                  Verification was recorded via {methodConfig.label}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Expandable Expected vs Observed State */}
        {(step.expectedState || step.observedState) && (
          <div className="pt-2 border-t border-zinc-100 dark:border-zinc-800">
            <button
              type="button"
              data-testid="toggle-state-details-button"
              onClick={() => setShowStateDetails((prev) => !prev)}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-white transition-colors"
            >
              <svg
                className={`size-3.5 transition-transform ${showStateDetails ? "rotate-90" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              {showStateDetails ? "Hide" : "Show"} technical details
            </button>

            {showStateDetails && (
              <div
                data-testid="step-state-details"
                className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3 text-xs"
              >
                {/* Expected */}
                <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-850 border border-zinc-200 dark:border-zinc-800">
                  <span className="font-semibold text-zinc-900 dark:text-zinc-100 block mb-1">
                    Expected State
                  </span>
                  {step.expectedState?.url_matches && (
                    <div className="mb-1">
                      <span className="text-zinc-500">URL matches: </span>
                      <code className="font-mono text-[11px] bg-zinc-200/60 dark:bg-zinc-800 px-1 py-0.5 rounded">
                        {step.expectedState.url_matches}
                      </code>
                    </div>
                  )}
                  {step.expectedState?.visible && step.expectedState.visible.length > 0 && (
                    <div>
                      <span className="text-zinc-500">Visible: </span>
                      {step.expectedState.visible.map((el, i) => (
                        <span key={i} className="font-mono text-[11px] text-zinc-700 dark:text-zinc-300">
                          [{el.role}: &quot;{el.name}&quot;]
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Observed */}
                <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-850 border border-zinc-200 dark:border-zinc-800">
                  <span className="font-semibold text-zinc-900 dark:text-zinc-100 block mb-1">
                    Observed State
                  </span>
                  {step.observedState?.url && (
                    <div className="mb-1">
                      <span className="text-zinc-500">URL: </span>
                      <code className="font-mono text-[11px] bg-zinc-200/60 dark:bg-zinc-800 px-1 py-0.5 rounded">
                        {step.observedState.url}
                      </code>
                    </div>
                  )}
                  {step.observedState?.title && (
                    <div>
                      <span className="text-zinc-500">Title: </span>
                      <span className="text-zinc-700 dark:text-zinc-300">{step.observedState.title}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const ACTION_VERBS: Record<string, string> = {
  navigate: "Opened a page",
  click: "Clicked",
  fill: "Typed into",
  select: "Chose an option in",
  press: "Pressed a key in",
  wait: "Waited for",
  scroll: "Scrolled to",
};

const ROLE_NAMES: Record<string, string> = {
  textbox: "the field",
  searchbox: "the search field",
  combobox: "the field",
  button: "the button",
  link: "the link",
  checkbox: "the checkbox",
  radio: "the option",
  tab: "the tab",
  menuitem: "the menu item",
};

/** "Clicked the button “Create label”" instead of "click · role: button · name: Create label" (#318). */
export function describeAction(action: string, role?: string | null, name?: string | null): string {
  const verb = ACTION_VERBS[action] ?? action;
  if (!name) return verb;
  const what = role ? (ROLE_NAMES[role] ?? `the ${role}`) : "";
  return `${verb} ${what} \u201c${name}\u201d`.replace(/\s+/g, " ");
}
