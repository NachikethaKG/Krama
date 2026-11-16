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
      className={`kr-glass flex flex-col rounded-3xl p-5 ${className}`}
    >
      <div className="flex items-center justify-between border-b pb-3 border-white/10">
        <div className="flex items-center gap-2">
          <h2 className="kr-display text-lg font-bold text-white">
            Execution Steps
          </h2>
          <span
            data-testid="step-count-badge"
            className="kr-chip kr-run"
          >
            {steps.length}
          </span>
        </div>

        {currentStepSeq && (
          <span className="text-xs text-ink-400">
            Current: Step {currentStepSeq}
          </span>
        )}
      </div>

      {steps.length === 0 ? (
        <div className="py-8 text-center text-xs text-ink-400">
          Waiting for execution plan…
        </div>
      ) : (
        <ol
          className="kr-scroll mt-3 flex max-h-[500px] flex-col gap-2.5 overflow-y-auto pr-1"
          aria-label="Planned execution steps"
        >
          {steps.map((step) => {
            const isActive = step.seq === currentStepSeq;
            return (
              <li
                key={step.seq}
                ref={isActive ? activeItemRef : null}
                data-testid={`step-checklist-item-${step.seq}`}
                className={`flex flex-col gap-1.5 rounded-2xl p-3.5 transition-all duration-300 ${
                  isActive
                    ? "kr-run kr-tone-card scale-[1.01]"
                    : step.status === "failed"
                      ? "kr-danger kr-tone-card"
                      : step.status === "paused"
                        ? "kr-plan kr-tone-card"
                        : step.status === "completed"
                          ? "kr-verify kr-tone-card"
                          : "border border-white/10 bg-ink-900/40 hover:bg-white/[0.06]"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5 min-w-0">
                    <span className="mt-0.5 shrink-0">
                      {step.status === "pending" && (
                        <span
                          data-testid="step-pending"
                          aria-label="Pending step"
                          className="flex size-5 items-center justify-center rounded-full border text-[10px] font-semibold border-white/10 bg-white/5 text-ink-400"
                        >
                          {step.seq}
                        </span>
                      )}

                      {step.status === "running" && (
                        <span
                          data-testid="step-running"
                          aria-label="Running step"
                          className="flex size-5 items-center justify-center rounded-full bg-run text-oncolor shadow-[0_0_12px_var(--run)]"
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
                          className="flex size-5 items-center justify-center rounded-full bg-verify text-oncolor shadow-[0_0_12px_var(--verify)]"
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
                          className="flex size-5 items-center justify-center rounded-full bg-plan text-oncolor shadow-[0_0_12px_var(--plan)]"
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
                          className="flex size-5 items-center justify-center rounded-full bg-danger text-oncolor shadow-[0_0_12px_var(--danger)]"
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

                    <span className="text-xs font-medium text-white leading-snug">
                      {step.instructionText}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0 text-[11px] font-medium">
                    {step.status === "completed" && step.durationMs !== undefined && (
                      <span className="font-mono text-ink-400">
                        {(step.durationMs / 1000).toFixed(1)}s
                      </span>
                    )}

                    <span
                      className={`capitalize px-2 py-0.5 rounded-md text-[10px] font-semibold ${
                        step.status === "completed"
                          ? "bg-verify/15 text-verify"
                          : step.status === "running"
                            ? "bg-run/15 text-run"
                            : step.status === "paused"
                              ? "bg-plan/15 text-plan"
                              : step.status === "failed"
                                ? "bg-danger/15 text-danger"
                                : "bg-white/[0.06] text-ink-400"
                      }`}
                    >
                      {step.status}
                    </span>
                  </div>
                </div>

                {step.status === "failed" && step.error && (
                  <div
                    data-testid="step-error-message"
                    className="mt-1 rounded-md p-2 text-[11px] bg-danger/15 text-danger font-mono"
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
