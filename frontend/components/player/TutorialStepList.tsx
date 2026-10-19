"use client";

import type { Scene, TutorialSpec } from "@krama/tutorial-compiler";

export interface TutorialStepListProps {
  spec: TutorialSpec;
  currentSceneIndex: number;
  onSelectStep: (index: number) => void;
  className?: string;
}

export function TutorialStepList({
  spec,
  currentSceneIndex,
  onSelectStep,
  className = "",
}: TutorialStepListProps) {
  const scenes = spec.scenes ?? [];

  return (
    <aside
      data-testid="step-list"
      aria-label="Tutorial step list"
      className={`flex flex-col rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950 ${className}`}
    >
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          Steps ({scenes.length})
        </h2>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          Total: {(spec.total_duration_ms / 1000).toFixed(1)}s
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto p-2" aria-label="Steps">
        <ol className="flex flex-col gap-1.5">
          {scenes.map((scene: Scene, index: number) => {
            const isActive = index === currentSceneIndex;
            const durationSec = (scene.duration_ms / 1000).toFixed(1);
            const stepTitle = scene.title || `${scene.action.type.toUpperCase()}`;

            return (
              <li key={scene.id ?? `step-${scene.step_seq}`}>
                <button
                  type="button"
                  data-testid={`step-item-${scene.step_seq}`}
                  onClick={() => onSelectStep(index)}
                  aria-current={isActive ? "step" : undefined}
                  className={`w-full rounded-md border p-2.5 text-left transition-all ${
                    isActive
                      ? "border-indigo-500 bg-indigo-50/70 shadow-xs dark:border-indigo-500 dark:bg-indigo-950/40"
                      : "border-transparent bg-transparent hover:border-zinc-200 hover:bg-zinc-50 dark:hover:border-zinc-800 dark:hover:bg-zinc-900/50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                          isActive
                            ? "bg-indigo-600 text-white dark:bg-indigo-500"
                            : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"
                        }`}
                      >
                        {scene.step_seq}
                      </span>
                      <span
                        className={`text-xs font-semibold ${
                          isActive
                            ? "text-indigo-950 dark:text-indigo-200"
                            : "text-zinc-800 dark:text-zinc-200"
                        }`}
                      >
                        {stepTitle}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {isActive && (
                        <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-medium text-indigo-700 dark:bg-indigo-900/60 dark:text-indigo-300">
                          Active
                        </span>
                      )}
                      <span className="text-[11px] font-mono text-zinc-400 dark:text-zinc-500">
                        {durationSec}s
                      </span>
                    </div>
                  </div>

                  <p
                    className={`mt-1 line-clamp-2 text-xs leading-relaxed ${
                      isActive
                        ? "text-zinc-900 dark:text-zinc-100 font-medium"
                        : "text-zinc-500 dark:text-zinc-400"
                    }`}
                  >
                    {scene.caption?.text || "No instruction"}
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
