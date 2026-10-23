"use client";

import { useRef, useState } from "react";
import type { TutorialSpec } from "@krama/tutorial-compiler";
import type { eventWithTime } from "@rrweb/types";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { CopyableText } from "./CopyableText";
import { TutorialControls } from "./TutorialControls";
import { TutorialStage } from "./TutorialStage";
import { TutorialStepList } from "./TutorialStepList";
import { usePlayerKeyboardShortcuts } from "./usePlayerKeyboardShortcuts";
import { useStepNarration } from "./useStepNarration";
import { useTutorialPlayer } from "./useTutorialPlayer";

export interface TutorialPlayerProps {
  spec: TutorialSpec;
  autoPlay?: boolean;
  initialStep?: number;
  initialZoom?: boolean;
  initialCaptions?: boolean;
  initialMuted?: boolean;
  isReducedMotion?: boolean;
  className?: string;
  onComplete?: () => void;
  /** The workflow's rrweb recording: the stage then shows the real page instead of the wireframe. */
  recording?: eventWithTime[] | null;
  /** When true, edit, delete, re-run, or sharing management controls are omitted. */
  readOnly?: boolean;
}

export function TutorialPlayer({
  spec,
  autoPlay = false,
  initialStep = 0,
  initialZoom = false,
  initialCaptions = true,
  initialMuted = false,
  isReducedMotion,
  className = "",
  onComplete,
  recording = null,
  readOnly = false,
}: TutorialPlayerProps) {
  // The narration sets this while it talks; the player holds the step's end until it's done (#83).
  const narratingRef = useRef(false);
  const player = useTutorialPlayer({
    spec,
    autoPlay,
    initialSceneIndex: initialStep,
    initialZoom,
    initialCaptions,
    onComplete,
    holdSceneEndRef: narratingRef,
  });

  const playerContainerRef = useRef<HTMLDivElement>(null);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);

  const systemReducedMotion = usePrefersReducedMotion();
  const effectiveReducedMotion = isReducedMotion ?? systemReducedMotion;

  const currentScene = player.currentScene;
  const actionValue = currentScene?.action?.value;

  // Web Speech API Narration with onboundary word sync
  const narration = useStepNarration({
    text: currentScene?.caption?.text,
    isPlaying: player.isPlaying,
    currentStepIndex: player.currentSceneIndex,
    initialMuted,
    narratingRef,
  });

  // WCAG Keyboard Navigation Shortcuts
  usePlayerKeyboardShortcuts({
    onTogglePlay: player.togglePlay,
    onNextStep: player.nextStep,
    onPrevStep: player.prevStep,
    onReplayCurrentStep: player.replayCurrentStep,
    onToggleZoom: player.toggleZoom,
    onToggleCaptions: player.toggleCaptions,
    onToggleMute: narration.toggleMute,
    isEnabled: true,
  });

  // Screen Reader polite live region text derived synchronously from active scene
  const announcement = currentScene
    ? `Step ${currentScene.step_seq} of ${player.totalScenes}: ${
        currentScene.caption?.text || currentScene.title || `Step ${currentScene.step_seq}`
      }`
    : "";

  return (
    <section
      ref={playerContainerRef}
      role="region"
      aria-label="Interactive Tutorial Player"
      aria-roledescription="interactive video tutorial"
      data-testid="tutorial-player-root"
      className={`mx-auto flex w-full max-w-7xl flex-col gap-6 overflow-x-hidden p-3 sm:p-4 md:p-6 ${className}`}
    >
      {/* Dedicated Screen Reader Live Region */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        data-testid="screen-reader-announcer"
        className="sr-only"
      >
        {announcement}
      </div>

      {/* Tutorial Header */}
      <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between border-b border-zinc-200 pb-4 dark:border-zinc-800">
        <div>
          <div className="flex items-center gap-2">
            {readOnly ? (
              <span
                data-testid="readonly-badge"
                className="rounded bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-700 ring-1 ring-inset ring-zinc-500/20 dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700"
              >
                Read-Only
              </span>
            ) : (
              <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                Interactive Tutorial
              </span>
            )}
            <span className="text-xs text-zinc-500 dark:text-zinc-400">
              v{spec.version}
            </span>
          </div>
          <h1 className="mt-1 text-xl sm:text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            {spec.title}
          </h1>
          {spec.description && (
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              {spec.description}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <div className="flex flex-col items-start md:items-end text-xs text-zinc-500 dark:text-zinc-400">
            <span>
              Viewport: {spec.viewport.width} × {spec.viewport.height}
            </span>
            <span>
              Duration: {((spec.total_duration_ms || 1) / 1000).toFixed(1)}s
            </span>
          </div>
        </div>
      </header>

      {/* Main Grid: Stage & Controls (Left/Center) + Step List Sidebar (Right) */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Stage and Controls Section (2 cols on large screen) */}
        <div className="flex flex-col gap-4 lg:col-span-2">
          {/* Visual Replay Stage */}
          <TutorialStage
            spec={spec}
            currentScene={currentScene}
            currentTimeMs={player.currentTimeMs}
            isZoomEnabled={player.isZoomEnabled}
            isCaptionsEnabled={player.isCaptionsEnabled}
            isReducedMotion={effectiveReducedMotion}
            activeWordIndex={narration.activeWordIndex}
            recording={recording}
          />

          {/* Controls Bar */}
          <TutorialControls
            spec={spec}
            currentSceneIndex={player.currentSceneIndex}
            currentScene={currentScene}
            currentTimeMs={player.currentTimeMs}
            isPlaying={player.isPlaying}
            isZoomEnabled={player.isZoomEnabled}
            isCaptionsEnabled={player.isCaptionsEnabled}
            isMuted={narration.isMuted}
            isFirstStep={player.isFirstStep}
            isLastStep={player.isLastStep}
            sceneProgress={player.sceneProgress}
            overallProgress={player.overallProgress}
            onPlay={player.play}
            onPause={player.pause}
            onTogglePlay={player.togglePlay}
            onNextStep={player.nextStep}
            onPrevStep={player.prevStep}
            onReplayCurrentStep={player.replayCurrentStep}
            onToggleZoom={player.toggleZoom}
            onToggleCaptions={player.toggleCaptions}
            onToggleMute={narration.toggleMute}
            onSeek={player.seekTo}
            onToggleDrawer={() => setIsMobileDrawerOpen((prev) => !prev)}
            isDrawerOpen={isMobileDrawerOpen}
          />

          {/* Current Step Instruction & Copyable Card */}
          {currentScene && (
            <div
              data-testid="current-step-card"
              className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
            >
              <div className="flex items-center justify-between gap-2 border-b border-zinc-100 pb-3 dark:border-zinc-900">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white dark:bg-indigo-500">
                    {currentScene.step_seq}
                  </span>
                  <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    {currentScene.title || `Step ${currentScene.step_seq}`}
                  </span>
                  <span className="rounded bg-zinc-100 px-2 py-0.5 text-xs font-mono font-medium text-zinc-700 uppercase dark:bg-zinc-800 dark:text-zinc-300">
                    {currentScene.action.type}
                  </span>
                  {currentScene.sensitive && (
                    <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950/60 dark:text-amber-300">
                      Sensitive
                    </span>
                  )}
                </div>

                <span className="text-xs text-zinc-400">
                  Duration: {(currentScene.duration_ms / 1000).toFixed(1)}s
                </span>
              </div>

              {/* Instruction Text with Copyable Action */}
              <div className="mt-3 space-y-3">
                <div>
                  <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                    Instruction
                  </h3>
                  <p
                    data-testid="instruction-text"
                    className="mt-1 text-sm font-medium text-zinc-800 dark:text-zinc-200"
                  >
                    {currentScene.caption?.text}
                  </p>
                </div>

                {/* Copyable Action Value */}
                {actionValue && (
                  <div>
                    <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-1">
                      Input Value
                    </h3>
                    <CopyableText
                      text={actionValue}
                      label="Value"
                      code={true}
                    />
                  </div>
                )}

                {/* Copy full instruction text */}
                {currentScene.caption?.text && (
                  <div className="pt-1">
                    <CopyableText
                      text={currentScene.caption.text}
                      label="Instruction"
                      code={false}
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Step List Desktop Sidebar (visible on lg screens >= 1024px) */}
        <div className="hidden lg:block lg:col-span-1">
          <TutorialStepList
            spec={spec}
            currentSceneIndex={player.currentSceneIndex}
            onSelectStep={(idx) => {
              player.goToStep(idx);
              player.pause();
            }}
            className="sticky top-6 max-h-[calc(100vh-6rem)]"
          />
        </div>
      </div>

      {/* Mobile Step List Drawer Sheet (for screens < 1024px) */}
      {isMobileDrawerOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Steps drawer"
          data-testid="mobile-step-drawer"
          className="fixed inset-0 z-50 flex flex-col justify-end bg-black/60 backdrop-blur-xs lg:hidden"
          onClick={() => setIsMobileDrawerOpen(false)}
        >
          <div
            className="max-h-[80vh] w-full rounded-t-2xl bg-white p-4 shadow-2xl dark:bg-zinc-950 flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <TutorialStepList
              spec={spec}
              currentSceneIndex={player.currentSceneIndex}
              onSelectStep={(idx) => {
                player.goToStep(idx);
                player.pause();
                setIsMobileDrawerOpen(false);
              }}
              isDrawer={true}
              onClose={() => setIsMobileDrawerOpen(false)}
              className="border-none shadow-none"
            />
          </div>
        </div>
      )}
    </section>
  );
}
