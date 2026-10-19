import type { WordTiming } from "./types.js";

export interface CaptionTimingOptions {
  /**
   * Initial delay before the first word begins in milliseconds.
   * Default: 100.
   */
  startOffsetMs?: number;

  /**
   * Minimum duration for a single word in milliseconds.
   * Default: 180.
   */
  minWordDurationMs?: number;

  /**
   * Speaking time multiplier per character in milliseconds.
   * Default: 45.
   */
  charDurationMs?: number;

  /**
   * Pause added after a comma or semicolon in milliseconds.
   * Default: 150.
   */
  shortPauseMs?: number;

  /**
   * Pause added after a period, exclamation mark, or question mark in milliseconds.
   * Default: 350.
   */
  longPauseMs?: number;

  /**
   * Standard gap between consecutive words in milliseconds.
   * Default: 40.
   */
  interWordGapMs?: number;
}

/**
 * Generates deterministic heuristic word-level caption timings for an instruction string.
 *
 * Implements the heuristic model from docs/research/phase-2-nachiketha-narration-and-speech-sync.md:
 *   duration_word = max(minDuration, length * 45ms)
 *   punctuation pauses: comma/semicolon (+150ms), period/exclamation/question (+350ms)
 *   inter-word baseline gap: +40ms
 */
export function generateHeuristicWordTimings(
  text: string,
  options?: CaptionTimingOptions,
): WordTiming[] {
  if (!text || text.trim().length === 0) {
    return [];
  }

  const startOffset = options?.startOffsetMs ?? 100;
  const minWordDuration = options?.minWordDurationMs ?? 180;
  const charDuration = options?.charDurationMs ?? 45;
  const shortPause = options?.shortPauseMs ?? 150;
  const longPause = options?.longPauseMs ?? 350;
  const interWordGap = options?.interWordGapMs ?? 40;

  const tokens = text.trim().split(/\s+/).filter(Boolean);
  const timings: WordTiming[] = [];

  let currentMs = startOffset;

  for (let i = 0; i < tokens.length; i++) {
    const word = tokens[i];
    const isLast = i === tokens.length - 1;

    // Calculate word duration based on character length
    let duration = Math.max(minWordDuration, word.length * charDuration);

    // If word is a short symbol like "+", assign a reasonable quick duration
    if (word.length === 1 && !/[a-zA-Z0-9]/.test(word)) {
      duration = 60;
    }

    const start_ms = currentMs;
    const end_ms = start_ms + duration;

    timings.push({
      word,
      start_ms,
      end_ms,
    });

    // Advance timeline with word gap and punctuation pause
    let pause = interWordGap;
    if (/[,;]$/.test(word)) {
      pause += shortPause;
    } else if (/[.!?]$/.test(word)) {
      pause += longPause;
    }

    currentMs = end_ms + (isLast ? 0 : pause);
  }

  return timings;
}
