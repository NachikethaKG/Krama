"use client";

import type { Scene, TutorialSpec } from "@krama/tutorial-compiler";
import { ListOrdered, Pause, Play, RotateCcw, SkipBack, SkipForward, Volume2, VolumeX, ZoomIn, ZoomOut } from "lucide-react";
import { stepColor } from "./spectrum";

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

  const ICON_BTN =
    "flex min-h-[44px] min-w-[44px] items-center justify-center rounded-2xl border border-white/10 bg-white/5 p-2.5 text-ink-300 transition-all hover:-translate-y-0.5 hover:border-learn/60 hover:text-white hover:shadow-[0_0_20px_-6px_var(--learn)] disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:translate-y-0";
  const toggle = (on: boolean, color: string) =>
    on
      ? { background: color, borderColor: color, color: "var(--ink-950)", boxShadow: `0 0 22px -4px ${color}` }
      : undefined;
  const sceneColor = stepColor(currentSceneIndex);

  return (
    <div
      data-testid="tutorial-controls"
      role="region"
      aria-label="Tutorial playback controls"
      className={`kr-glass flex flex-col gap-3 rounded-3xl p-3 sm:p-4 ${className}`}
    >
      {/* Timeline Scrubbing Bar: a spectrum rail, one coloured segment per scene */}
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
        className="group relative h-3 w-full cursor-pointer overflow-hidden rounded-full bg-white/10 transition-all hover:h-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-learn focus-visible:ring-offset-2 focus-visible:ring-offset-ink-950"
      >
        <div
          className="h-full rounded-full transition-all duration-75"
          style={{
            width: `${sceneProgress * 100}%`,
            background: `linear-gradient(90deg, ${sceneColor}, var(--learn))`,
            boxShadow: `0 0 16px ${sceneColor}`,
          }}
        />
        {/* Step division markers */}
        <div className="pointer-events-none absolute inset-0 flex">
          {spec.scenes?.map((scene, idx) => (
            <div
              key={scene.id ?? idx}
              style={{
                width: `${(scene.duration_ms / (spec.total_duration_ms || 1)) * 100}%`,
                boxShadow: `inset 0 -2px 0 ${stepColor(idx)}`,
                opacity: idx === currentSceneIndex ? 1 : 0.55,
              }}
              className="h-full border-r-2 border-ink-950/80 last:border-r-0"
            />
          ))}
        </div>
      </div>

      {/* Primary Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* Left: Transport Buttons */}
        <div className="flex items-center gap-1.5">
          {/* Previous Step */}
          <button
            type="button"
            onClick={onPrevStep}
            disabled={isFirstStep && currentTimeMs === 0}
            data-testid="control-prev-step"
            aria-label="Previous step"
            title="Previous step (ArrowLeft or J)"
            className={ICON_BTN}
          >
            <SkipBack aria-hidden="true" className="size-5" />
          </button>

          {/* Play / Pause Toggle */}
          <button
            type="button"
            onClick={onTogglePlay}
            data-testid="control-play-pause"
            aria-label={isPlaying ? "Pause tutorial" : "Play tutorial"}
            title={isPlaying ? "Pause (Space or K)" : "Play (Space or K)"}
            className="kr-btn kr-btn-primary size-14 min-h-[44px] min-w-[44px] !rounded-full"
          >
            {isPlaying ? (
              <Pause aria-hidden="true" className="size-6 fill-current" />
            ) : (
              <Play aria-hidden="true" className="size-6 translate-x-0.5 fill-current" />
            )}
          </button>

          {/* Replay Current Step */}
          <button
            type="button"
            onClick={onReplayCurrentStep}
            data-testid="control-replay-step"
            aria-label="Replay current step"
            title="Replay step (R)"
            className={ICON_BTN}
          >
            <RotateCcw aria-hidden="true" className="size-5" />
          </button>

          {/* Next Step */}
          <button
            type="button"
            onClick={onNextStep}
            disabled={isLastStep}
            data-testid="control-next-step"
            aria-label="Next step"
            title="Next step (ArrowRight or L)"
            className={ICON_BTN}
          >
            <SkipForward aria-hidden="true" className="size-5" />
          </button>

          {/* Step & Time display */}
          <div className="ml-1 flex items-center gap-2 text-xs font-medium text-ink-300 sm:ml-2">
            <span
              className="rounded-full px-2.5 py-1 font-bold text-ink-950"
              style={{ background: sceneColor, boxShadow: `0 0 16px -4px ${sceneColor}` }}
            >
              Step {currentSceneIndex + 1} of {totalScenes}
            </span>
            <span className="hidden font-mono sm:inline">
              {formatTime(currentTimeMs)} / {formatTime(currentDurationMs)}
            </span>
            <span className="hidden font-mono text-[11px] text-learn sm:inline">
              ({Math.round(overallProgress * 100)}%)
            </span>
          </div>
        </div>

        {/* Right: Audio Narration, Zoom & Captions Toggles */}
        <div className="flex items-center gap-1.5">
          {/* Audio Narration Mute / Unmute Toggle */}
          {onToggleMute && (
            <button
              type="button"
              onClick={onToggleMute}
              data-testid="control-toggle-mute"
              aria-pressed={!isMuted}
              aria-label={isMuted ? "Unmute narration" : "Mute narration"}
              title={`Toggle narration (M) - Currently ${isMuted ? "Muted" : "Active"}`}
              className={ICON_BTN}
              style={toggle(!isMuted, "var(--ask)")}
            >
              {isMuted ? (
                <VolumeX aria-hidden="true" className="size-5" />
              ) : (
                <Volume2 aria-hidden="true" className="size-5" />
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
            className={`${ICON_BTN} gap-1.5 px-3 text-xs font-bold`}
            style={toggle(isZoomEnabled, "var(--run)")}
          >
            {isZoomEnabled ? (
              <ZoomOut aria-hidden="true" className="size-4 shrink-0" />
            ) : (
              <ZoomIn aria-hidden="true" className="size-4 shrink-0" />
            )}
            <span className="hidden sm:inline">{isZoomEnabled ? "Zoom Active" : "Overview"}</span>
          </button>

          {/* Captions Toggle */}
          <button
            type="button"
            onClick={onToggleCaptions}
            data-testid="control-toggle-captions"
            aria-pressed={isCaptionsEnabled}
            aria-label={isCaptionsEnabled ? "Hide captions" : "Show captions"}
            title="Toggle captions (C)"
            className={`${ICON_BTN} px-3 text-xs font-extrabold`}
            style={toggle(isCaptionsEnabled, "var(--verify)")}
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
              className={`${ICON_BTN} lg:hidden`}
            >
              <ListOrdered aria-hidden="true" className="size-5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
