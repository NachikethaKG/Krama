import type { Point, Scene, WorkflowViewport } from "@krama/contracts-ts";
import { VIDEO_MAX_ZOOM, type FramingTransform } from "./landscape.js";

/** Page px -> canvas px around the highlight (#394): ~73% of a 1280px page's width, text still readable. */
export const PORTRAIT_ZOOM = VIDEO_MAX_ZOOM;

/**
 * Computes 9:16 portrait framing (1080x1920) for mobile.
 * Implements "Follow the Highlight" (D8, gentler since #394):
 * - Shows the page at PORTRAIT_ZOOM, panned sideways so the highlight is in frame and as central as the page
 *   edges allow.
 * - The page is a band across the middle of the tall canvas, a little above centre so the captions in the
 *   bottom third don't cover it.
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

  const zoomScale = PORTRAIT_ZOOM;
  const scaledW = viewport.width * zoomScale;
  const scaledH = viewport.height * zoomScale;

  // Sideways: the highlight as central as possible without showing past the page's edges.
  const rawPanX = canvas.width / 2 - targetCenter.x * zoomScale;
  const panX = Math.max(canvas.width - scaledW, Math.min(0, rawPanX));

  // Up and down: the whole page height fits, so it isn't cropped. Centre it, shifted up by a tenth of the
  // canvas to keep clear of the captions; a page taller than the canvas follows the highlight instead.
  const panY =
    scaledH <= canvas.height
      ? (canvas.height - scaledH) / 2 - canvas.height * 0.1
      : Math.max(canvas.height - scaledH, Math.min(0, canvas.height * 0.4 - targetCenter.y * zoomScale));

  return {
    scale: zoomScale,
    panX,
    panY,
    fitScale: fitWidthScale,
  };
}
