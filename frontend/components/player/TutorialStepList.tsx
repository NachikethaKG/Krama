"use client";

import type { Scene, TutorialSpec } from "@krama/tutorial-compiler";
import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { stepColor } from "./spectrum";

export interface TutorialStepListProps {
  spec: TutorialSpec;
  currentSceneIndex: number;
  onSelectStep: (index: number) => void;
  onClose?: () => void;
  isDrawer?: boolean;
  className?: string;
}

export function TutorialStepList({
  spec,
  currentSceneIndex,
  onSelectStep,
  onClose,
  isDrawer = false,
  className = "",
}: TutorialStepListProps) {
  const t = useTranslations("player");
  const scenes = spec.scenes ?? [];

  return (
    <aside
      data-testid="step-list"
      aria-label={t("stepList.label")}
      className={`kr-glass flex flex-col overflow-hidden rounded-3xl ${className}`}
    >
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <div className="flex items-baseline gap-2">
          <h2 className="kr-display text-lg font-extrabold text-white">{t("stepList.heading", { count: scenes.length })}</h2>
          <span className="font-mono text-xs text-learn">
            {t("stepList.total", { seconds: ((spec.total_duration_ms || 1) / 1000).toFixed(1) })}
          </span>
        </div>

        {isDrawer && onClose && (
          <button
            type="button"
            onClick={onClose}
            data-testid="drawer-close-button"
            aria-label={t("stepList.close")}
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-2xl text-ink-300 transition-colors hover:bg-white/10 hover:text-white"
          >
            <X aria-hidden="true" className="size-5" />
          </button>
        )}
      </div>

      <nav className="kr-scroll flex-1 overflow-y-auto p-2.5" aria-label={t("stepList.nav")}>
        <ol className="relative flex flex-col gap-1.5">
          {scenes.map((scene: Scene, index: number) => {
            const isActive = index === currentSceneIndex;
            const isDone = index < currentSceneIndex;
            const color = stepColor(index);
            const durationSec = (scene.duration_ms / 1000).toFixed(1);
            const stepTitle = scene.title || `${scene.action.type.toUpperCase()}`;

            return (
              <li key={scene.id ?? `step-${scene.step_seq}`}>
                <button
                  type="button"
                  data-testid={`step-item-${scene.step_seq}`}
                  onClick={() => {
                    onSelectStep(index);
                    if (isDrawer && onClose) {
                      onClose();
                    }
                  }}
                  aria-current={isActive ? "step" : undefined}
                  className={`group flex min-h-[44px] w-full flex-col justify-center rounded-2xl border p-3 text-left transition-all duration-300 ${
                    isActive ? "translate-x-1" : "border-transparent hover:bg-white/5"
                  }`}
                  style={
                    isActive
                      ? {
                          borderColor: color,
                          background: `linear-gradient(110deg, color-mix(in oklab, ${color} 22%, transparent), transparent 75%)`,
                          boxShadow: `0 0 26px -10px ${color}`,
                        }
                      : undefined
                  }
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <span
                        className="flex size-7 shrink-0 items-center justify-center rounded-xl text-xs font-extrabold transition-all"
                        style={
                          isActive || isDone
                            ? { background: color, color: "var(--ink-950)", boxShadow: isActive ? `0 0 16px ${color}` : undefined }
                            : { border: `1.5px solid ${color}`, color }
                        }
                      >
                        {scene.step_seq}
                      </span>
                      <span className={`text-sm font-bold ${isActive ? "text-white" : "text-ink-300 group-hover:text-white"}`}>
                        {stepTitle}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {isActive && (
                        <span
                          className="rounded-full px-2 py-0.5 text-[10px] font-extrabold uppercase tracking-wider text-oncolor"
                          style={{ background: color }}
                        >
                          {t("stepList.active")}
                        </span>
                      )}
                      <span className="font-mono text-[11px] text-ink-400">{durationSec}s</span>
                    </div>
                  </div>

                  <p
                    className={`mt-1.5 line-clamp-2 pl-9 text-xs leading-relaxed ${
                      isActive ? "font-medium text-white" : "text-ink-400"
                    }`}
                  >
                    {scene.caption?.text || t("stepList.noInstruction")}
                  </p>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>
    </aside>
  );
}
