"use client";

import { useEffect, useRef, useState } from "react";
import {
  computeClampedOffsets,
  evaluateBezierPoint,
  type Point,
  type Scene,
  type TutorialSpec,
  type WordTiming,
} from "@krama/tutorial-compiler";
import type { eventWithTime } from "@rrweb/types";
import { useTranslations } from "next-intl";
import { usePrefersReducedMotion } from "@/hooks/usePrefersReducedMotion";
import { RecordedPage } from "./RecordedPage";

export interface TutorialStageProps {
  spec: TutorialSpec;
  currentScene: Scene | undefined;
  currentTimeMs: number;
  isZoomEnabled: boolean;
  isCaptionsEnabled: boolean;
  isReducedMotion?: boolean;
  activeWordIndex?: number | null;
  className?: string;
  /** The workflow's rrweb recording. With it, the stage shows the real page instead of the wireframe. */
  recording?: eventWithTime[] | null;
}

export function TutorialStage({
  spec,
  currentScene,
  currentTimeMs,
  isZoomEnabled,
  isCaptionsEnabled,
  isReducedMotion,
  activeWordIndex,
  className = "",
  recording = null,
}: TutorialStageProps) {
  const t = useTranslations("player");
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(0);

  const systemReducedMotion = usePrefersReducedMotion();
  const effectiveReducedMotion = isReducedMotion ?? systemReducedMotion;

  const viewport = spec.viewport ?? { width: 1280, height: 800 };

  // Observe container size for responsive scaling
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Initial measurement
    setContainerWidth(el.clientWidth || viewport.width);

    if (typeof ResizeObserver === "undefined") {
      return;
    }

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setContainerWidth(entry.contentRect.width);
        }
      }
    });

    ro.observe(el);
    return () => ro.disconnect();
  }, [viewport.width]);

  const stageScale = containerWidth > 0 ? containerWidth / viewport.width : 1;

  // Over the real page, page coordinates (bbox, cursor, camera) become viewport coordinates by subtracting the
  // window scroll the step ran at (#72). The wireframe backdrop never scrolls.
  const showRecording = Boolean(recording && recording.length > 1 && currentScene);
  const scroll = showRecording && currentScene?.scroll ? currentScene.scroll : { x: 0, y: 0 };
  const onScreen = (p: Point): Point => ({ x: p.x - scroll.x, y: p.y - scroll.y });
  // Before the click: the page the learner acts on. After it (or for a step without an element): the result.
  const clickMs = currentScene?.cursor?.click_ms;
  const showResult = clickMs === null || clickMs === undefined || currentTimeMs >= clickMs;
  const recordingOffsetMs = currentScene
    ? showResult
      ? currentScene.recording.end_ms
      : currentScene.recording.start_ms
    : 0;

  // Camera calculations (reduced motion disables zoom transforms completely)
  let cameraTransform = "none";
  let cameraTransition = "none";

  if (!effectiveReducedMotion && isZoomEnabled && currentScene?.camera) {
    const { panX, panY } = computeClampedOffsets(
      onScreen(currentScene.camera.center),
      currentScene.camera.scale,
      viewport,
    );
    cameraTransform = `translate(${panX}px, ${panY}px) scale(${currentScene.camera.scale})`;
    cameraTransition = `transform ${currentScene.camera.pan_duration_ms ?? 450}ms ${
      currentScene.camera.easing ?? "cubic-bezier(0.22, 1, 0.36, 1)"
    }`;
  }

  // Cursor position calculation
  let cursorPos: Point | null = null;
  if (currentScene?.cursor?.path && currentScene.cursor.path.length === 4) {
    const { path, start_ms, end_ms } = currentScene.cursor;
    if (effectiveReducedMotion) {
      // Reduced motion: snap cursor instantly to target without Bezier interpolation
      cursorPos = onScreen(currentTimeMs >= start_ms ? path[3] : path[0]);
    } else if (currentTimeMs <= start_ms) {
      cursorPos = onScreen(path[0]);
    } else if (currentTimeMs >= end_ms) {
      cursorPos = onScreen(path[3]);
    } else {
      const duration = Math.max(1, end_ms - start_ms);
      const t = (currentTimeMs - start_ms) / duration;
      cursorPos = onScreen(evaluateBezierPoint(path as [Point, Point, Point, Point], t));
    }
  }

  // Click ripple calculation
  let rippleActive = false;
  let rippleRadius = 24;
  let rippleOpacity = 0;
  let rippleCenter: Point | null = null;

  if (
    currentScene?.cursor?.ripple &&
    currentScene.cursor.click_ms !== null &&
    currentScene.cursor.click_ms !== undefined &&
    currentScene.cursor.path &&
    currentScene.cursor.path.length === 4
  ) {
    const clickMs = currentScene.cursor.click_ms;
    const rippleDuration = effectiveReducedMotion ? 200 : 600;
    if (currentTimeMs >= clickMs && currentTimeMs < clickMs + rippleDuration) {
      rippleActive = true;
      const t = (currentTimeMs - clickMs) / rippleDuration;
      const maxRadius = currentScene.cursor.ripple.radius ?? 24;
      rippleRadius = effectiveReducedMotion
        ? maxRadius
        : Math.max(4, maxRadius * Math.sin((t * Math.PI) / 2));
      rippleOpacity = Math.max(0, 1 - t);
      rippleCenter = onScreen(currentScene.cursor.path[3]);
    }
  }

  // Highlight calculations
  const highlight = currentScene?.highlight;
  // After a click or key press the stage shows the result, often a new page: the element the box pointed at
  // is gone there, so the box would float over unrelated content (#320 follow-up). Typing keeps its box.
  const resultHidesTarget =
    showRecording &&
    showResult &&
    clickMs !== null &&
    clickMs !== undefined &&
    (currentScene?.action?.type === "click" || currentScene?.action?.type === "press");
  const highlightBbox = resultHidesTarget ? undefined : highlight?.bbox;
  const highlightPadding = highlight?.padding ?? 8;
  const highlightColor = highlight?.color ?? "#4f46e5";
  const highlightStyle = highlight?.style ?? "pulsing_ring";
  const isPulsing =
    !effectiveReducedMotion && highlightStyle === "pulsing_ring";

  return (
    <div
      ref={containerRef}
      data-testid="tutorial-stage-container"
      className={`relative w-full overflow-hidden rounded-3xl border border-learn/50 bg-ink-950 select-none ${className}`}
      style={{
        aspectRatio: `${viewport.width} / ${viewport.height}`,
        boxShadow:
          "0 0 0 1px rgb(0 0 0 / 0.4), 0 0 60px -12px var(--learn), 0 30px 80px -30px var(--ask)",
      }}
    >
      {/* Scaled Canvas Container */}
      <div
        className="absolute top-0 left-0 origin-top-left"
        style={{
          width: `${viewport.width}px`,
          height: `${viewport.height}px`,
          transform: `scale(${stageScale})`,
        }}
      >
        {/* Camera Pan & Zoom Layer */}
        <div
          data-testid="camera-viewport"
          className="absolute inset-0 origin-top-left"
          style={{
            transform: cameraTransform,
            transition: cameraTransition,
          }}
        >
          {showRecording && recording ? (
            <RecordedPage
              events={recording}
              timeOffsetMs={recordingOffsetMs}
              viewport={viewport}
              scroll={scroll}
            />
          ) : (
          <>
          {/* Mock Browser & Page Content Backdrop */}
          <div className="absolute inset-0 flex flex-col bg-ink-900 text-white">
            {/* Browser Chrome Header */}
            <div className="flex h-10 w-full items-center gap-3 border-b border-white/10 bg-ink-950 px-4">
              <div className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-full bg-danger" />
                <div className="h-3 w-3 rounded-full bg-plan" />
                <div className="h-3 w-3 rounded-full bg-verify" />
              </div>
              <div className="flex flex-1 items-center justify-center">
                <div className="flex h-6 w-full max-w-md items-center justify-between rounded-full border border-white/10 bg-white/5 px-3 font-mono text-xs text-ink-300">
                  <span className="truncate">
                    {t("stage.fakeUrl", { slug: spec.title.toLowerCase().replace(/\s+/g, "-") })}
                  </span>
                  <span className="text-[10px] text-verify">{t("stage.secure")}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-ink-300">
                <span className="font-bold text-learn">{t("stage.brand")}</span>
              </div>
            </div>

            {/* Simulated Page Body */}
            <div className="relative flex-1 overflow-hidden bg-gradient-to-br from-ink-900 via-ink-850 to-ink-800 p-8">
              {/* Decorative Mock Application Elements */}
              <div className="mx-auto max-w-4xl space-y-6">
                <div className="flex items-center justify-between border-b border-white/10 pb-4">
                  <div>
                    <h1 className="text-xl font-bold tracking-tight text-white">
                      {spec.title}
                    </h1>
                    <p className="text-xs text-ink-300 mt-1">
                      {spec.description || t("stage.descriptionFallback")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-24 rounded-lg border border-ask/50 bg-ask/25 flex items-center justify-center text-xs font-bold text-ask">
                      {t("stage.newButton")}
                    </div>
                  </div>
                </div>

                {/* Simulated Content Grid */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="h-28 rounded-lg border border-white/10 bg-white/[0.03] p-4">
                    <div className="h-4 w-20 rounded bg-ask/60" />
                    <div className="mt-3 h-3 w-full rounded bg-white/10" />
                    <div className="mt-2 h-3 w-3/4 rounded bg-white/5" />
                  </div>
                  <div className="h-28 rounded-lg border border-white/10 bg-white/[0.03] p-4">
                    <div className="h-4 w-24 rounded bg-run/60" />
                    <div className="mt-3 h-3 w-full rounded bg-white/10" />
                    <div className="mt-2 h-3 w-2/3 rounded bg-white/5" />
                  </div>
                  <div className="h-28 rounded-lg border border-white/10 bg-white/[0.03] p-4">
                    <div className="h-4 w-16 rounded bg-plan/60" />
                    <div className="mt-3 h-3 w-full rounded bg-white/10" />
                    <div className="mt-2 h-3 w-4/5 rounded bg-white/5" />
                  </div>
                </div>

                {/* Form or Table Wireframe */}
                <div className="rounded-lg border border-white/10 bg-white/[0.04] p-6 space-y-4">
                  <div className="h-5 w-48 rounded bg-approve/50" />
                  <div className="h-10 w-full rounded border border-white/10 bg-ink-950/50" />
                  <div className="h-20 w-full rounded border border-white/10 bg-ink-950/50" />
                  <div className="flex justify-end gap-2 pt-2">
                    <div className="h-8 w-20 rounded border border-white/15 bg-white/10" />
                    <div className="h-8 w-28 rounded-lg bg-verify/80" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          </>
          )}

          {/* Target Highlight Overlay */}
          {highlightBbox && highlightBbox.length === 4 && (
            <div
              data-testid="target-highlight"
              className={`absolute pointer-events-none rounded transition-all duration-300 ${
                isPulsing ? "animate-pulse" : ""
              }`}
              style={{
                left: `${highlightBbox[0] - scroll.x - highlightPadding}px`,
                top: `${highlightBbox[1] - scroll.y - highlightPadding}px`,
                width: `${highlightBbox[2] + highlightPadding * 2}px`,
                height: `${highlightBbox[3] + highlightPadding * 2}px`,
                border: `2px solid ${highlightColor}`,
                boxShadow: isPulsing
                  ? `0 0 0 4px ${highlightColor}40, 0 0 16px ${highlightColor}80`
                  : `0 0 4px ${highlightColor}40`,
                backgroundColor: `${highlightColor}10`,
              }}
            />
          )}

          {/* Click Ripple Effect */}
          {rippleActive && rippleCenter && (
            <div
              data-testid="click-ripple"
              className="absolute pointer-events-none rounded-full"
              style={{
                left: `${rippleCenter.x - rippleRadius}px`,
                top: `${rippleCenter.y - rippleRadius}px`,
                width: `${rippleRadius * 2}px`,
                height: `${rippleRadius * 2}px`,
                border: `2px solid ${currentScene?.cursor?.ripple?.color || "rgba(255, 122, 26, 0.85)"}`,
                backgroundColor: `${currentScene?.cursor?.ripple?.color || "rgba(255, 122, 26, 0.3)"}`,
                opacity: rippleOpacity,
                transition: effectiveReducedMotion
                  ? "none"
                  : "opacity 100ms ease-out",
              }}
            />
          )}

          {/* Animated Cursor */}
          {cursorPos && (
            <div
              data-testid="tutorial-cursor"
              className="absolute pointer-events-none z-30"
              style={{
                left: `${cursorPos.x}px`,
                top: `${cursorPos.y}px`,
                transform: "translate(-2px, -2px)",
                transition: effectiveReducedMotion
                  ? "none"
                  : "transform 75ms linear",
              }}
            >
              {/* Realistic Pointer Cursor */}
              <svg
                width="28"
                height="28"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="drop-shadow-[0_0_8px_rgba(255,79,216,0.75)]"
              >
                <path
                  d="M4 3L11.5 21L14.5 13.5L22 10.5L4 3Z"
                  fill="#ffffff"
                  stroke="#07060f"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
              </svg>
            </div>
          )}
        </div>
      </div>

      {/* Synchronized Caption Banner */}
      {isCaptionsEnabled && currentScene?.caption?.text && (
        <div
          data-testid="tutorial-caption"
          className="absolute bottom-4 left-1/2 z-40 max-w-[90%] -translate-x-1/2 rounded-2xl border border-learn/60 bg-ink-950/85 px-5 py-3 text-center text-sm font-semibold text-white shadow-[0_0_40px_-10px_var(--learn)] backdrop-blur-md transition-all sm:text-base"
        >
          {currentScene.caption.words && currentScene.caption.words.length > 0 ? (
            <div className="flex flex-wrap items-center justify-center gap-x-1.5 gap-y-0.5">
              {currentScene.caption.words.map((wordObj: WordTiming, wIdx: number) => {
                const hasSpeechSync =
                  activeWordIndex !== null && activeWordIndex !== undefined;
                const isWordActive = hasSpeechSync
                  ? wIdx === activeWordIndex
                  : currentTimeMs >= wordObj.start_ms &&
                    currentTimeMs < wordObj.end_ms;
                const isWordSpoken = hasSpeechSync
                  ? wIdx < activeWordIndex
                  : currentTimeMs >= wordObj.end_ms;

                return (
                  <span key={`${wordObj.word}-${wIdx}`}>
                    <span
                      className={`transition-colors duration-100 ${
                        isWordActive
                          ? "font-extrabold text-learn underline decoration-ask decoration-2 underline-offset-4 [text-shadow:0_0_14px_var(--learn)]"
                          : isWordSpoken
                            ? "text-white font-bold"
                            : "text-ink-400"
                      }`}
                    >
                      {wordObj.word}
                    </span>
                    {wIdx < (currentScene.caption.words?.length ?? 0) - 1 ? " " : ""}
                  </span>
                );
              })}
            </div>
          ) : (
            <span>{currentScene.caption.text}</span>
          )}
        </div>
      )}
    </div>
  );
}
