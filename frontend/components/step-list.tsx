import type { PlannedStep } from "@krama/contracts-ts";

import { RiskBadge } from "./risk-badge";

export interface StepListProps {
  /** Plan steps (a workflow Step is a superset, so Step[] works too). */
  steps: PlannedStep[];
  isEditing?: boolean;
  onInstructionChange?: (seq: number, newInstruction: string) => void;
  onMoveUp?: (seq: number) => void;
  onMoveDown?: (seq: number) => void;
  onDeleteStep?: (seq: number) => void;
  className?: string;
}

export function StepList({
  steps,
  isEditing = false,
  onInstructionChange,
  onMoveUp,
  onMoveDown,
  onDeleteStep,
  className = "",
}: StepListProps) {
  if (!steps || steps.length === 0) {
    return (
      <section
        data-testid="step-list-empty"
        className={`rounded-xl border border-dashed border-zinc-300 p-8 text-center dark:border-zinc-700 ${className}`}
      >
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          No steps proposed in this workflow plan.
        </p>
      </section>
    );
  }

  return (
    <section
      data-testid="step-list"
      aria-label="Planned execution steps"
      className={`flex flex-col gap-3 ${className}`}
    >
      <div className="flex items-center justify-between px-1">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          Proposed Steps ({steps.length})
        </h2>
        {isEditing && (
          <span className="text-xs font-medium text-amber-600 dark:text-amber-400">
            Editing step instructions and sequence
          </span>
        )}
      </div>

      <ol className="flex flex-col gap-3">
        {steps.map((step, index) => {
          const actionType = step.action?.type ?? "action";
          const targetRole = step.target?.role;
          const targetName = step.target?.name;
          const hasTarget = Boolean(targetRole || targetName);

          return (
            <li
              key={step.seq}
              data-testid="step-item"
              data-step-seq={step.seq}
              className="group flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 transition-colors hover:border-zinc-300 sm:flex-row sm:items-start sm:justify-between dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
            >
              <div className="flex flex-1 items-start gap-3.5">
                {/* Step sequence pill */}
                <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-xs font-bold text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                  {step.seq}
                </div>

                <div className="flex flex-1 flex-col gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-md bg-zinc-100 px-2 py-0.5 font-mono text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                      {actionType}
                    </span>
                    {hasTarget && (
                      <span className="text-xs text-zinc-500 dark:text-zinc-400">
                        on {targetRole && <span className="font-medium text-zinc-700 dark:text-zinc-300">{targetRole}</span>}
                        {targetName && <span> &quot;{targetName}&quot;</span>}
                      </span>
                    )}
                  </div>

                  {/* Instruction text (editable or static) */}
                  {isEditing ? (
                    <div className="flex flex-col gap-1">
                      <label
                        htmlFor={`step-input-${step.seq}`}
                        className="sr-only"
                      >
                        Step {step.seq} instruction
                      </label>
                      <input
                        id={`step-input-${step.seq}`}
                        data-testid={`step-input-${step.seq}`}
                        type="text"
                        value={step.instruction_text}
                        onChange={(e) =>
                          onInstructionChange?.(step.seq, e.target.value)
                        }
                        className="w-full rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-900 shadow-xs focus:border-blue-500 focus:outline-hidden focus:ring-1 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                      />
                    </div>
                  ) : (
                    <p
                      data-testid="step-instruction"
                      className="text-sm font-medium leading-relaxed text-zinc-800 dark:text-zinc-200"
                    >
                      {step.instruction_text}
                    </p>
                  )}
                </div>
              </div>

              {/* Controls and Risk Badge */}
              <div className="flex shrink-0 flex-wrap items-center gap-2 self-start pt-0.5 sm:self-center">
                {isEditing && (
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      aria-label={`Move step ${step.seq} up`}
                      data-testid={`move-step-up-${step.seq}`}
                      disabled={index === 0}
                      onClick={() => onMoveUp?.(step.seq)}
                      className="rounded-md border border-zinc-200 p-1.5 text-zinc-600 transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                      title="Move step up"
                    >
                      <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
                      </svg>
                    </button>

                    <button
                      type="button"
                      aria-label={`Move step ${step.seq} down`}
                      data-testid={`move-step-down-${step.seq}`}
                      disabled={index === steps.length - 1}
                      onClick={() => onMoveDown?.(step.seq)}
                      className="rounded-md border border-zinc-200 p-1.5 text-zinc-600 transition-colors hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
                      title="Move step down"
                    >
                      <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
                      </svg>
                    </button>

                    <button
                      type="button"
                      aria-label={`Delete step ${step.seq}`}
                      data-testid={`delete-step-${step.seq}`}
                      onClick={() => onDeleteStep?.(step.seq)}
                      className="rounded-md border border-rose-200 p-1.5 text-rose-600 transition-colors hover:bg-rose-50 dark:border-rose-900/60 dark:text-rose-400 dark:hover:bg-rose-950/40"
                      title="Delete step"
                    >
                      <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </button>
                  </div>
                )}
                <RiskBadge level={step.risk} size="sm" />
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
