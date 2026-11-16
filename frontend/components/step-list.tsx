import type { CSSProperties } from "react";
import type { PlannedStep } from "@krama/contracts-ts";
import { ArrowDown, ArrowUp, PencilLine, Trash2 } from "lucide-react";

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

// Each bead on the sequence rail takes the next colour of the spectrum.
const BEAD_COLORS = ["var(--plan)", "var(--approve)", "var(--run)", "var(--verify)", "var(--learn)", "var(--ask)"];

const iconButton =
  "flex size-8 items-center justify-center rounded-full border border-white/15 bg-white/5 text-ink-300 transition-all hover:border-run hover:text-run disabled:cursor-not-allowed disabled:opacity-30";

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
        className={`rounded-[2rem] border-2 border-dashed border-white/15 p-10 text-center ${className}`}
      >
        <p className="text-sm text-ink-400">No steps proposed in this workflow plan.</p>
      </section>
    );
  }

  return (
    <section data-testid="step-list" aria-label="Planned execution steps" className={`flex flex-col gap-4 ${className}`}>
      <div className="flex items-center justify-between px-1">
        <h2 className="kr-display text-xl font-bold text-white">Proposed Steps ({steps.length})</h2>
        {isEditing && (
          <span className="kr-chip kr-plan">
            <PencilLine aria-hidden="true" className="size-3.5" />
            Editing step instructions and sequence
          </span>
        )}
      </div>

      <div className="relative">
        {/* the sequence rail: one glowing line the steps hang on */}
        <div
          aria-hidden="true"
          className="absolute bottom-6 left-[1.4rem] top-6 w-[3px] rounded-full"
          style={{
            background: `linear-gradient(180deg, ${BEAD_COLORS.slice(0, Math.max(2, steps.length)).join(", ")})`,
            boxShadow: "0 0 16px rgb(255 176 32 / 0.45)",
          }}
        />
        <ol className="relative flex flex-col gap-3">
          {steps.map((step, index) => {
            const actionType = step.action?.type ?? "action";
            const targetRole = step.target?.role;
            const targetName = step.target?.name;
            const hasTarget = Boolean(targetRole || targetName);
            const color = BEAD_COLORS[index % BEAD_COLORS.length];
            const risky = step.risk === "high";

            return (
              <li
                key={step.seq}
                data-testid="step-item"
                data-step-seq={step.seq}
                className="kr-rise group flex gap-4"
                style={{ animationDelay: `${Math.min(index, 8) * 60}ms` }}
              >
                {/* Step sequence bead */}
                <div
                  className="relative z-10 flex size-12 shrink-0 items-center justify-center rounded-full border-4 border-ink-950 font-mono text-sm font-extrabold text-oncolor transition-transform duration-300 group-hover:scale-110"
                  style={{ background: color, boxShadow: `0 0 24px -2px ${color}` }}
                >
                  {step.seq}
                </div>

                <div
                  className={`kr-tone-card flex flex-1 flex-col gap-3 rounded-3xl p-4 sm:flex-row sm:items-start sm:justify-between ${
                    risky ? "kr-danger" : ""
                  }`}
                  style={risky ? undefined : ({ "--kr-tone": color } as CSSProperties)}
                >
                  <div className="flex flex-1 flex-col gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className="rounded-full px-2.5 py-0.5 font-mono text-[11px] font-bold uppercase tracking-wider text-oncolor"
                        style={{ background: color }}
                      >
                        {actionType}
                      </span>
                      {hasTarget && (
                        <span className="text-xs text-ink-400">
                          on {targetRole && <span className="font-semibold text-ink-300">{targetRole}</span>}
                          {targetName && <span className="text-white"> &quot;{targetName}&quot;</span>}
                        </span>
                      )}
                    </div>

                    {/* Instruction text (editable or static) */}
                    {isEditing ? (
                      <div className="flex flex-col gap-1">
                        <label htmlFor={`step-input-${step.seq}`} className="sr-only">
                          Step {step.seq} instruction
                        </label>
                        <input
                          id={`step-input-${step.seq}`}
                          data-testid={`step-input-${step.seq}`}
                          type="text"
                          value={step.instruction_text}
                          onChange={(e) => onInstructionChange?.(step.seq, e.target.value)}
                          className="kr-input kr-plan w-full px-3 py-2 text-sm"
                        />
                      </div>
                    ) : (
                      <p data-testid="step-instruction" className="text-base font-medium leading-relaxed text-white">
                        {step.instruction_text}
                      </p>
                    )}
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
                          className={iconButton}
                          title="Move step up"
                        >
                          <ArrowUp aria-hidden="true" className="size-4" />
                        </button>

                        <button
                          type="button"
                          aria-label={`Move step ${step.seq} down`}
                          data-testid={`move-step-down-${step.seq}`}
                          disabled={index === steps.length - 1}
                          onClick={() => onMoveDown?.(step.seq)}
                          className={iconButton}
                          title="Move step down"
                        >
                          <ArrowDown aria-hidden="true" className="size-4" />
                        </button>

                        <button
                          type="button"
                          aria-label={`Delete step ${step.seq}`}
                          data-testid={`delete-step-${step.seq}`}
                          onClick={() => onDeleteStep?.(step.seq)}
                          className="flex size-8 items-center justify-center rounded-full border border-danger/40 bg-danger/10 text-danger transition-all hover:bg-danger hover:text-oncolor"
                          title="Delete step"
                        >
                          <Trash2 aria-hidden="true" className="size-4" />
                        </button>
                      </div>
                    )}
                    <RiskBadge level={step.risk} size="sm" />
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
