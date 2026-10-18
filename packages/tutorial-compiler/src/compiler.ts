import { generateCursorTrajectory, round1 } from "./bezier.js";
import { computeCameraKeyframe } from "./camera.js";
import { generateHeuristicWordTimings } from "./caption.js";
import type {
  Action1,
  CompilerOptions,
  Cursor,
  Highlight,
  HighlightStyle,
  Point,
  RecordingSlice,
  Ripple,
  Scene,
  ScrollOffset,
  TutorialSpec,
  VerifiedWorkflow,
  WorkflowViewport,
} from "./types.js";
import { assertValidTutorialSpec } from "./validator.js";

/**
 * Pure TypeScript compiler that transforms a VerifiedWorkflow into a renderable TutorialSpec.
 *
 * Generates:
 * - Parametric cubic Bezier cursor trajectories that mimic natural wrist motion
 * - Click ripples and timing
 * - Element highlight bounding boxes
 * - Focal camera zoom and pan keyframes with canvas edge clamping
 * - Synchronous scroll preservation
 * - Caption and word timings
 * - Isolated recording slices
 *
 * Pure function: operates without DOM or platform-specific APIs.
 *
 * @param workflow The source verified workflow
 * @param options Compilation options
 * @returns A canonical TutorialSpec conforming to tutorial-spec.schema.json
 */
export function compileWorkflow(
  workflow: VerifiedWorkflow,
  options?: CompilerOptions,
): TutorialSpec {
  if (!workflow || typeof workflow !== "object") {
    throw new Error("Invalid workflow: expected a non-null object");
  }

  if (!workflow.id) {
    throw new Error("Invalid workflow: missing workflow id");
  }

  if (!workflow.title) {
    throw new Error("Invalid workflow: missing workflow title");
  }

  if (!Array.isArray(workflow.steps) || workflow.steps.length === 0) {
    throw new Error("Workflow must contain at least one step to compile a tutorial");
  }

  const viewport: WorkflowViewport = {
    width: workflow.viewport?.width ?? 1280,
    height: workflow.viewport?.height ?? 800,
    device_scale_factor: workflow.viewport?.device_scale_factor ?? 1.0,
  };

  const fps = options?.fps ?? 30;
  const scenePrefix = options?.sceneIdPrefix ?? "scene-";
  const reducedMotion = Boolean(options?.reducedMotion);

  let currentTimelineMs = 0;
  let previousCursorPos: Point = {
    x: round1(viewport.width / 2),
    y: round1(viewport.height / 2),
  };

  const scenes: Scene[] = [];

  for (const step of workflow.steps) {
    const step_seq = step.seq;
    const sceneId = `${scenePrefix}${step_seq}`;
    const sceneTitle = step.target?.name ?? null;

    // Action definition
    const action: Action1 = {
      type: step.action.type,
      value: step.action.value ?? null,
    };

    const sensitive = Boolean(step.sensitive);

    // Synchronous window scroll position
    const scroll: ScrollOffset | null = step.target?.scroll
      ? {
          x: step.target.scroll.x,
          y: step.target.scroll.y,
        }
      : null;

    // Recording slice alignment
    const recordingStartMs = step.timing?.start_ms ?? step.start_ms ?? 0;
    const recordingEndMs = step.timing?.end_ms ?? step.end_ms ?? 0;
    const baselineSnapshotIndex = step_seq === 1 ? 0 : null;

    const recording: RecordingSlice = {
      start_ms: recordingStartMs,
      end_ms: recordingEndMs,
      baseline_snapshot_index: baselineSnapshotIndex,
    };

    // Scene duration calculation
    let duration_ms: number;
    if (options?.stepDurations?.[step_seq] !== undefined) {
      duration_ms = options.stepDurations[step_seq];
    } else {
      const baseDuration = options?.baseDurationMs ?? 1650;
      if (step.action.type === "fill") {
        duration_ms = baseDuration + (options?.fillExtraDurationMs ?? 400);
      } else {
        duration_ms = baseDuration;
      }
    }

    // Caption and word timings
    let words = null;
    if (options?.wordTimings && options.wordTimings[step_seq] !== undefined) {
      words = options.wordTimings[step_seq];
    } else if (options?.generateWordTimings) {
      words = generateHeuristicWordTimings(step.instruction_text);
    }

    const caption = {
      text: step.instruction_text,
      words,
    };

    // Visual geometry: camera, cursor, and highlight
    let camera = null;
    let cursor: Cursor | null = null;
    let highlight: Highlight | null = null;

    const bbox = step.target?.bbox;

    if (bbox && bbox.length === 4) {
      const targetCenter: Point = {
        x: round1(bbox[0] + bbox[2] / 2),
        y: round1(bbox[1] + bbox[3] / 2),
      };

      // Camera focal zoom
      camera = computeCameraKeyframe(bbox, viewport, {
        scale: options?.cameraScale,
        easing: options?.cameraEasing,
        panDurationMs: options?.panDurationMs,
        reducedMotion,
      });

      // Target highlight
      const highlightStyle: HighlightStyle = reducedMotion
        ? "solid_box"
        : (options?.highlightStyle ?? "pulsing_ring");

      highlight = {
        bbox: [bbox[0], bbox[1], bbox[2], bbox[3]],
        style: highlightStyle,
        padding: options?.highlightPadding ?? 8,
        color: options?.highlightColor ?? "#4f46e5",
      };

      // Cursor trajectory & ripple
      const path = generateCursorTrajectory(previousCursorPos, targetCenter, {
        curveOffsetY1: options?.curveOffsetY1,
        curveOffsetY2: options?.curveOffsetY2,
        reducedMotion,
      });

      let clickType = options?.clickType ?? "single";
      if (
        step.action.type !== "click" &&
        step.action.type !== "fill" &&
        step.action.type !== "select" &&
        !options?.clickType
      ) {
        clickType = "none";
      }

      const ripple: Ripple | null =
        clickType !== "none"
          ? {
              radius: options?.rippleRadius ?? 24,
              color: options?.rippleColor ?? "rgba(99, 102, 241, 0.4)",
            }
          : null;

      cursor = {
        path,
        start_ms: reducedMotion ? 0 : (options?.cursorStartMs ?? 400),
        end_ms: reducedMotion ? 0 : (options?.cursorEndMs ?? 1000),
        click_ms: options?.cursorClickMs ?? 1150,
        click_type: clickType,
        ripple,
      };

      // Update cursor tracking position for next scene
      previousCursorPos = targetCenter;
    }

    const scene: Scene = {
      id: sceneId,
      step_seq,
      title: sceneTitle,
      start_ms: currentTimelineMs,
      duration_ms,
      action,
      sensitive,
      caption,
      recording,
      scroll,
      camera,
      cursor,
      highlight,
    };

    scenes.push(scene);
    currentTimelineMs += duration_ms;
  }

  const spec: TutorialSpec = {
    version: "1.0",
    workflow_id: workflow.id,
    title: workflow.title,
    description: workflow.task ?? null,
    viewport,
    fps,
    total_duration_ms: currentTimelineMs,
    scenes: scenes as [Scene, ...Scene[]],
  };

  if (options?.validate) {
    assertValidTutorialSpec(spec);
  }

  return spec;
}
