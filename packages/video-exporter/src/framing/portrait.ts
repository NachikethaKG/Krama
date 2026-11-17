import type { Point, Scene, WorkflowViewport } from "@krama/contracts-ts";
import type { FramingTransform } from "./landscape.js";

/**
 * Computes 9:16 portrait framing (1080x1920) for mobile.
 * Implements "Follow the Highlight":
 * - Focuses on the highlight bounding box center with scale >= 1.6x so UI text is crisp.
 * - Positions target element at ~40% canvas height, keeping the bottom third clear for subtitles.
 * - Falls back to a horizontally fitted overview for steps without a target element.
 */
export function computePortraitFraming(
  scene: Scene | undefined,
  viewport: WorkflowViewport = { width: 1280, height: 800 },
  canvas = { width: 1080, height: 1920 },
): FramingTransform {
  const fitWidthScale = canvas.width / viewport.width; // 1080 / 1280 = 0.84375

  const highlightBbox = scene?.highlight?.bbox;
  const hasTarget = highlightBbox && highlightBbox.length === 4;

  if (!hasTarget) {
    // Overview step (navigate, overview): fit width, center vertically
    const fittedHeight = viewport.height * fitWidthScale;
    const centerY = (canvas.height - fittedHeight) / 2;
    return {
      scale: fitWidthScale,
      panX: 0,
      panY: centerY,
      fitScale: fitWidthScale,
    };
  }

  // Follow the highlight: center on the element
  const scrollX = scene?.scroll?.x ?? 0;
  const scrollY = scene?.scroll?.y ?? 0;

  const targetCenter: Point = {
    x: highlightBbox[0] + highlightBbox[2] / 2 - scrollX,
    y: highlightBbox[1] + highlightBbox[3] / 2 - scrollY,
  };

  // Zoom scale: minimum 1.6x for mobile readability, up to 2.2x
  const zoomScale = Math.max(1.6, Math.min(2.2, (scene?.camera?.scale ?? 1.35) * 1.3));

  // Desired position on canvas: horizontal center, 40% vertical height
  const desiredX = canvas.width / 2;
  const desiredY = canvas.height * 0.40;

  const rawPanX = desiredX - targetCenter.x * zoomScale;
  const rawPanY = desiredY - targetCenter.y * zoomScale;

  // Soft clamping: ensure target remains fully in frame
  const scaledW = viewport.width * zoomScale;
  const scaledH = viewport.height * zoomScale;

  const minPanX = canvas.width - scaledW - 40;
  const maxPanX = 40;
  const minPanY = canvas.height - scaledH - 80;
  const maxPanY = 80;

  const panX = Math.max(minPanX, Math.min(maxPanX, rawPanX));
  const panY = Math.max(minPanY, Math.min(maxPanY, rawPanY));

  return {
    scale: zoomScale,
    panX,
    panY,
    fitScale: fitWidthScale,
  };
}
