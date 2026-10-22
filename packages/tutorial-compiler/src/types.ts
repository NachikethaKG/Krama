import type {
  Action,
  Action1,
  ActionType,
  BoundingBox,
  Camera,
  Caption,
  ClickType,
  Cursor,
  Highlight,
  HighlightStyle,
  Point,
  RecordingSlice,
  Ripple,
  Scene,
  ScrollOffset,
  Step,
  TutorialSpec,
  WordTiming,
  Workflow,
  WorkflowViewport,
} from "@krama/contracts-ts";

export type {
  Action,
  Action1,
  ActionType,
  BoundingBox,
  Camera,
  Caption,
  ClickType,
  Cursor,
  Highlight,
  HighlightStyle,
  Point,
  RecordingSlice,
  Ripple,
  Scene,
  ScrollOffset,
  Step,
  TutorialSpec,
  WordTiming,
  Workflow,
  WorkflowViewport,
};

/**
 * A VerifiedWorkflow ready to be compiled into a TutorialSpec.
 * Conforms to the canonical Workflow schema.
 */
export type VerifiedWorkflow = Workflow;

/**
 * Options to configure the workflow-to-tutorial-spec compiler.
 */
export interface CompilerOptions {
  /**
   * Target frame rate for video rendering (Remotion export).
   * Default: 30.
   */
  fps?: number;

  /**
   * Camera zoom scale factor (1.0 to 3.0).
   * Default: 1.35.
   */
  cameraScale?: number;

  /**
   * CSS easing function for camera pan/zoom.
   * Default: "cubic-bezier(0.22, 1, 0.36, 1)".
   */
  cameraEasing?: string;

  /**
   * Duration of camera zoom/pan transition in milliseconds.
   * Default: 450.
   */
  panDurationMs?: number;

  /**
   * Default scene duration in milliseconds for normal steps (fallback/minimum).
   * Default: 1650.
   */
  baseDurationMs?: number;

  /**
   * Extra duration added for 'fill' steps to allow for typing simulation.
   * Default: 400.
   */
  fillExtraDurationMs?: number;

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

  /**
   * Milliseconds after scene start when cursor glide begins.
   * Default: 400.
   */
  cursorStartMs?: number;

  /**
   * Milliseconds after scene start when cursor arrives at target.
   * Default: 1000.
   */
  cursorEndMs?: number;

  /**
   * Milliseconds after scene start when click ripple triggers.
   * Default: 1150.
   */
  cursorClickMs?: number;

  /**
   * Default click type for interactive elements.
   * Default: "single".
   */
  clickType?: ClickType;

  /**
   * Default ripple radius in CSS pixels.
   * Default: 24.
   */
  rippleRadius?: number;

  /**
   * Default ripple color.
   * Default: "rgba(99, 102, 241, 0.4)".
   */
  rippleColor?: string;

  /**
   * Default highlight style.
   * Default: "pulsing_ring".
   */
  highlightStyle?: HighlightStyle;

  /**
   * Default highlight padding in CSS pixels.
   * Default: 8.
   */
  highlightPadding?: number;

  /**
   * Default highlight color.
   * Default: "#4f46e5".
   */
  highlightColor?: string;

  /**
   * Vertical arc offset in pixels at t=1/3 for Bezier curve.
   * Default: 40.
   */
  curveOffsetY1?: number;

  /**
   * Vertical arc offset in pixels at t=2/3 for Bezier curve.
   * Default: 20.
   */
  curveOffsetY2?: number;

  /**
   * Respects prefers-reduced-motion:
   * - Clamps camera scale to 1.0 (no zoom)
   * - Sets pan duration to 0
   * - Cursor trajectory jumps instantly to target (start_ms=0, end_ms=0)
   * - Highlight style becomes "solid_box"
   */
  reducedMotion?: boolean;

  /**
   * Per-step explicit word timings (key = step_seq).
   * If provided for a step, overrides automatic word timings.
   */
  wordTimings?: Record<number, WordTiming[] | null>;

  /**
   * Whether to automatically generate heuristic word timings for steps
   * without explicit word timings.
   * Default: false (caption.words is null unless provided).
   */
  generateWordTimings?: boolean;

  /**
   * Per-step duration overrides in milliseconds (key = step_seq).
   */
  stepDurations?: Record<number, number>;

  /**
   * Scene ID prefix.
   * Default: "scene-".
   */
  sceneIdPrefix?: string;

  /**
   * Whether to validate the compiled TutorialSpec against the JSON Schema.
   * Default: false.
   */
  validate?: boolean;
}
