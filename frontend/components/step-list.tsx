import type { Step } from "@krama/contracts-ts";

import { RiskBadge } from "./risk-badge";

export interface StepListProps {
  steps: Step[];
  isEditing?: boolean;
  onInstructionChange?: (seq: number, newInstruction: string) => void;
  className?: string;
}

export function StepList({
  steps,
  isEditing = false,
  onInstructionChange,
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
            Editing step instructions
          </span>
        )}
      </div>

      <ol className="flex flex-col gap-3">
        {steps.map((step) => {
          const actionType = step.action?.type ?? "action";
          const targetRole = step.target?.role;
          const targetName = step.target?.name;
          const hasTarget = Boolean(targetRole || targetName);

          return (
            <li
              key={step.id || step.seq}
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

              {/* Risk Badge */}
              <div className="flex shrink-0 items-center self-start pt-0.5 sm:self-center">
                <RiskBadge level={step.risk} size="sm" />
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
