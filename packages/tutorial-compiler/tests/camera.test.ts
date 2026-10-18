import { describe, expect, it } from "vitest";
import {
  computeCameraKeyframe,
  computeClampedOffsets,
} from "../src/camera.js";
import type { BoundingBox, WorkflowViewport } from "../src/types.js";

describe("computeCameraKeyframe", () => {
  const viewport: WorkflowViewport = {
    width: 1280,
    height: 800,
    device_scale_factor: 1.0,
  };

  it("calculates camera center and default zoom scale for a target bounding box", () => {
    const bbox: BoundingBox = [1146, 6, 56, 36];

    const camera = computeCameraKeyframe(bbox, viewport);

    expect(camera).not.toBeNull();
    expect(camera?.center).toEqual({
      x: 1174, // 1146 + 28
      y: 24,   // 6 + 18
    });
    expect(camera?.scale).toBe(1.35);
    expect(camera?.easing).toBe("cubic-bezier(0.22, 1, 0.36, 1)");
    expect(camera?.pan_duration_ms).toBe(450);
  });

  it("returns null when no bounding box is provided", () => {
    expect(computeCameraKeyframe(null, viewport)).toBeNull();
    expect(computeCameraKeyframe(undefined, viewport)).toBeNull();
  });

  it("clamps scale between 1.0 and 3.0", () => {
    const bbox: BoundingBox = [100, 100, 50, 50];

    const low = computeCameraKeyframe(bbox, viewport, { scale: 0.5 });
    expect(low?.scale).toBe(1.0);

    const high = computeCameraKeyframe(bbox, viewport, { scale: 5.0 });
    expect(high?.scale).toBe(3.0);
  });

  it("clamps scale to 1.0 and pan duration to 0 under reduced motion", () => {
    const bbox: BoundingBox = [100, 100, 50, 50];

    const camera = computeCameraKeyframe(bbox, viewport, {
      scale: 1.5,
      panDurationMs: 600,
      reducedMotion: true,
    });

    expect(camera?.scale).toBe(1.0);
    expect(camera?.pan_duration_ms).toBe(0);
    expect(camera?.center).toEqual({ x: 125, y: 125 });
  });
});

describe("computeClampedOffsets", () => {
  const viewport: WorkflowViewport = {
    width: 1280,
    height: 800,
    device_scale_factor: 1.0,
  };

  it("prevents exposing top-left canvas borders", () => {
    // Zooming into top-left element
    const center = { x: 50, y: 50 };
    const scale = 1.5;

    const { panX, panY } = computeClampedOffsets(center, scale, viewport);

    // deltaX = 50 * (1 - 1.5) = -25
    expect(panX).toBe(-25);
    expect(panY).toBe(-25);
  });

  it("clamps to maximum negative translation for bottom-right elements", () => {
    // Element past bottom-right corner
    const center = { x: 1300, y: 850 };
    const scale = 1.35;

    const { panX, panY } = computeClampedOffsets(center, scale, viewport);

    // Max translation: -(W * (S - 1)) = -(1280 * 0.35) = -448
    // Max translation Y: -(H * (S - 1)) = -(800 * 0.35) = -280
    expect(panX).toBe(-448);
    expect(panY).toBe(-280);
  });
});
