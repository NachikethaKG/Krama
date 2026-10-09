/**
 * Types and interfaces for rrweb replay and SVG highlight overlays.
 */

import type { eventWithTime } from '@rrweb/types';
export type { eventWithTime };

/**
 * Bounding box represented as a 4-tuple [x, y, width, height] in page coordinates (CSS px).
 */
export type BoundingBoxTuple = [x: number, y: number, width: number, height: number];

/**
 * Bounding box represented as an object with x, y, width, height in page coordinates (CSS px).
 */
export interface BoundingBoxRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * Accepted bounding box inputs (either tuple or rect object).
 */
export type BoundingBox = BoundingBoxTuple | BoundingBoxRect;

/**
 * Normalized 2D coordinates.
 */
export interface Point {
  x: number;
  y: number;
}

/**
 * Represents a single workflow step with timing and spatial annotations.
 */
export interface ReplayStep {
  id?: string;
  seq?: number;
  instruction?: string;
  timeOffset: number; // millisecond timestamp relative to recording start
  bbox?: BoundingBox | null;
  cursorPosition?: Point | null;
  status?: 'pending' | 'active' | 'completed' | 'failed';
}

/**
 * Scaled coordinates for rendering on top of the responsive player container.
 */
export interface TransformedRect {
  x: number;
  y: number;
  width: number;
  height: number;
  scaleX: number;
  scaleY: number;
  visible: boolean;
}

/**
 * Options for computing coordinate scaling.
 */
export interface TransformOptions {
  bbox: BoundingBox | null | undefined;
  containerWidth: number;
  containerHeight: number;
  recordedWidth: number;
  recordedHeight: number;
  scrollX?: number;
  scrollY?: number;
  preserveAspectRatio?: boolean;
}

/**
 * Helper to normalize any bounding box format into a BoundingBoxRect.
 * Returns null if the bbox is missing, zero-sized, or invalid.
 */
export function normalizeBbox(bbox?: BoundingBox | null): BoundingBoxRect | null {
  if (!bbox) return null;

  let x: number;
  let y: number;
  let width: number;
  let height: number;

  if (Array.isArray(bbox)) {
    if (bbox.length < 4) return null;
    [x, y, width, height] = bbox;
  } else {
    ({ x, y, width, height } = bbox);
  }

  if (
    typeof x !== 'number' ||
    typeof y !== 'number' ||
    typeof width !== 'number' ||
    typeof height !== 'number' ||
    isNaN(x) ||
    isNaN(y) ||
    isNaN(width) ||
    isNaN(height) ||
    width <= 0 ||
    height <= 0
  ) {
    return null;
  }

  return { x, y, width, height };
}

/**
 * Props for the ReplayViewer component.
 */
export interface ReplayViewerProps {
  events: eventWithTime[];
  steps?: ReplayStep[];
  currentStepIndex?: number;
  onStepChange?: (index: number) => void;
  width?: number | string;
  height?: number | string;
  autoPlay?: boolean;
  className?: string;
  showControls?: boolean;
  showOverlay?: boolean;
}
