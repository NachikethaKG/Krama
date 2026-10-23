"use client";

import { useEffect, useRef } from "react";
import type { StreamStep } from "@/hooks/useRunStream";

export interface StepChecklistProps {
  steps: StreamStep[];
  currentStepSeq?: number | null;
  className?: string;
}

export function StepChecklist({ steps, currentStepSeq, className = "" }: StepChecklistProps) {
  const activeItemRef = useRef<HTMLLIElement | null>(null);

  // Auto-scroll to active step if list is long
  useEffect(() => {
    if (activeItemRef.current && typeof activeItemRef.current.scrollIntoView === "function") {
      activeItemRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [currentStepSeq]);

  return (
    <div
      data-testid="step-checklist"
      className={`flex flex-col rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 ${className}`}
    >
      <div className="flex items-center justify-between border-b border-zinc-100 pb-3 dark:border-zinc-800/80">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
            Execution Steps
          </h2>
          <span
            data-testid="step-count-badge"
            className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"
          >
            {steps.length}
          </span>
        </div>

        {currentStepSeq && (
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            Current: Step {currentStepSeq}
          </span>
        )}
      </div>

      {steps.length === 0 ? (
        <div className="py-8 text-center text-xs text-zinc-500 dark:text-zinc-400">
          Waiting for execution plan…
        </div>
      ) : (
        <ol
          className="mt-3 flex max-h-[500px] flex-col gap-2.5 overflow-y-auto pr-1"
          aria-label="Planned execution steps"
        >
          {steps.map((step) => {
            const isActive = step.seq === currentStepSeq;
            return (
              <li
                key={step.seq}
                ref={isActive ? activeItemRef : null}
                data-testid={`step-checklist-item-${step.seq}`}
                className={`flex flex-col gap-1.5 rounded-xl border p-3.5 transition-colors ${
                  isActive
                    ? "border-indigo-400/80 bg-indigo-50/50 shadow-xs dark:border-indigo-500/60 dark:bg-indigo-950/20"
                    : step.status === "failed"
                      ? "border-rose-200 bg-rose-50/40 dark:border-rose-900/40 dark:bg-rose-950/20"
                      : step.status === "paused"
                        ? "border-amber-200 bg-amber-50/40 dark:border-amber-900/40 dark:bg-amber-950/20"
                        : "border-zinc-100 bg-zinc-50/50 hover:bg-zinc-100/60 dark:border-zinc-800/60 dark:bg-zinc-900/40 dark:hover:bg-zinc-800/40"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5 min-w-0">
                    <span className="mt-0.5 shrink-0">
                      {step.status === "pending" && (
                        <span
                          data-testid="step-pending"
                          aria-label="Pending step"
                          className="flex size-5 items-center justify-center rounded-full border border-zinc-300 bg-zinc-100 text-[10px] font-semibold text-zinc-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400"
                        >
                          {step.seq}
                        </span>
                      )}

                      {step.status === "running" && (
                        <span
                          data-testid="step-running"
                          aria-label="Running step"
                          className="flex size-5 items-center justify-center rounded-full bg-indigo-600 text-white shadow-xs dark:bg-indigo-500"
                        >
                          <svg
                            className="size-3 animate-spin"
                            fill="none"
                            viewBox="0 0 24 24"
                          >
                            <circle
                              className="opacity-25"
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="4"
                            />
                            <path
                              className="opacity-75"
                              fill="currentColor"
                              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                            />
                          </svg>
                        </span>
                      )}

                      {step.status === "completed" && (
                        <span
                          data-testid="step-completed"
                          aria-label="Completed step"
                          className="flex size-5 items-center justify-center rounded-full bg-emerald-600 text-white shadow-xs dark:bg-emerald-500"
                        >
                          <svg
                            className="size-3"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth="3"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M4.5 12.75l6 6 9-13.5"
                            />
                          </svg>
                        </span>
                      )}

                      {step.status === "paused" && (
                        <span
                          data-testid="step-paused"
                          aria-label="Paused step"
                          className="flex size-5 items-center justify-center rounded-full bg-amber-500 text-white shadow-xs dark:bg-amber-600"
                        >
                          <svg
                            className="size-3"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth="2.5"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M15.75 5.25v13.5m-7.5-13.5v13.5"
                            />
                          </svg>
                        </span>
                      )}

                      {step.status === "failed" && (
                        <span
                          data-testid="step-failed"
                          aria-label="Failed step"
                          className="flex size-5 items-center justify-center rounded-full bg-rose-600 text-white shadow-xs dark:bg-rose-500"
                        >
                          <svg
                            className="size-3"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth="3"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M6 18L18 6M6 6l12 12"
                            />
                          </svg>
                        </span>
                      )}
                    </span>

                    <span className="text-xs font-medium text-zinc-900 dark:text-zinc-100 leading-snug">
                      {step.instructionText}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0 text-[11px] font-medium">
                    {step.status === "completed" && step.durationMs !== undefined && (
                      <span className="font-mono text-zinc-400 dark:text-zinc-500">
                        {(step.durationMs / 1000).toFixed(1)}s
                      </span>
                    )}

                    <span
                      className={`capitalize px-2 py-0.5 rounded-md text-[10px] font-semibold ${
                        step.status === "completed"
                          ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                          : step.status === "running"
                            ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
                            : step.status === "paused"
                              ? "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
                              : step.status === "failed"
                                ? "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300"
                                : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                      }`}
                    >
                      {step.status}
                    </span>
                  </div>
                </div>

                {step.status === "failed" && step.error && (
                  <div
                    data-testid="step-error-message"
                    className="mt-1 rounded-md bg-rose-50 p-2 text-[11px] text-rose-700 dark:bg-rose-950/50 dark:text-rose-300 font-mono"
                  >
                    {step.error}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
