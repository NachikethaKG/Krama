export const MS_PER_WORD = 375; // ~160 words per minute
export const SENTENCE_END_BUFFER_MS = 400;
export const MIN_STEP_DURATION_MS = 1500;
export const MAX_STEP_DURATION_MS = 14000;

export interface SpeechDurationOptions {
  /**
   * Speaking time multiplier per word in milliseconds.
   * Default: 375 (~160 words per minute).
   */
  msPerWord?: number;

  /**
   * Sentence boundary trailing buffer in milliseconds.
   * Default: 400.
   */
  sentenceEndBufferMs?: number;

  /**
   * Minimum step duration in milliseconds when estimating from speech.
   * Default: 1500.
   */
  minStepDurationMs?: number;

  /**
   * Maximum step duration in milliseconds when estimating from speech.
   * Default: 14000.
   */
  maxStepDurationMs?: number;
}

/**
 * Estimates natural speaking / reading duration in milliseconds from instruction text.
 *
 * Implements natural speaking rate (~160 wpm, ~375 ms/word) + trailing sentence boundary buffer (400 ms),
 * clamped between MIN_STEP_DURATION_MS (1500 ms) and MAX_STEP_DURATION_MS (14000 ms).
 *
 * @param text The instruction or caption text
 * @param options Optional overrides for timing constants
 * @returns Estimated duration in milliseconds
 */
export function estimateSpeechDurationMs(
  text: string,
  options?: SpeechDurationOptions,
): number {
  const minDuration = options?.minStepDurationMs ?? MIN_STEP_DURATION_MS;
  const maxDuration = options?.maxStepDurationMs ?? MAX_STEP_DURATION_MS;
  const msPerWord = options?.msPerWord ?? MS_PER_WORD;
  const sentenceEndBuffer = options?.sentenceEndBufferMs ?? SENTENCE_END_BUFFER_MS;

  if (!text || typeof text !== "string") {
    return minDuration;
  }

  const words = text.trim().split(/\s+/).filter(Boolean);
  const wordCount = words.length;
  if (wordCount === 0) {
    return minDuration;
  }

  const rawEstimate = wordCount * msPerWord + sentenceEndBuffer;
  return Math.min(Math.max(rawEstimate, minDuration), maxDuration);
}
