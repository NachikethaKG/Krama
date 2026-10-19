"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
}

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
  initialZoom = true,
  initialCaptions = true,
  playbackSpeed = 1.0,
  onSceneChange,
  onComplete,
}: UseTutorialPlayerOptions): UseTutorialPlayerReturn {
  const totalScenes = spec?.scenes?.length ?? 0;

  const [currentSceneIndex, setCurrentSceneIndex] = useState(() => {
    if (totalScenes === 0) return 0;
    return Math.max(0, Math.min(totalScenes - 1, initialSceneIndex));
  });

  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [isZoomEnabled, setIsZoomEnabled] = useState(initialZoom);
  const [isCaptionsEnabled, setIsCaptionsEnabled] = useState(initialCaptions);

  // Keep refs to avoid stale closures in requestAnimationFrame
  const currentSceneIndexRef = useRef(currentSceneIndex);
  const scenesRef = useRef(spec?.scenes ?? []);

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
    if (curIdx === scenes.length - 1 && curScene && currentTimeMs >= curScene.duration_ms) {
      setCurrentSceneIndex(0);
      currentSceneIndexRef.current = 0;
      setCurrentTimeMs(0);
      onSceneChange?.(0);
    }
    setIsPlaying(true);
  }, [currentTimeMs, onSceneChange]);

  const pause = useCallback(() => {
    setIsPlaying(false);
  }, []);

  const togglePlay = useCallback(() => {
    setIsPlaying((prev) => {
      if (prev) return false;

      // When starting to play, check if we need to reset from the end
      const scenes = scenesRef.current;
      const curIdx = currentSceneIndexRef.current;
      const curScene = scenes[curIdx];
      if (curIdx === scenes.length - 1 && curScene && currentTimeMs >= curScene.duration_ms) {
        setCurrentSceneIndex(0);
        currentSceneIndexRef.current = 0;
        setCurrentTimeMs(0);
        onSceneChange?.(0);
      }
      return true;
    });
  }, [currentTimeMs, onSceneChange]);

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
    [onSceneChange],
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
  }, [onSceneChange]);

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
  }, [currentTimeMs, onSceneChange]);

  const replayCurrentStep = useCallback(() => {
    setCurrentTimeMs(0);
  }, []);

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
  }, []);

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

      setCurrentTimeMs((prevTime) => {
        const scenes = scenesRef.current;
        const curIdx = currentSceneIndexRef.current;
        const curScene = scenes[curIdx];

        if (!curScene) return prevTime;

        const nextTime = prevTime + delta;
        if (nextTime >= curScene.duration_ms) {
          // Check if there is a subsequent scene
          if (curIdx < scenes.length - 1) {
            const nextIdx = curIdx + 1;
            setCurrentSceneIndex(nextIdx);
            currentSceneIndexRef.current = nextIdx;
            onSceneChange?.(nextIdx);
            return 0;
          } else {
            // End of tutorial reached
            setIsPlaying(false);
            onComplete?.();
            return curScene.duration_ms;
          }
        }
        return nextTime;
      });

      animId = requestAnimationFrame(tick);
    };

    animId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [isPlaying, spec, playbackSpeed, onSceneChange, onComplete]);

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
