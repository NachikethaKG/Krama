/**
 * Pure coordinate transformation math for scaling bounding boxes and points
 * across responsive rrweb-player container dimensions.
 */

import type {
  Point,
  TransformedRect,
  TransformOptions,
} from './types';
import { normalizeBbox } from './types';

export interface ScaleAndOffsetResult {
  scale: number;
  scaleX: number;
  scaleY: number;
  offsetX: number;
  offsetY: number;
  contentWidth: number;
  contentHeight: number;
}

/**
 * Calculates scaling factors and letterbox centering offsets.
 *
 * In rrweb-player, the replayer wrapper is centered via `left: 50%; top: 50%; transform: translate(-50%, -50%) scale(...)`.
 * When aspect ratio is preserved:
 *   scale = min(containerWidth / recordedWidth, containerHeight / recordedHeight)
 *   offsetX = (containerWidth - (recordedWidth * scale)) / 2
 *   offsetY = (containerHeight - (recordedHeight * scale)) / 2
 */
export function computeScaleAndOffsets(
  containerWidth: number,
  containerHeight: number,
  recordedWidth: number,
  recordedHeight: number,
  preserveAspectRatio: boolean = true
): ScaleAndOffsetResult | null {
  if (
    containerWidth <= 0 ||
    containerHeight <= 0 ||
    recordedWidth <= 0 ||
    recordedHeight <= 0 ||
    isNaN(containerWidth) ||
    isNaN(containerHeight) ||
    isNaN(recordedWidth) ||
    isNaN(recordedHeight)
  ) {
    return null;
  }

  if (preserveAspectRatio) {
    const scale = Math.min(containerWidth / recordedWidth, containerHeight / recordedHeight);
    const contentWidth = recordedWidth * scale;
    const contentHeight = recordedHeight * scale;
    const offsetX = (containerWidth - contentWidth) / 2;
    const offsetY = (containerHeight - contentHeight) / 2;

    return {
      scale,
      scaleX: scale,
      scaleY: scale,
      offsetX,
      offsetY,
      contentWidth,
      contentHeight,
    };
  }

  const scaleX = containerWidth / recordedWidth;
  const scaleY = containerHeight / recordedHeight;
  return {
    scale: Math.min(scaleX, scaleY),
    scaleX,
    scaleY,
    offsetX: 0,
    offsetY: 0,
    contentWidth: containerWidth,
    contentHeight: containerHeight,
  };
}

/**
 * Transforms a recorded bounding box into container coordinates, accounting for
 * player scaling, letterbox offsets, and page scroll offsets.
 */
export function transformCoordinates(options: TransformOptions): TransformedRect | null {
  const norm = normalizeBbox(options.bbox);
  if (!norm) {
    return null;
  }

  const {
    containerWidth,
    containerHeight,
    recordedWidth,
    recordedHeight,
    scrollX = 0,
    scrollY = 0,
    preserveAspectRatio = true,
  } = options;

  const layout = computeScaleAndOffsets(
    containerWidth,
    containerHeight,
    recordedWidth,
    recordedHeight,
    preserveAspectRatio
  );

  if (!layout) {
    return null;
  }

  const { scaleX, scaleY, offsetX, offsetY } = layout;

  // Viewport-relative coordinates (subtracting page scroll)
  const viewportX = norm.x - scrollX;
  const viewportY = norm.y - scrollY;

  // Scaled coordinates centered in container
  const x = offsetX + viewportX * scaleX;
  const y = offsetY + viewportY * scaleY;
  const width = norm.width * scaleX;
  const height = norm.height * scaleY;

  // Check if transformed rectangle is visible in the container viewport
  const visible =
    x + width > 0 &&
    y + height > 0 &&
    x < containerWidth &&
    y < containerHeight;

  return {
    x: Math.round(x * 100) / 100,
    y: Math.round(y * 100) / 100,
    width: Math.round(width * 100) / 100,
    height: Math.round(height * 100) / 100,
    scaleX,
    scaleY,
    visible,
  };
}

/**
 * Transforms a recorded 2D point (such as cursor position) into container coordinates.
 */
export function transformPoint(
  point: Point | null | undefined,
  options: Omit<TransformOptions, 'bbox'>
): Point | null {
  if (
    !point ||
    typeof point.x !== 'number' ||
    typeof point.y !== 'number' ||
    isNaN(point.x) ||
    isNaN(point.y)
  ) {
    return null;
  }

  const {
    containerWidth,
    containerHeight,
    recordedWidth,
    recordedHeight,
    scrollX = 0,
    scrollY = 0,
    preserveAspectRatio = true,
  } = options;

  const layout = computeScaleAndOffsets(
    containerWidth,
    containerHeight,
    recordedWidth,
    recordedHeight,
    preserveAspectRatio
  );

  if (!layout) {
    return null;
  }

  const { scaleX, scaleY, offsetX, offsetY } = layout;
  const viewportX = point.x - scrollX;
  const viewportY = point.y - scrollY;

  return {
    x: Math.round((offsetX + viewportX * scaleX) * 100) / 100,
    y: Math.round((offsetY + viewportY * scaleY) * 100) / 100,
  };
}
