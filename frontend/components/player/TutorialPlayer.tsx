"use client";

import { useRef, useState } from "react";
import type { TutorialSpec } from "@krama/tutorial-compiler";
import type { eventWithTime } from "@rrweb/types";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { Clapperboard, Eye, Timer } from "lucide-react";
import { CopyableText } from "./CopyableText";
import { stepColor } from "./spectrum";
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

      {/* Tutorial Header: one title, then what the learner needs to know (#318) */}
      <header className="kr-learn relative flex flex-col gap-2 pb-5">
        <div className="flex items-center gap-2">
          <span className="kr-chip">
            <Clapperboard aria-hidden="true" className="size-3.5" />
            Learn
          </span>
          {readOnly ? (
            <span data-testid="readonly-badge" className="kr-chip kr-run">
              <Eye aria-hidden="true" className="size-3.5" />
              Read-Only
            </span>
          ) : null}
        </div>
        <h1 className="kr-display text-3xl font-extrabold leading-tight text-white sm:text-4xl">
          {spec.title}
        </h1>
        {spec.description && spec.description.trim() !== spec.title.trim() && (
          <p className="max-w-3xl text-sm text-ink-300">{spec.description}</p>
        )}
        <p data-testid="tutorial-summary" className="flex items-center gap-1.5 font-mono text-xs text-learn">
          <Timer aria-hidden="true" className="size-3.5" />
          {spec.scenes.length} {spec.scenes.length === 1 ? "step" : "steps"}, each one checked ·{" "}
          {Math.max(1, Math.round((spec.total_duration_ms || 1) / 1000))} s to watch
        </p>
        <div aria-hidden="true" className="kr-rail absolute bottom-0 left-0 w-full opacity-60" />
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
              className="kr-tone-card rounded-3xl p-5"
              style={{ ["--kr-tone" as string]: stepColor(player.currentSceneIndex) }}
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="kr-display flex size-9 items-center justify-center rounded-xl text-base font-extrabold text-oncolor" style={{ background: "var(--kr-tone)", boxShadow: "0 0 22px -4px var(--kr-tone)" }}>
                    {currentScene.step_seq}
                  </span>
                  <span className="kr-display text-lg font-bold text-white">
                    {currentScene.title || `Step ${currentScene.step_seq}`}
                  </span>
                  <span className="kr-chip font-mono uppercase">
                    {currentScene.action.type}
                  </span>
                  {currentScene.sensitive && (
                    <span className="kr-chip kr-plan">
                      Sensitive
                    </span>
                  )}
                </div>

                <span className="font-mono text-xs text-ink-400">
                  Duration: {(currentScene.duration_ms / 1000).toFixed(1)}s
                </span>
              </div>

              {/* Instruction Text with Copyable Action */}
              <div className="mt-3 space-y-3">
                <div>
                  <h3 className="text-[11px] font-bold uppercase tracking-[0.2em]" style={{ color: "var(--kr-tone)" }}>
                    Instruction
                  </h3>
                  <p
                    data-testid="instruction-text"
                    className="mt-1.5 text-lg font-semibold leading-snug text-white"
                  >
                    {currentScene.caption?.text}
                  </p>
                </div>

                {/* Copyable Action Value */}
                {actionValue && (
                  <div>
                    <h3 className="mb-1 text-[11px] font-bold uppercase tracking-[0.2em] text-ink-400">
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
          className="fixed inset-0 z-50 flex flex-col justify-end bg-ink-950/70 backdrop-blur-sm lg:hidden"
          onClick={() => setIsMobileDrawerOpen(false)}
        >
          <div
            className="kr-spectrum-border flex max-h-[80vh] w-full flex-col rounded-t-[2rem] bg-ink-900 p-4 shadow-2xl"
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
