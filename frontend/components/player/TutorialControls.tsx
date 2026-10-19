"use client";

import type { Scene, TutorialSpec } from "@krama/tutorial-compiler";

export interface TutorialControlsProps {
  spec: TutorialSpec;
  currentSceneIndex: number;
  currentScene: Scene | undefined;
  currentTimeMs: number;
  isPlaying: boolean;
  isZoomEnabled: boolean;
  isCaptionsEnabled: boolean;
  isFirstStep: boolean;
  isLastStep: boolean;
  sceneProgress: number;
  overallProgress: number;
  onPlay: () => void;
  onPause: () => void;
  onTogglePlay: () => void;
  onNextStep: () => void;
  onPrevStep: () => void;
  onReplayCurrentStep: () => void;
  onToggleZoom: () => void;
  onToggleCaptions: () => void;
  onSeek?: (timeMs: number) => void;
  className?: string;
}

function formatTime(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

export function TutorialControls({
  spec,
  currentSceneIndex,
  currentScene,
  currentTimeMs,
  isPlaying,
  isZoomEnabled,
  isCaptionsEnabled,
  isFirstStep,
  isLastStep,
  sceneProgress,
  overallProgress,
  onTogglePlay,
  onNextStep,
  onPrevStep,
  onReplayCurrentStep,
  onToggleZoom,
  onToggleCaptions,
  onSeek,
  className = "",
}: TutorialControlsProps) {
  const totalScenes = spec.scenes?.length ?? 0;
  const currentDurationMs = currentScene?.duration_ms ?? 1000;

  const handleProgressBarClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!onSeek) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    onSeek(ratio * currentDurationMs);
  };

  return (
    <div
      data-testid="tutorial-controls"
      className={`flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-3 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 ${className}`}
    >
      {/* Timeline Scrubbing Bar */}
      <div
        className="group relative h-2 w-full cursor-pointer rounded-full bg-zinc-200 dark:bg-zinc-800"
        onClick={handleProgressBarClick}
        role="progressbar"
        aria-valuenow={Math.round(sceneProgress * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Scene playback progress"
      >
        <div
          className="h-full rounded-full bg-indigo-600 transition-all duration-75 dark:bg-indigo-500"
          style={{ width: `${sceneProgress * 100}%` }}
        />
        {/* Step division markers */}
        <div className="pointer-events-none absolute inset-0 flex">
          {spec.scenes?.map((scene, idx) => (
            <div
              key={scene.id ?? idx}
              style={{ width: `${(scene.duration_ms / spec.total_duration_ms) * 100}%` }}
              className="h-full border-r border-white/50 first:border-l-0 last:border-r-0 dark:border-zinc-900/60"
            />
          ))}
        </div>
      </div>

      {/* Primary Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* Left: Transport Buttons */}
        <div className="flex items-center gap-1">
          {/* Previous Step */}
          <button
            type="button"
            onClick={onPrevStep}
            disabled={isFirstStep && currentTimeMs === 0}
            data-testid="control-prev-step"
            aria-label="Previous step"
            title="Previous step (ArrowLeft)"
            className="rounded-md p-1.5 text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" />
            </svg>
          </button>

          {/* Play / Pause Toggle */}
          <button
            type="button"
            onClick={onTogglePlay}
            data-testid="control-play-pause"
            aria-label={isPlaying ? "Pause tutorial" : "Play tutorial"}
            title={isPlaying ? "Pause (Space)" : "Play (Space)"}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 text-white shadow hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:bg-indigo-500 dark:hover:bg-indigo-600 dark:focus:ring-offset-zinc-950"
          >
            {isPlaying ? (
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 5h4v14H6zm8 0h4v14h-4z" />
              </svg>
            ) : (
              <svg className="h-5 w-5 translate-x-0.5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>

          {/* Replay Current Step */}
          <button
            type="button"
            onClick={onReplayCurrentStep}
            data-testid="control-replay-step"
            aria-label="Replay current step"
            title="Replay step (R)"
            className="rounded-md p-1.5 text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>

          {/* Next Step */}
          <button
            type="button"
            onClick={onNextStep}
            disabled={isLastStep}
            data-testid="control-next-step"
            aria-label="Next step"
            title="Next step (ArrowRight)"
            className="rounded-md p-1.5 text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
            </svg>
          </button>

          {/* Step & Time display */}
          <div className="ml-2 flex items-center gap-1.5 text-xs font-medium text-zinc-600 dark:text-zinc-400">
            <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
              Step {currentSceneIndex + 1} of {totalScenes}
            </span>
            <span>
              {formatTime(currentTimeMs)} / {formatTime(currentDurationMs)}
            </span>
            <span className="text-[11px] text-zinc-400 font-mono">
              ({Math.round(overallProgress * 100)}%)
            </span>
          </div>
        </div>

        {/* Right: View & Accessibility Toggles */}
        <div className="flex items-center gap-1.5">
          {/* Zoom Toggle */}
          <button
            type="button"
            onClick={onToggleZoom}
            data-testid="control-toggle-zoom"
            aria-pressed={isZoomEnabled}
            aria-label={isZoomEnabled ? "Disable auto-zoom" : "Enable auto-zoom"}
            title={`Toggle zoom (Z) - Currently ${isZoomEnabled ? "Auto-Zoom" : "Overview (1.0x)"}`}
            className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
              isZoomEnabled
                ? "bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-950/50 dark:text-indigo-300 dark:border-indigo-800"
                : "border border-zinc-200 bg-zinc-50 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800"
            }`}
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
              {isZoomEnabled ? (
                <>
                  <line x1="8" y1="11" x2="14" y2="11" />
                </>
              ) : (
                <>
                  <line x1="11" y1="8" x2="11" y2="14" />
                  <line x1="8" y1="11" x2="14" y2="11" />
                </>
              )}
            </svg>
            <span>{isZoomEnabled ? "Zoom Active" : "Overview"}</span>
          </button>

          {/* Captions Toggle */}
          <button
            type="button"
            onClick={onToggleCaptions}
            data-testid="control-toggle-captions"
            aria-pressed={isCaptionsEnabled}
            aria-label={isCaptionsEnabled ? "Hide captions" : "Show captions"}
            title="Toggle captions (C)"
            className={`rounded-md px-2 py-1 text-xs font-bold transition-colors ${
              isCaptionsEnabled
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "border border-zinc-200 bg-zinc-50 text-zinc-500 hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400"
            }`}
          >
            CC
          </button>
        </div>
      </div>
    </div>
  );
}
