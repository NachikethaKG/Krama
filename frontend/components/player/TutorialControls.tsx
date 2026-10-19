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
  isMuted?: boolean;
  isFirstStep: boolean;
  isLastStep: boolean;
  sceneProgress: number;
  overallProgress: number;
  onPlay?: () => void;
  onPause?: () => void;
  onTogglePlay: () => void;
  onNextStep: () => void;
  onPrevStep: () => void;
  onReplayCurrentStep: () => void;
  onToggleZoom: () => void;
  onToggleCaptions: () => void;
  onToggleMute?: () => void;
  onSeek?: (timeMs: number) => void;
  onToggleDrawer?: () => void;
  isDrawerOpen?: boolean;
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
  isMuted = false,
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
  onToggleMute,
  onSeek,
  onToggleDrawer,
  isDrawerOpen = false,
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

  const handleKeyDownSlider = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (!onSeek) return;
    if (e.key === "ArrowRight") {
      e.preventDefault();
      onSeek(Math.min(currentDurationMs, currentTimeMs + 500));
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      onSeek(Math.max(0, currentTimeMs - 500));
    }
  };

  return (
    <div
      data-testid="tutorial-controls"
      role="region"
      aria-label="Tutorial playback controls"
      className={`flex flex-col gap-2 rounded-lg border border-zinc-200 bg-white p-3 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 ${className}`}
    >
      {/* Timeline Scrubbing Bar */}
      <div
        tabIndex={0}
        onKeyDown={handleKeyDownSlider}
        onClick={handleProgressBarClick}
        role="slider"
        aria-valuenow={Math.round(sceneProgress * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Scene playback progress"
        aria-valuetext={`Step ${currentSceneIndex + 1} of ${totalScenes}: ${currentScene?.title || ""}`}
        className="group relative h-2.5 w-full cursor-pointer rounded-full bg-zinc-200 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:bg-zinc-800 dark:focus-visible:ring-offset-zinc-950"
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
              style={{
                width: `${(scene.duration_ms / (spec.total_duration_ms || 1)) * 100}%`,
              }}
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
            title="Previous step (ArrowLeft or J)"
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-md p-2.5 text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:focus-visible:ring-offset-zinc-950"
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
            title={isPlaying ? "Pause (Space or K)" : "Play (Space or K)"}
            className="flex h-11 w-11 min-h-[44px] min-w-[44px] items-center justify-center rounded-full bg-indigo-600 text-white shadow hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:bg-indigo-500 dark:hover:bg-indigo-600 dark:focus-visible:ring-offset-zinc-950"
          >
            {isPlaying ? (
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 5h4v14H6zm8 0h4v14h-4z" />
              </svg>
            ) : (
              <svg
                className="h-5 w-5 translate-x-0.5"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
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
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-md p-2.5 text-zinc-700 hover:bg-zinc-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:focus-visible:ring-offset-zinc-950"
          >
            <svg
              className="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          </button>

          {/* Next Step */}
          <button
            type="button"
            onClick={onNextStep}
            disabled={isLastStep}
            data-testid="control-next-step"
            aria-label="Next step"
            title="Next step (ArrowRight or L)"
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-md p-2.5 text-zinc-700 hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-40 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:focus-visible:ring-offset-zinc-950"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
            </svg>
          </button>

          {/* Step & Time display */}
          <div className="ml-1 sm:ml-2 flex items-center gap-1.5 text-xs font-medium text-zinc-600 dark:text-zinc-400">
            <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
              Step {currentSceneIndex + 1} of {totalScenes}
            </span>
            <span className="hidden sm:inline">
              {formatTime(currentTimeMs)} / {formatTime(currentDurationMs)}
            </span>
            <span className="hidden sm:inline text-[11px] text-zinc-400 font-mono">
              ({Math.round(overallProgress * 100)}%)
            </span>
          </div>
        </div>

        {/* Right: Audio Narration, Zoom & Captions Toggles */}
        <div className="flex items-center gap-1 sm:gap-1.5">
          {/* Audio Narration Mute / Unmute Toggle */}
          {onToggleMute && (
            <button
              type="button"
              onClick={onToggleMute}
              data-testid="control-toggle-mute"
              aria-pressed={!isMuted}
              aria-label={isMuted ? "Unmute narration" : "Mute narration"}
              title={`Toggle narration (M) - Currently ${isMuted ? "Muted" : "Active"}`}
              className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-md p-2.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-zinc-950 ${
                !isMuted
                  ? "bg-indigo-50 text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:text-indigo-300 dark:hover:bg-indigo-900"
                  : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
              }`}
            >
              {isMuted ? (
                // Muted Speaker Icon
                <svg
                  className="h-5 w-5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M11 5L6 9H2v6h4l5 4V5z"
                  />
                  <line
                    x1="23"
                    y1="9"
                    x2="17"
                    y2="15"
                    strokeLinecap="round"
                  />
                  <line
                    x1="17"
                    y1="9"
                    x2="23"
                    y2="15"
                    strokeLinecap="round"
                  />
                </svg>
              ) : (
                // Active Speaker Icon
                <svg
                  className="h-5 w-5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M11 5L6 9H2v6h4l5 4V5z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M15.54 8.46a5 5 0 0 1 0 7.07m3.53-10.6a10 10 0 0 1 0 14.14"
                  />
                </svg>
              )}
            </button>
          )}

          {/* Zoom Toggle */}
          <button
            type="button"
            onClick={onToggleZoom}
            data-testid="control-toggle-zoom"
            aria-pressed={isZoomEnabled}
            aria-label={isZoomEnabled ? "Disable auto-zoom" : "Enable auto-zoom"}
            title={`Toggle zoom (Z) - Currently ${isZoomEnabled ? "Auto-Zoom" : "Overview (1.0x)"}`}
            className={`flex min-h-[44px] items-center gap-1.5 rounded-md px-3 py-2.5 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-zinc-950 ${
              isZoomEnabled
                ? "bg-indigo-50 text-indigo-700 border border-indigo-200 dark:bg-indigo-950/50 dark:text-indigo-300 dark:border-indigo-800"
                : "border border-zinc-200 bg-zinc-50 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800"
            }`}
          >
            <svg
              className="h-4 w-4 shrink-0"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
              {isZoomEnabled ? (
                <line x1="8" y1="11" x2="14" y2="11" />
              ) : (
                <>
                  <line x1="11" y1="8" x2="11" y2="14" />
                  <line x1="8" y1="11" x2="14" y2="11" />
                </>
              )}
            </svg>
            <span className="hidden sm:inline">
              {isZoomEnabled ? "Zoom Active" : "Overview"}
            </span>
          </button>

          {/* Captions Toggle */}
          <button
            type="button"
            onClick={onToggleCaptions}
            data-testid="control-toggle-captions"
            aria-pressed={isCaptionsEnabled}
            aria-label={isCaptionsEnabled ? "Hide captions" : "Show captions"}
            title="Toggle captions (C)"
            className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-md px-3 py-2.5 text-xs font-bold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-zinc-950 ${
              isCaptionsEnabled
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "border border-zinc-200 bg-zinc-50 text-zinc-500 hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400"
            }`}
          >
            CC
          </button>

          {/* Mobile Step Drawer Toggle (only visible on small screens < 1024px) */}
          {onToggleDrawer && (
            <button
              type="button"
              onClick={onToggleDrawer}
              data-testid="mobile-step-drawer-toggle"
              aria-expanded={isDrawerOpen}
              aria-label={isDrawerOpen ? "Close step list" : "Open step list"}
              title="Toggle step list"
              className="lg:hidden flex min-h-[44px] min-w-[44px] items-center justify-center rounded-md border border-zinc-200 bg-zinc-50 p-2.5 text-xs font-medium text-zinc-700 hover:bg-zinc-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:focus-visible:ring-offset-zinc-950"
            >
              <svg
                className="h-5 w-5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 6h16M4 12h16M4 18h7"
                />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
