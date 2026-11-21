"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import type { TutorialSpec } from "@krama/tutorial-compiler";
import type { eventWithTime } from "@rrweb/types";
import type { TutorialFreshnessStatus } from "@/types/tutorial";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { Clapperboard, Eye, Film, History, Share2, Timer, Zap } from "lucide-react";
import { TutorialStatusBadge } from "@/components/tutorials/TutorialStatusBadge";
import { VersionHistoryPanel } from "@/components/versions/VersionHistoryPanel";
import { ShareTutorialModal } from "@/components/share";
import { ExportVideoModal } from "@/components/export";
import { DoItForMeModal } from "@/components/do-it";
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
  status?: TutorialFreshnessStatus;
  workflowId?: string;
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
  status,
  workflowId,
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
  const t = useTranslations("player");
  const narratingRef = useRef(false);
  const [isVersionHistoryOpen, setIsVersionHistoryOpen] = useState(false);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [isDoItModalOpen, setIsDoItModalOpen] = useState(false);
  const freshnessStatus: TutorialFreshnessStatus =
    status ?? (spec as unknown as { status?: TutorialFreshnessStatus }).status ?? "verified";
  const effectiveWorkflowId = workflowId ?? spec.workflow_id;
  // Only a verified workflow can run for the user (P2); the dialog explains any other refusal.
  const canDoIt = freshnessStatus === "verified" || freshnessStatus === "auto-updated";
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
    ? t("player.announcement", {
        seq: currentScene.step_seq,
        total: player.totalScenes,
        text: currentScene.caption?.text || currentScene.title || t("player.stepN", { seq: currentScene.step_seq }),
      })
    : "";

  return (
    <section
      ref={playerContainerRef}
      role="region"
      aria-label={t("player.region")}
      aria-roledescription={t("player.roleDescription")}
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
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="kr-chip">
              <Clapperboard aria-hidden="true" className="size-3.5" />
              {t("player.learn")}
            </span>
            <TutorialStatusBadge
              status={freshnessStatus}
              onInspectDiff={() => setIsVersionHistoryOpen(true)}
            />
            {readOnly ? (
              <span data-testid="readonly-badge" className="kr-chip kr-run">
                <Eye aria-hidden="true" className="size-3.5" />
                {t("player.readOnly")}
              </span>
            ) : null}
          </div>

          {!readOnly && effectiveWorkflowId && canDoIt && (
            <button
              type="button"
              data-testid="do-it-for-me-button"
              onClick={() => setIsDoItModalOpen(true)}
              className="kr-chip cursor-pointer transition-colors hover:text-white"
            >
              <Zap className="size-3.5 text-approve" aria-hidden="true" />
              <span>{t("player.doItForMe")}</span>
            </button>
          )}

          {!readOnly && effectiveWorkflowId && (
            <button
              type="button"
              data-testid="export-video-button"
              onClick={() => setIsExportModalOpen(true)}
              className="kr-chip cursor-pointer transition-colors hover:text-white"
            >
              <Film className="size-3.5 text-accent" aria-hidden="true" />
              <span>{t("player.exportMp4")}</span>
            </button>
          )}

          {!readOnly && effectiveWorkflowId && (
            <button
              type="button"
              data-testid="share-tutorial-button"
              onClick={() => setIsShareModalOpen(true)}
              className="kr-chip cursor-pointer transition-colors hover:text-white"
            >
              <Share2 className="size-3.5 text-approve" aria-hidden="true" />
              <span>{t("player.share")}</span>
            </button>
          )}

          {effectiveWorkflowId && (
            <button
              type="button"
              data-testid="open-version-history-btn"
              onClick={() => setIsVersionHistoryOpen(true)}
              className="kr-chip cursor-pointer transition-colors hover:text-white"
            >
              <History className="size-3.5 text-learn" aria-hidden="true" />
              <span>{t("player.versionHistory")}</span>
            </button>
          )}
        </div>
        <h1 className="kr-display text-3xl font-extrabold leading-tight text-white sm:text-4xl">
          {spec.title}
        </h1>
        {spec.description && spec.description.trim() !== spec.title.trim() && (
          <p className="max-w-3xl text-sm text-ink-300">{spec.description}</p>
        )}
        <p data-testid="tutorial-summary" className="flex items-center gap-1.5 font-mono text-xs text-learn">
          <Timer aria-hidden="true" className="size-3.5" />
          {t("player.summary", {
            count: spec.scenes.length,
            seconds: Math.max(1, Math.round((spec.total_duration_ms || 1) / 1000)),
          })}
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
                    {currentScene.title || t("player.stepN", { seq: currentScene.step_seq })}
                  </span>
                  <span className="kr-chip font-mono uppercase">
                    {currentScene.action.type}
                  </span>
                  {currentScene.sensitive && (
                    <span className="kr-chip kr-plan">
                      {t("player.sensitive")}
                    </span>
                  )}
                </div>

                <span className="font-mono text-xs text-ink-400">
                  {t("player.duration", { seconds: (currentScene.duration_ms / 1000).toFixed(1) })}
                </span>
              </div>

              {/* Instruction Text with Copyable Action */}
              <div className="mt-3 space-y-3">
                <div>
                  <h3 className="text-[11px] font-bold uppercase tracking-[0.2em]" style={{ color: "var(--kr-tone)" }}>
                    {t("player.instruction")}
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
                      {t("player.inputValue")}
                    </h3>
                    <CopyableText
                      text={actionValue}
                      label={t("player.valueLabel")}
                      code={true}
                    />
                  </div>
                )}

                {/* Copy full instruction text */}
                {currentScene.caption?.text && (
                  <div className="pt-1">
                    <CopyableText
                      text={currentScene.caption.text}
                      label={t("player.instruction")}
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
          aria-label={t("player.stepsDrawer")}
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

      {/* Version History Drawer / Modal */}
      {isVersionHistoryOpen && (
        <div
          data-testid="version-history-drawer"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
        >
          <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl dark:bg-zinc-950 overflow-hidden border border-zinc-200 dark:border-zinc-800">
            <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
              <h4 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                {t("player.versionHistoryTitle")}
              </h4>
              <button
                type="button"
                data-testid="close-version-history-btn"
                onClick={() => setIsVersionHistoryOpen(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                aria-label={t("player.closeVersionHistory")}
              >
                <svg className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <VersionHistoryPanel
                workflowId={effectiveWorkflowId}
                readOnly={readOnly}
              />
            </div>
          </div>
        </div>
      )}

      {!readOnly && effectiveWorkflowId && (
        <ShareTutorialModal
          isOpen={isShareModalOpen}
          onClose={() => setIsShareModalOpen(false)}
          workflowId={effectiveWorkflowId}
          tutorialTitle={spec.title}
        />
      )}

      {!readOnly && effectiveWorkflowId && canDoIt && (
        <DoItForMeModal
          isOpen={isDoItModalOpen}
          onClose={() => setIsDoItModalOpen(false)}
          workflowId={effectiveWorkflowId}
          tutorialTitle={spec.title}
        />
      )}

      {!readOnly && effectiveWorkflowId && (
        <ExportVideoModal
          isOpen={isExportModalOpen}
          onClose={() => setIsExportModalOpen(false)}
          workflowId={effectiveWorkflowId}
          tutorialTitle={spec.title}
          stepCount={spec.scenes.length}
        />
      )}
    </section>
  );
}
