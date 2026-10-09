/**
 * Hook for responsive bounding box and cursor coordinate transformation.
 * Observes container dimensions via ResizeObserver and continuously computes
 * transformed coordinates for SVG overlays.
 */

import { useState, useEffect, useMemo, RefObject } from 'react';
import type { BoundingBox, Point, TransformedRect } from './types';
import { transformCoordinates, transformPoint } from './coordinateTransform';

export interface UseCoordinateTransformOptions {
  containerRef: RefObject<HTMLElement | null>;
  bbox?: BoundingBox | null;
  cursorPosition?: Point | null;
  recordedWidth?: number;
  recordedHeight?: number;
  scrollX?: number;
  scrollY?: number;
  preserveAspectRatio?: boolean;
}

export interface UseCoordinateTransformResult {
  containerSize: { width: number; height: number };
  transformedRect: TransformedRect | null;
  transformedCursor: Point | null;
}

export function useCoordinateTransform({
  containerRef,
  bbox,
  cursorPosition,
  recordedWidth = 1280,
  recordedHeight = 720,
  scrollX = 0,
  scrollY = 0,
  preserveAspectRatio = true,
}: UseCoordinateTransformOptions): UseCoordinateTransformResult {
  const [containerSize, setContainerSize] = useState<{ width: number; height: number }>({
    width: 0,
    height: 0,
  });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Initial measurement
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      setContainerSize({ width: rect.width, height: rect.height });
    }

    if (typeof ResizeObserver === 'undefined') {
      return;
    }

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;

      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) {
        setContainerSize((prev) => {
          if (prev.width === width && prev.height === height) {
            return prev;
          }
          return { width, height };
        });
      }
    });

    observer.observe(el);

    return () => {
      observer.disconnect();
    };
  }, [containerRef]);

  const transformedRect = useMemo(() => {
    if (containerSize.width <= 0 || containerSize.height <= 0 || !bbox) {
      return null;
    }

    return transformCoordinates({
      bbox,
      containerWidth: containerSize.width,
      containerHeight: containerSize.height,
      recordedWidth,
      recordedHeight,
      scrollX,
      scrollY,
      preserveAspectRatio,
    });
  }, [
    bbox,
    containerSize.width,
    containerSize.height,
    recordedWidth,
    recordedHeight,
    scrollX,
    scrollY,
    preserveAspectRatio,
  ]);

  const transformedCursor = useMemo(() => {
    if (containerSize.width <= 0 || containerSize.height <= 0 || !cursorPosition) {
      return null;
    }

    return transformPoint(cursorPosition, {
      containerWidth: containerSize.width,
      containerHeight: containerSize.height,
      recordedWidth,
      recordedHeight,
      scrollX,
      scrollY,
      preserveAspectRatio,
    });
  }, [
    cursorPosition,
    containerSize.width,
    containerSize.height,
    recordedWidth,
    recordedHeight,
    scrollX,
    scrollY,
    preserveAspectRatio,
  ]);

  return {
    containerSize,
    transformedRect,
    transformedCursor,
  };
}
