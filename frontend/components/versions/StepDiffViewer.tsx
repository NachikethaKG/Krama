"use client";

import React from "react";
import { useTranslations } from "next-intl";
import type { StepDiffItem } from "@/types/tutorial";

export interface StepDiffViewerProps {
  diffs?: StepDiffItem[];
  fromVersion?: string;
  toVersion?: string;
  changeSummary?: string;
  className?: string;
}

export function StepDiffViewer({
  diffs = [],
  fromVersion,
  toVersion,
  changeSummary,
  className = "",
}: StepDiffViewerProps) {
  const t = useTranslations("tutorial");
  const modifiedCount = diffs.filter((d) => d.changeType !== "unchanged").length;
  const unchangedCount = diffs.filter((d) => d.changeType === "unchanged").length;

  if (diffs.length === 0) {
    return (
      <div
        data-testid="step-diff-viewer"
        className={`rounded-xl border border-zinc-200 bg-white p-6 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400 ${className}`}
      >
        <p data-testid="step-diff-empty">
          {t("diff.empty")}
        </p>
      </div>
    );
  }

  return (
    <div
      data-testid="step-diff-viewer"
      className={`flex flex-col gap-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950 ${className}`}
    >
      {/* Header with version compare metadata */}
      <div className="flex flex-col gap-1 border-b border-zinc-100 pb-3 dark:border-zinc-900">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
              {t("diff.title")}
            </span>
            {fromVersion && toVersion && (
              <span
                data-testid="diff-version-comparison"
                className="inline-flex items-center gap-1 rounded bg-zinc-100 px-2 py-0.5 text-xs font-mono font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
              >
                <span>{fromVersion}</span>
                <span className="text-zinc-400">→</span>
                <span className="text-indigo-600 dark:text-indigo-400 font-bold">{toVersion}</span>
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
            <span className="text-emerald-600 dark:text-emerald-400 font-medium">
              {t("diff.modified", { count: modifiedCount })}
            </span>
            <span>·</span>
            <span>{t("diff.unchangedCount", { count: unchangedCount })}</span>
          </div>
        </div>

        {changeSummary && (
          <p
            data-testid="diff-change-summary"
            className="text-xs text-zinc-600 dark:text-zinc-300 font-medium mt-1"
          >
            {changeSummary}
          </p>
        )}
      </div>

      {/* Step comparison list */}
      <div className="flex flex-col gap-3" data-testid="step-diff-list">
        {diffs.map((step) => {
          if (step.changeType === "unchanged") {
            return (
              <div
                key={step.stepIndex}
                data-testid="step-diff-item"
                data-change-type="unchanged"
                className="flex items-center justify-between rounded-lg border border-zinc-100 bg-zinc-50/70 px-3 py-2 text-xs text-zinc-500 dark:border-zinc-900 dark:bg-zinc-900/30 dark:text-zinc-400"
              >
                <div className="flex items-center gap-2 truncate">
                  <span className="size-5 rounded-full bg-zinc-200 flex items-center justify-center text-[10px] font-mono text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                    {step.stepIndex}
                  </span>
                  <span className="truncate">{step.stepTitle}</span>
                </div>
                <span className="rounded px-1.5 py-0.5 text-[10px] font-medium text-zinc-400 uppercase tracking-wider">
                  {t("diff.unchanged")}
                </span>
              </div>
            );
          }

          const isHealed = step.changeType === "locator_healed";

          return (
            <div
              key={step.stepIndex}
              data-testid="step-diff-item"
              data-change-type={step.changeType}
              className={`flex flex-col gap-3 rounded-lg border p-4 transition-colors ${
                isHealed
                  ? "border-emerald-200 bg-emerald-50/30 dark:border-emerald-900/70 dark:bg-emerald-950/20"
                  : "border-sky-200 bg-sky-50/30 dark:border-sky-900/70 dark:bg-sky-950/20"
              }`}
            >
              {/* Step Header */}
              <div className="flex items-center justify-between gap-2 border-b border-zinc-100/80 pb-2 dark:border-zinc-800/60">
                <div className="flex items-center gap-2">
                  <span
                    className={`flex size-6 items-center justify-center rounded-full text-xs font-bold ${
                      isHealed
                        ? "bg-emerald-600 text-white dark:bg-emerald-500"
                        : "bg-sky-600 text-white dark:bg-sky-500"
                    }`}
                  >
                    {step.stepIndex}
                  </span>
                  <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    {step.stepTitle}
                  </span>
                </div>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                    isHealed
                      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-200"
                      : "bg-sky-100 text-sky-800 dark:bg-sky-900/60 dark:text-sky-200"
                  }`}
                >
                  {isHealed ? t("diff.locatorHealed") : t("diff.wordingChanged")}
                </span>
              </div>

              {/* Locator / Label Diffs */}
              {(step.oldSelector || step.newSelector || step.oldLabel || step.newLabel) && (
                <div className="flex flex-col gap-2 rounded-md bg-white/80 p-3 text-xs dark:bg-zinc-900/60">
                  {/* Selector Diff */}
                  {(step.oldSelector || step.newSelector) && (
                    <div className="flex flex-col gap-1">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                        {t("diff.targetSelector")}
                      </span>
                      <div className="flex flex-wrap items-center gap-2 font-mono">
                        {step.oldSelector && (
                          <span
                            data-testid="diff-old-selector"
                            className="rounded border border-rose-200 bg-rose-50 px-2 py-0.5 text-rose-700 line-through dark:border-rose-900/70 dark:bg-rose-950/50 dark:text-rose-300"
                          >
                            {step.oldSelector}
                          </span>
                        )}
                        <span className="text-zinc-400">→</span>
                        {step.newSelector && (
                          <span
                            data-testid="diff-new-selector"
                            className="rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200"
                          >
                            {step.newSelector}
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Accessible Label Diff */}
                  {(step.oldLabel || step.newLabel) && (
                    <div className="flex flex-col gap-1 mt-1">
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                        {t("diff.elementLabel")}
                      </span>
                      <div className="flex flex-wrap items-center gap-2">
                        {step.oldLabel && (
                          <span
                            data-testid="diff-old-label"
                            className="rounded border border-rose-200 bg-rose-50 px-2 py-0.5 text-rose-700 line-through dark:border-rose-900/70 dark:bg-rose-950/50 dark:text-rose-300"
                          >
                            {t("diff.quoted", { text: step.oldLabel })}
                          </span>
                        )}
                        <span className="text-zinc-400">→</span>
                        {step.newLabel && (
                          <span
                            data-testid="diff-new-label"
                            className="rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 font-semibold text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-200"
                          >
                            {t("diff.quoted", { text: step.newLabel })}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Caption / Instruction Text Diff */}
              {(step.oldCaption || step.newCaption) && (
                <div className="flex flex-col gap-1.5 rounded-md bg-white/80 p-3 text-xs dark:bg-zinc-900/60">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                    {t("diff.instructionCaption")}
                  </span>
                  <div className="flex flex-col gap-1">
                    {step.oldCaption && (
                      <div className="flex items-start gap-1.5 text-rose-700 dark:text-rose-300 line-through">
                        <span className="font-mono text-[10px] font-bold text-rose-400">-</span>
                        <span data-testid="diff-old-caption">{step.oldCaption}</span>
                      </div>
                    )}
                    {step.newCaption && (
                      <div className="flex items-start gap-1.5 text-emerald-800 font-medium dark:text-emerald-200">
                        <span className="font-mono text-[10px] font-bold text-emerald-500">+</span>
                        <span data-testid="diff-new-caption">{step.newCaption}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
