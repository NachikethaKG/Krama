import type { Point, Scene, WorkflowViewport } from "@krama/contracts-ts";

export interface FramingTransform {
  scale: number;
  panX: number;
  panY: number;
  fitScale: number;
}

/**
 * Computes 16:9 landscape framing (1920x1080) for a tutorial scene.
 * Fits the recorded viewport (1280x800) into 1728x1080 with 96px side bars,
 * applying camera zoom and pan focused on the target element.
 */
export function computeLandscapeFraming(
  scene: Scene | undefined,
  viewport: WorkflowViewport = { width: 1280, height: 800 },
  canvas = { width: 1920, height: 1080 },
): FramingTransform {
  // Base scale to fit viewport height to 1080
  const fitScale = canvas.height / viewport.height; // 1.35 for 800 -> 1080
  const fittedWidth = viewport.width * fitScale; // 1728 for 1280 -> 1920
  const defaultSideBar = (canvas.width - fittedWidth) / 2; // 96px

  if (!scene?.camera || scene.camera.scale <= 1.01) {
    return {
      scale: fitScale,
      panX: defaultSideBar,
      panY: 0,
      fitScale,
    };
  }

  const scrollX = scene.scroll?.x ?? 0;
  const scrollY = scene.scroll?.y ?? 0;
  const onScreenCenter: Point = {
    x: scene.camera.center.x - scrollX,
    y: scene.camera.center.y - scrollY,
  };

  const cameraScale = Math.max(1.0, Math.min(3.0, scene.camera.scale));
  const totalScale = fitScale * cameraScale;

  // Aim to place target center at the center of the 1920x1080 canvas
  const desiredPanX = canvas.width / 2 - onScreenCenter.x * totalScale;
  const desiredPanY = canvas.height / 2 - onScreenCenter.y * totalScale;

  // Clamping: don't reveal excessive blank margins outside the document
  const minPanX = canvas.width - viewport.width * totalScale;
  const minPanY = canvas.height - viewport.height * totalScale;

  const panX = Math.max(minPanX, Math.min(0, desiredPanX));
  const panY = Math.max(minPanY, Math.min(0, desiredPanY));

  return {
    scale: totalScale,
    panX,
    panY,
    fitScale,
  };
}
