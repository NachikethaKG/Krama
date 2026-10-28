"use client";

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import type { Scene, TutorialSpec } from "@krama/tutorial-compiler";

export interface UseTutorialPlayerOptions {
  spec: TutorialSpec;
  autoPlay?: boolean;
  initialSceneIndex?: number;
  initialZoom?: boolean;
  initialCaptions?: boolean;
  playbackSpeed?: number;
  onSceneChange?: (sceneIndex: number) => void;
  onComplete?: () => void;
  /** While true, a scene that reached its end waits instead of moving on (the narration is still talking). */
  holdSceneEndRef?: RefObject<boolean>;
}

/** Longest a scene waits for its narration, in case the browser never reports the end of speech. */
export const MAX_SCENE_HOLD_MS = 15000;

export interface UseTutorialPlayerReturn {
  // State
  currentSceneIndex: number;
  isPlaying: boolean;
  currentTimeMs: number;
  isZoomEnabled: boolean;
  isCaptionsEnabled: boolean;

  // Computed
  currentScene: Scene | undefined;
  totalScenes: number;
  sceneProgress: number; // 0..1
  overallProgress: number; // 0..1
  isFirstStep: boolean;
  isLastStep: boolean;

  // Actions
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  nextStep: () => void;
  prevStep: () => void;
  replayCurrentStep: () => void;
  goToStep: (index: number) => void;
  toggleZoom: () => void;
  toggleCaptions: () => void;
  seekTo: (timeMs: number) => void;
}

