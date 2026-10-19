"use client";

import { useEffect } from "react";

export interface UsePlayerKeyboardShortcutsOptions {
  onTogglePlay: () => void;
  onNextStep: () => void;
  onPrevStep: () => void;
  onReplayCurrentStep: () => void;
  onToggleZoom?: () => void;
  onToggleCaptions?: () => void;
  onToggleMute?: () => void;
  isEnabled?: boolean;
}

/**
 * Binds global/container keyboard navigation shortcuts for tutorial playback.
 * Ignores keystrokes when focus is inside text inputs, textareas, or contentEditable elements.
 */
export function usePlayerKeyboardShortcuts({
  onTogglePlay,
  onNextStep,
  onPrevStep,
  onReplayCurrentStep,
  onToggleZoom,
  onToggleCaptions,
  onToggleMute,
  isEnabled = true,
}: UsePlayerKeyboardShortcutsOptions) {
  useEffect(() => {
    if (!isEnabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Do not capture keys when user is typing in form controls
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }

      switch (e.key) {
        // Play / Pause: Space or K
        case " ":
        case "k":
        case "K":
          e.preventDefault();
          onTogglePlay();
          break;

        // Next Step: ArrowRight or L
        case "ArrowRight":
        case "l":
        case "L":
          e.preventDefault();
          onNextStep();
          break;

        // Previous Step: ArrowLeft or J
        case "ArrowLeft":
        case "j":
        case "J":
          e.preventDefault();
          onPrevStep();
          break;

        // Replay Current Step: R
        case "r":
        case "R":
          e.preventDefault();
          onReplayCurrentStep();
          break;

        // Toggle Audio Narration Mute: M
        case "m":
        case "M":
          if (onToggleMute) {
            e.preventDefault();
            onToggleMute();
          }
          break;

        // Toggle Captions: C
        case "c":
        case "C":
          if (onToggleCaptions) {
            e.preventDefault();
            onToggleCaptions();
          }
          break;

        // Toggle Camera Auto-Zoom: Z
        case "z":
        case "Z":
          if (onToggleZoom) {
            e.preventDefault();
            onToggleZoom();
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    isEnabled,
    onTogglePlay,
    onNextStep,
    onPrevStep,
    onReplayCurrentStep,
    onToggleZoom,
    onToggleCaptions,
    onToggleMute,
  ]);
}
