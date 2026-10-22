export { compileWorkflow } from "./compiler.js";
export {
  generateCursorTrajectory,
  evaluateBezierPoint,
  bezierToSvgPath,
  round1,
  type BezierOptions,
} from "./bezier.js";
export {
  computeCameraKeyframe,
  computeClampedOffsets,
  type CameraOptions,
} from "./camera.js";
export {
  generateHeuristicWordTimings,
  type CaptionTimingOptions,
} from "./caption.js";
export {
  estimateSpeechDurationMs,
  MS_PER_WORD,
  SENTENCE_END_BUFFER_MS,
  MIN_STEP_DURATION_MS,
  MAX_STEP_DURATION_MS,
  type SpeechDurationOptions,
} from "./timing/speech.js";
export {
  validateTutorialSpec,
  assertValidTutorialSpec,
  type ValidationResult,
} from "./validator.js";
export {
  commonSchema,
  stepSchema,
  workflowSchema,
  tutorialSpecSchema,
} from "./schema/index.js";
export type {
  Action,
  Action1,
  ActionType,
  BoundingBox,
  Camera,
  Caption,
  ClickType,
  CompilerOptions,
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
  VerifiedWorkflow,
  WordTiming,
  Workflow,
  WorkflowViewport,
} from "./types.js";
