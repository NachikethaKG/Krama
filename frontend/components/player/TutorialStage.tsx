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
      className={`relative w-full overflow-hidden rounded-xl border border-zinc-200 bg-zinc-950 shadow-md select-none dark:border-zinc-800 ${className}`}
      style={{
        aspectRatio: `${viewport.width} / ${viewport.height}`,
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
          <div className="absolute inset-0 bg-zinc-900 text-zinc-100 flex flex-col">
            {/* Browser Chrome Header */}
            <div className="flex h-10 w-full items-center gap-3 border-b border-zinc-800 bg-zinc-950 px-4">
              <div className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-full bg-rose-500/80" />
                <div className="h-3 w-3 rounded-full bg-amber-500/80" />
                <div className="h-3 w-3 rounded-full bg-emerald-500/80" />
              </div>
              <div className="flex flex-1 items-center justify-center">
                <div className="flex h-6 w-full max-w-md items-center justify-between rounded-md border border-zinc-800 bg-zinc-900 px-3 text-xs text-zinc-400">
                  <span className="truncate">
                    https://git.local/{spec.title.toLowerCase().replace(/\s+/g, "-")}
                  </span>
                  <span className="text-[10px] text-zinc-500">🔒 SSL</span>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-zinc-400">
                <span className="font-semibold text-indigo-400">Krama Tutorial</span>
              </div>
            </div>

            {/* Simulated Page Body */}
            <div className="relative flex-1 overflow-hidden bg-zinc-900 p-8">
              {/* Decorative Mock Application Elements */}
              <div className="mx-auto max-w-4xl space-y-6">
                <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
                  <div>
                    <h1 className="text-xl font-bold tracking-tight text-zinc-100">
                      {spec.title}
                    </h1>
                    <p className="text-xs text-zinc-400 mt-1">
                      {spec.description || "Follow the highlighted steps to complete the workflow."}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-24 rounded bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-xs font-medium text-indigo-300">
                      + New
                    </div>
                  </div>
                </div>

                {/* Simulated Content Grid */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="h-28 rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
                    <div className="h-4 w-20 rounded bg-zinc-800" />
                    <div className="mt-3 h-3 w-full rounded bg-zinc-800/60" />
                    <div className="mt-2 h-3 w-3/4 rounded bg-zinc-800/40" />
                  </div>
                  <div className="h-28 rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
                    <div className="h-4 w-24 rounded bg-zinc-800" />
                    <div className="mt-3 h-3 w-full rounded bg-zinc-800/60" />
                    <div className="mt-2 h-3 w-2/3 rounded bg-zinc-800/40" />
                  </div>
                  <div className="h-28 rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
                    <div className="h-4 w-16 rounded bg-zinc-800" />
                    <div className="mt-3 h-3 w-full rounded bg-zinc-800/60" />
                    <div className="mt-2 h-3 w-4/5 rounded bg-zinc-800/40" />
                  </div>
                </div>

                {/* Form or Table Wireframe */}
                <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-6 space-y-4">
                  <div className="h-5 w-48 rounded bg-zinc-800" />
                  <div className="h-10 w-full rounded border border-zinc-800 bg-zinc-900" />
                  <div className="h-20 w-full rounded border border-zinc-800 bg-zinc-900" />
                  <div className="flex justify-end gap-2 pt-2">
                    <div className="h-8 w-20 rounded border border-zinc-700 bg-zinc-800" />
                    <div className="h-8 w-28 rounded bg-indigo-600" />
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
                border: `2px solid ${currentScene?.cursor?.ripple?.color || "rgba(99, 102, 241, 0.8)"}`,
                backgroundColor: `${currentScene?.cursor?.ripple?.color || "rgba(99, 102, 241, 0.3)"}`,
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
                className="drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]"
              >
                <path
                  d="M4 3L11.5 21L14.5 13.5L22 10.5L4 3Z"
                  fill="#0f172a"
                  stroke="#ffffff"
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
          className="absolute bottom-4 left-1/2 -translate-x-1/2 max-w-[90%] rounded-lg border border-zinc-700/80 bg-zinc-950/90 px-4 py-2.5 text-center text-sm font-medium text-white shadow-xl backdrop-blur-md z-40 transition-all"
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
                          ? "font-bold text-indigo-400 underline decoration-indigo-400 decoration-2 underline-offset-4"
                          : isWordSpoken
                            ? "text-zinc-100 font-semibold"
                            : "text-zinc-400"
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