export function useTutorialPlayer({
  spec,
  autoPlay = false,
  initialSceneIndex = 0,
  initialZoom = false,
  initialCaptions = true,
  playbackSpeed = 1.0,
  onSceneChange,
  onComplete,
  holdSceneEndRef,
}: UseTutorialPlayerOptions): UseTutorialPlayerReturn {
  const totalScenes = spec?.scenes?.length ?? 0;

  const [currentSceneIndex, setCurrentSceneIndex] = useState(() => {
    if (totalScenes === 0) return 0;
    return Math.max(0, Math.min(totalScenes - 1, initialSceneIndex));
  });

  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [currentTimeMs, setCurrentTimeMsState] = useState(0);
  // The frame loop reads time from a ref and changes scenes outside any state updater: React may run an updater
  // twice (always in dev StrictMode), and advancing inside one skipped steps (#319).
  const currentTimeRef = useRef(0);
  const setCurrentTimeMs = useCallback((ms: number) => {
    currentTimeRef.current = ms;
    setCurrentTimeMsState(ms);
  }, []);
  const [isZoomEnabled, setIsZoomEnabled] = useState(initialZoom);
  const [isCaptionsEnabled, setIsCaptionsEnabled] = useState(initialCaptions);

  // Keep refs to avoid stale closures in requestAnimationFrame
  const currentSceneIndexRef = useRef(currentSceneIndex);
  const scenesRef = useRef(spec?.scenes ?? []);
  const heldMsRef = useRef(0);

  useEffect(() => {
    currentSceneIndexRef.current = currentSceneIndex;
  }, [currentSceneIndex]);

  useEffect(() => {
    scenesRef.current = spec?.scenes ?? [];
  }, [spec?.scenes]);

  const currentScene = spec?.scenes?.[currentSceneIndex];

  // Actions
  const play = useCallback(() => {
    const scenes = scenesRef.current;
    const curIdx = currentSceneIndexRef.current;
    const curScene = scenes[curIdx];

    // If at the end of the last step, wrap back to the beginning
    if (curIdx === scenes.length - 1 && curScene && currentTimeRef.current >= curScene.duration_ms) {
      setCurrentSceneIndex(0);
      currentSceneIndexRef.current = 0;
      setCurrentTimeMs(0);
      onSceneChange?.(0);
    }
    setIsPlaying(true);
  }, [onSceneChange, setCurrentTimeMs]);

  const pause = useCallback(() => {
    setIsPlaying(false);
  }, []);

  const togglePlay = useCallback(() => {
    if (isPlaying) pause();
    else play();
  }, [isPlaying, pause, play]);

  const goToStep = useCallback(
    (index: number) => {
      const scenes = scenesRef.current;
      if (scenes.length === 0) return;
      const clamped = Math.max(0, Math.min(scenes.length - 1, index));
      setCurrentSceneIndex(clamped);
      currentSceneIndexRef.current = clamped;
      setCurrentTimeMs(0);
      onSceneChange?.(clamped);
    },
    [onSceneChange, setCurrentTimeMs],
  );

  const nextStep = useCallback(() => {
    const scenes = scenesRef.current;
    const curIdx = currentSceneIndexRef.current;
    if (curIdx < scenes.length - 1) {
      const nextIdx = curIdx + 1;
      setCurrentSceneIndex(nextIdx);
      currentSceneIndexRef.current = nextIdx;
      setCurrentTimeMs(0);
      onSceneChange?.(nextIdx);
    }
  }, [onSceneChange, setCurrentTimeMs]);

  const prevStep = useCallback(() => {
    // If we've played more than 500ms into the step, reset to start of this step
    if (currentTimeMs > 500) {
      setCurrentTimeMs(0);
      return;
    }

    const curIdx = currentSceneIndexRef.current;
    if (curIdx > 0) {
      const prevIdx = curIdx - 1;
      setCurrentSceneIndex(prevIdx);
      currentSceneIndexRef.current = prevIdx;
      setCurrentTimeMs(0);
      onSceneChange?.(prevIdx);
    } else {
      setCurrentTimeMs(0);
    }
  }, [currentTimeMs, onSceneChange, setCurrentTimeMs]);

  const replayCurrentStep = useCallback(() => {
    setCurrentTimeMs(0);
  }, [setCurrentTimeMs]);

  const toggleZoom = useCallback(() => {
    setIsZoomEnabled((prev) => !prev);
  }, []);

  const toggleCaptions = useCallback(() => {
    setIsCaptionsEnabled((prev) => !prev);
  }, []);

  const seekTo = useCallback((timeMs: number) => {
    const scenes = scenesRef.current;
    const curScene = scenes[currentSceneIndexRef.current];
    if (!curScene) return;
    const clamped = Math.max(0, Math.min(curScene.duration_ms, timeMs));
    setCurrentTimeMs(clamped);
  }, [setCurrentTimeMs]);

  // Animation frame loop for playback progression
  useEffect(() => {
    if (!isPlaying || !spec || !spec.scenes || spec.scenes.length === 0) {
      return;
    }

    let animId: number;
    let lastTime = performance.now();

    const tick = (now: number) => {
      const delta = (now - lastTime) * playbackSpeed;
      lastTime = now;

      const scenes = scenesRef.current;
      const curIdx = currentSceneIndexRef.current;
      const curScene = scenes[curIdx];
      if (curScene) {
        const nextTime = currentTimeRef.current + delta;
        if (nextTime < curScene.duration_ms) {
          heldMsRef.current = 0;
          setCurrentTimeMs(nextTime);
        } else if (holdSceneEndRef?.current && heldMsRef.current < MAX_SCENE_HOLD_MS) {
          heldMsRef.current += delta;
          setCurrentTimeMs(curScene.duration_ms);
        } else if (curIdx < scenes.length - 1) {
          heldMsRef.current = 0;
          const nextIdx = curIdx + 1;
          currentSceneIndexRef.current = nextIdx;
          setCurrentSceneIndex(nextIdx);
          setCurrentTimeMs(0);
          onSceneChange?.(nextIdx);
        } else {
          // End of tutorial reached: stop the loop here, so onComplete runs once
          heldMsRef.current = 0;
          setCurrentTimeMs(curScene.duration_ms);
          setIsPlaying(false);
          onComplete?.();
          return;
        }
      }

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [isPlaying, spec, playbackSpeed, onSceneChange, onComplete, holdSceneEndRef, setCurrentTimeMs]);

  // Derived progress values
  const sceneDuration = currentScene?.duration_ms ?? 1;
  const sceneProgress = Math.max(0, Math.min(1, currentTimeMs / sceneDuration));

  let elapsedTotalMs = 0;
  for (let i = 0; i < currentSceneIndex; i++) {
    elapsedTotalMs += spec?.scenes?.[i]?.duration_ms ?? 0;
  }
  elapsedTotalMs += currentTimeMs;

  const totalDurationMs = spec?.total_duration_ms || 1;
  const overallProgress = Math.max(0, Math.min(1, elapsedTotalMs / totalDurationMs));

  const isFirstStep = currentSceneIndex === 0;
  const isLastStep = currentSceneIndex === totalScenes - 1;

  return {
    currentSceneIndex,
    isPlaying,
    currentTimeMs,
    isZoomEnabled,
    isCaptionsEnabled,
    currentScene,
    totalScenes,
    sceneProgress,
    overallProgress,
    isFirstStep,
    isLastStep,
    play,
    pause,
    togglePlay,
    nextStep,
    prevStep,
    replayCurrentStep,
    goToStep,
    toggleZoom,
    toggleCaptions,
    seekTo,
  };
}
