import type { ReactNode } from "react";
import type { StageKey } from "./stages";
import { STAGE } from "./stages";

/**
 * The big header at the top of an app page: a stage chip (which part of the pipeline you are in),
 * a display title and an optional subtitle and actions. The page is tinted by its stage colour.
 */
export function PageHero({
  stage,
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  stage: StageKey;
  eyebrow?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  const s = STAGE[stage];
  const Icon = s.icon;
  return (
    <div className={`${s.tone} kr-rise relative mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between`}>
      <div className="min-w-0">
        <span className="kr-chip mb-3">
          <Icon aria-hidden="true" className="size-3.5" />
          {eyebrow ?? s.label}
        </span>
        <h1 className="kr-display text-4xl font-extrabold leading-[1.05] text-white sm:text-5xl">{title}</h1>
        {subtitle && <p className="mt-3 max-w-2xl text-base text-ink-300">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      <div
        aria-hidden="true"
        className="absolute -bottom-4 left-0 h-px w-full"
        style={{ background: `linear-gradient(90deg, ${s.color}, transparent 70%)` }}
      />
    </div>
  );
}
