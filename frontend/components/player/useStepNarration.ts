"use client";

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";

export interface UseStepNarrationOptions {
  text?: string;
  isPlaying: boolean;
  currentStepIndex: number;
  initialMuted?: boolean;
  rate?: number;
  pitch?: number;
  onWordBoundary?: (wordIndex: number, charIndex: number) => void;
  onNarrationEnd?: () => void;
  /**
   * Set to true from the moment a step's narration starts until a short pause after its last word, so the
   * player can hold the step until the voice is done instead of cutting it off mid-word (#83).
   */
  narratingRef?: MutableRefObject<boolean>;
}

/** Pause after the last word before the player may move on, so steps don't run into each other. */
export const NARRATION_TAIL_MS = 400;

export interface UseStepNarrationReturn {
  isSupported: boolean;
  isMuted: boolean;
  isSpeaking: boolean;
  activeWordIndex: number | null;
  toggleMute: () => void;
  setMuted: (muted: boolean) => void;
  speak: () => void;
  cancel: () => void;
  selectedVoice: SpeechSynthesisVoice | null;
}

/**
 * Calculates zero-based word token index corresponding to the given charIndex in text.
 */
export function calculateWordIndex(text: string, charIndex: number): number {
  if (!text || charIndex <= 0) return 0;
  const prefix = text.slice(0, charIndex);
  const words = prefix.trim().split(/\s+/).filter(Boolean);
  return Math.max(0, words.length);
}

/**
 * Selects the optimal natural English voice, falling back to local/standard voices.
 */
export function selectOptimalVoice(
  voices: SpeechSynthesisVoice[],
): SpeechSynthesisVoice | null {
  if (!voices || voices.length === 0) return null;

  // 1. Prioritize Microsoft Natural Online English voices
  const natural = voices.find(
    (v) =>
      v.lang.toLowerCase().startsWith("en") &&
      v.name.includes("Natural") &&
      v.name.includes("Microsoft"),
  );
  if (natural) return natural;

  // 2. Standard Google / Microsoft English online voices
  const standard = voices.find(
    (v) => v.lang.toLowerCase().startsWith("en") && !v.localService,
  );
  if (standard) return standard;

  // 3. Local offline voices (SAPI5: David, Zira, Mark, etc.)
  const local = voices.find(
    (v) => v.lang.toLowerCase().startsWith("en") && v.localService,
  );
  if (local) return local;

  // 4. Any English voice
  const anyEnglish = voices.find((v) => v.lang.toLowerCase().startsWith("en"));
  if (anyEnglish) return anyEnglish;

  return voices[0] || null;
}

