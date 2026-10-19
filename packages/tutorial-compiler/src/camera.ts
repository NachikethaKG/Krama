import { round1 } from "./bezier.js";
import type { BoundingBox, Camera, Point, WorkflowViewport } from "./types.js";

export interface CameraOptions {
  /**
   * Camera zoom scale factor (1.0 to 3.0).
   * Default: 1.35.
   */
  scale?: number;

  /**
   * CSS easing function for camera pan/zoom.
   * Default: "cubic-bezier(0.22, 1, 0.36, 1)".
   */
  easing?: string;

  /**
   * Duration of camera zoom/pan transition in milliseconds.
   * Default: 450.
   */
  panDurationMs?: number;

  /**
   * Respects prefers-reduced-motion:
   * - Clamps scale to 1.0 (no zoom)
   * - Sets panDurationMs to 0
   */
  reducedMotion?: boolean;
}

/**
 * Computes the Camera keyframe focused on the target bounding box.
 * Returns null if no bounding box is provided (e.g. for non-element steps like navigate or wait).
 */
export function computeCameraKeyframe(
  bbox: BoundingBox | null | undefined,
  viewport: WorkflowViewport,
  options?: CameraOptions,
): Camera | null {
  if (!bbox) {
    return null;
  }

  const [x, y, w, h] = bbox;
  const center: Point = {
    x: round1(x + w / 2),
    y: round1(y + h / 2),
  };

  if (options?.reducedMotion) {
    return {
      scale: 1.0,
      center,
      easing: options?.easing ?? "cubic-bezier(0.22, 1, 0.36, 1)",
      pan_duration_ms: 0,
    };
  }

  const rawScale = options?.scale ?? 1.35;
  const scale = Math.max(1.0, Math.min(3.0, rawScale));

  return {
    scale,
    center,
    easing: options?.easing ?? "cubic-bezier(0.22, 1, 0.36, 1)",
    pan_duration_ms: options?.panDurationMs ?? 450,
  };
}

/**
 * Computes clamped pan offsets (panX, panY) ensuring the zoomed canvas
 * does not expose blank margins outside document bounds.
 *
 * Implements:
 *   deltaX_clamped = max(-(W * (S - 1)), min(0, Cx * (1 - S)))
 *   deltaY_clamped = max(-(H * (S - 1)), min(0, Cy * (1 - S)))
 */
export function computeClampedOffsets(
  center: Point,
  scale: number,
  viewport: WorkflowViewport,
): { panX: number; panY: number } {
  const W = viewport.width;
  const H = viewport.height;
  const S = Math.max(1.0, scale);

  const deltaX = center.x * (1 - S);
  const deltaY = center.y * (1 - S);

  const minX = -(W * (S - 1));
  const minY = -(H * (S - 1));

  const panX = Math.max(minX, Math.min(0, deltaX));
  const panY = Math.max(minY, Math.min(0, deltaY));

  return {
    panX: round1(panX),
    panY: round1(panY),
  };
}