export function useStepNarration({
  text,
  isPlaying,
  currentStepIndex,
  initialMuted = false,
  rate = 1.0,
  pitch = 1.0,
  onWordBoundary,
  onNarrationEnd,
  narratingRef,
}: UseStepNarrationOptions): UseStepNarrationReturn {
  const isSupported =
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    typeof window.SpeechSynthesisUtterance !== "undefined";

  const [isMuted, setIsMuted] = useState(initialMuted);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [activeWordIndex, setActiveWordIndex] = useState<number | null>(null);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>(() => {
    if (
      typeof window !== "undefined" &&
      "speechSynthesis" in window &&
      typeof window.speechSynthesis.getVoices === "function"
    ) {
      try {
        return window.speechSynthesis.getVoices() || [];
      } catch {
        return [];
      }
    }
    return [];
  });

  // Events of a cancelled utterance can arrive after the next one started (Chrome fires them async):
  // only the current utterance may change state.
  const currentUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const tailTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopNarrating = useCallback(() => {
    if (tailTimerRef.current !== null) clearTimeout(tailTimerRef.current);
    tailTimerRef.current = null;
    currentUtteranceRef.current = null;
    if (narratingRef) narratingRef.current = false;
  }, [narratingRef]);

  const finishNarration = useCallback(() => {
    if (tailTimerRef.current !== null) clearTimeout(tailTimerRef.current);
    tailTimerRef.current = setTimeout(() => {
      tailTimerRef.current = null;
      if (narratingRef) narratingRef.current = false;
    }, NARRATION_TAIL_MS);
  }, [narratingRef]);

  const isMutedRef = useRef(isMuted);
  useEffect(() => {
    isMutedRef.current = isMuted;
  }, [isMuted]);

  // Load available speech synthesis voices when browser updates them
  useEffect(() => {
    if (!isSupported) return;

    const loadVoices = () => {
      try {
        const available = window.speechSynthesis.getVoices();
        if (available && available.length > 0) {
          setVoices(available);
        }
      } catch (err) {
        console.warn("Failed to retrieve speech synthesis voices:", err);
      }
    };

    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = loadVoices;
    }

    return () => {
      if (window.speechSynthesis) {
        window.speechSynthesis.onvoiceschanged = null;
      }
    };
  }, [isSupported]);

  const selectedVoice = selectOptimalVoice(voices);

  const cancel = useCallback(() => {
    if (!isSupported) return;
    try {
      window.speechSynthesis.cancel();
    } catch (err) {
      console.warn("Error cancelling speech synthesis:", err);
    }
    stopNarrating();
    setIsSpeaking(false);
    setActiveWordIndex(null);
  }, [isSupported, stopNarrating]);

  const speak = useCallback(() => {
    if (!isSupported || isMutedRef.current || !text || text.trim() === "") {
      return;
    }

    try {
      window.speechSynthesis.cancel();
    } catch {
      // ignore
    }

    try {
      const utterance = new window.SpeechSynthesisUtterance(text);
      if (selectedVoice) {
        utterance.voice = selectedVoice;
      }
      utterance.rate = rate;
      utterance.pitch = pitch;

      utterance.onstart = () => {
        if (currentUtteranceRef.current !== utterance) return;
        setIsSpeaking(true);
        setActiveWordIndex(0);
      };

      utterance.onboundary = (e: SpeechSynthesisEvent) => {
        if (currentUtteranceRef.current !== utterance) return;
        if (e.name === "word") {
          const wIdx = calculateWordIndex(text, e.charIndex);
          setActiveWordIndex(wIdx);
          onWordBoundary?.(wIdx, e.charIndex);
        }
      };

      utterance.onend = () => {
        if (currentUtteranceRef.current !== utterance) return;
        setIsSpeaking(false);
        setActiveWordIndex(null);
        finishNarration();
        onNarrationEnd?.();
      };

      utterance.onerror = (e: SpeechSynthesisErrorEvent) => {
        if (currentUtteranceRef.current !== utterance) return;
        if (e.error !== "canceled" && e.error !== "interrupted") {
          console.warn("Speech synthesis utterance error:", e.error);
        }
        setIsSpeaking(false);
        setActiveWordIndex(null);
        stopNarrating();
      };

      currentUtteranceRef.current = utterance;
      if (narratingRef) narratingRef.current = true;
      window.speechSynthesis.speak(utterance);
    } catch (err) {
      console.warn("Failed to speak utterance via Speech API:", err);
    }
  }, [
    isSupported,
    text,
    selectedVoice,
    rate,
    pitch,
    onWordBoundary,
    onNarrationEnd,
    finishNarration,
    stopNarrating,
    narratingRef,
  ]);

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      if (next) {
        cancel();
      }
      return next;
    });
  }, [cancel]);

  const setMuted = useCallback(
    (muted: boolean) => {
      setIsMuted(muted);
      if (muted) {
        cancel();
      }
    },
    [cancel],
  );

  // Trigger speech synthesis when playback is active
  useEffect(() => {
    if (!isSupported) return;

    if (isPlaying && !isMuted && text && text.trim() !== "") {
      try {
        window.speechSynthesis.cancel();
        const utterance = new window.SpeechSynthesisUtterance(text);
        if (selectedVoice) {
          utterance.voice = selectedVoice;
        }
        utterance.rate = rate;
        utterance.pitch = pitch;

        utterance.onstart = () => {
          if (currentUtteranceRef.current !== utterance) return;
          setIsSpeaking(true);
          setActiveWordIndex(0);
        };

        utterance.onboundary = (e: SpeechSynthesisEvent) => {
          if (currentUtteranceRef.current !== utterance) return;
          if (e.name === "word") {
            const wIdx = calculateWordIndex(text, e.charIndex);
            setActiveWordIndex(wIdx);
            onWordBoundary?.(wIdx, e.charIndex);
          }
        };

        utterance.onend = () => {
          if (currentUtteranceRef.current !== utterance) return;
          setIsSpeaking(false);
          setActiveWordIndex(null);
          finishNarration();
          onNarrationEnd?.();
        };

        utterance.onerror = (e: SpeechSynthesisErrorEvent) => {
          if (currentUtteranceRef.current !== utterance) return;
          if (e.error !== "canceled" && e.error !== "interrupted") {
            console.warn("Speech synthesis utterance error:", e.error);
          }
          setIsSpeaking(false);
          setActiveWordIndex(null);
          stopNarrating();
        };

        currentUtteranceRef.current = utterance;
        if (narratingRef) narratingRef.current = true;
        window.speechSynthesis.speak(utterance);
      } catch (err) {
        console.warn("Failed to speak utterance via Speech API:", err);
      }
    } else {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // ignore
      }
      stopNarrating();
    }

    return () => {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // ignore
      }
      stopNarrating();
    };
  }, [
    isSupported,
    isPlaying,
    isMuted,
    currentStepIndex,
    text,
    selectedVoice,
    rate,
    pitch,
    onWordBoundary,
    onNarrationEnd,
    finishNarration,
    stopNarrating,
    narratingRef,
  ]);

  return {
    isSupported,
    isMuted,
    isSpeaking,
    activeWordIndex,
    toggleMute,
    setMuted,
    speak,
    cancel,
    selectedVoice,
  };
}
