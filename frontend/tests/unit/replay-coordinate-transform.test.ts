import { describe, expect, it } from 'vitest';
import {
  normalizeBbox,
  computeScaleAndOffsets,
  transformCoordinates,
  transformPoint,
  extractRecordedDimensions,
} from '@/components/replay';
import type { BoundingBox, eventWithTime } from '@/components/replay';

describe('replay coordinate transformation', () => {
  describe('normalizeBbox', () => {
    it('normalizes a 4-tuple [x, y, width, height]', () => {
      const tuple: BoundingBox = [100, 200, 300, 400];
      const result = normalizeBbox(tuple);
      expect(result).toEqual({ x: 100, y: 200, width: 300, height: 400 });
    });

    it('normalizes an object { x, y, width, height }', () => {
      const obj: BoundingBox = { x: 50, y: 75, width: 120, height: 60 };
      const result = normalizeBbox(obj);
      expect(result).toEqual({ x: 50, y: 75, width: 120, height: 60 });
    });

    it('returns null for missing, null, or undefined bboxes', () => {
      expect(normalizeBbox(null)).toBeNull();
      expect(normalizeBbox(undefined)).toBeNull();
    });

    it('returns null for zero or negative dimensions', () => {
      expect(normalizeBbox([10, 20, 0, 50])).toBeNull();
      expect(normalizeBbox([10, 20, 50, -10])).toBeNull();
      expect(normalizeBbox({ x: 10, y: 20, width: -10, height: 50 })).toBeNull();
      expect(normalizeBbox({ x: 10, y: 20, width: 50, height: 0 })).toBeNull();
    });

    it('returns null for NaN or incomplete inputs', () => {
      expect(normalizeBbox([NaN, 20, 100, 50])).toBeNull();
      // @ts-expect-error testing malformed array
      expect(normalizeBbox([10, 20])).toBeNull();
      // @ts-expect-error testing invalid type
      expect(normalizeBbox({ x: '10', y: 20, width: 100, height: 50 })).toBeNull();
    });
  });

  describe('computeScaleAndOffsets', () => {
    it('computes 1:1 scale when container matches recorded viewport', () => {
      const layout = computeScaleAndOffsets(1280, 720, 1280, 720);
      expect(layout).toEqual({
        scale: 1,
        scaleX: 1,
        scaleY: 1,
        offsetX: 0,
        offsetY: 0,
        contentWidth: 1280,
        contentHeight: 720,
      });
    });

    it('computes uniform half-scale when container is proportionally half size', () => {
      const layout = computeScaleAndOffsets(640, 360, 1280, 720);
      expect(layout).toEqual({
        scale: 0.5,
        scaleX: 0.5,
        scaleY: 0.5,
        offsetX: 0,
        offsetY: 0,
        contentWidth: 640,
        contentHeight: 360,
      });
    });

    it('computes letterboxing offsets when container is taller than aspect ratio', () => {
      // 1280x1000 container with 1280x720 recorded aspect -> scale is 1.0, offsetY = (1000 - 720)/2 = 140
      const layout = computeScaleAndOffsets(1280, 1000, 1280, 720);
      expect(layout).not.toBeNull();
      expect(layout?.scale).toBe(1);
      expect(layout?.offsetX).toBe(0);
      expect(layout?.offsetY).toBe(140);
    });

    it('computes pillarboxing offsets when container is wider than aspect ratio', () => {
      // 1600x720 container with 1280x720 recorded aspect -> scale is 1.0, offsetX = (1600 - 1280)/2 = 160
      const layout = computeScaleAndOffsets(1600, 720, 1280, 720);
      expect(layout).not.toBeNull();
      expect(layout?.scale).toBe(1);
      expect(layout?.offsetX).toBe(160);
      expect(layout?.offsetY).toBe(0);
    });

    it('handles non-proportional stretch when preserveAspectRatio is false', () => {
      const layout = computeScaleAndOffsets(1000, 500, 1280, 720, false);
      expect(layout).not.toBeNull();
      expect(layout?.scaleX).toBeCloseTo(1000 / 1280, 5);
      expect(layout?.scaleY).toBeCloseTo(500 / 720, 5);
      expect(layout?.offsetX).toBe(0);
      expect(layout?.offsetY).toBe(0);
    });

    it('returns null for non-positive or NaN dimensions', () => {
      expect(computeScaleAndOffsets(0, 500, 1280, 720)).toBeNull();
      expect(computeScaleAndOffsets(1000, -10, 1280, 720)).toBeNull();
      expect(computeScaleAndOffsets(1000, 500, 0, 720)).toBeNull();
      expect(computeScaleAndOffsets(1000, 500, 1280, NaN)).toBeNull();
    });
  });

  describe('transformCoordinates', () => {
    it('scales bounding box accurately at 1:1 ratio without scroll', () => {
      const transformed = transformCoordinates({
        bbox: [100, 150, 200, 80],
        containerWidth: 1280,
        containerHeight: 720,
        recordedWidth: 1280,
        recordedHeight: 720,
      });

      expect(transformed).toEqual({
        x: 100,
        y: 150,
        width: 200,
        height: 80,
        scaleX: 1,
        scaleY: 1,
        visible: true,
      });
    });

    it('scales bounding box accurately at 0.5x ratio', () => {
      const transformed = transformCoordinates({
        bbox: [100, 150, 200, 80],
        containerWidth: 640,
        containerHeight: 360,
        recordedWidth: 1280,
        recordedHeight: 720,
      });

      expect(transformed).toEqual({
        x: 50,
        y: 75,
        width: 100,
        height: 40,
        scaleX: 0.5,
        scaleY: 0.5,
        visible: true,
      });
    });

    it('scales bounding box accurately at 0.25x ratio', () => {
      const transformed = transformCoordinates({
        bbox: [100, 200, 400, 80],
        containerWidth: 320,
        containerHeight: 180,
        recordedWidth: 1280,
        recordedHeight: 720,
      });

      expect(transformed).toEqual({
        x: 25,
        y: 50,
        width: 100,
        height: 20,
        scaleX: 0.25,
        scaleY: 0.25,
        visible: true,
      });
    });

    it('accounts for vertical and horizontal scroll offset', () => {
      const transformed = transformCoordinates({
        bbox: [200, 800, 300, 50],
        containerWidth: 1280,
        containerHeight: 720,
        recordedWidth: 1280,
        recordedHeight: 720,
        scrollX: 50,
        scrollY: 700,
      });

      // viewport x = 200 - 50 = 150, viewport y = 800 - 700 = 100
      expect(transformed).toEqual({
        x: 150,
        y: 100,
        width: 300,
        height: 50,
        scaleX: 1,
        scaleY: 1,
        visible: true,
      });
    });

    it('accounts for letterbox centering offsets', () => {
      // 1600x720 container with 1280x720 content -> offsetX = (1600-1280)/2 = 160
      const transformed = transformCoordinates({
        bbox: [100, 50, 200, 60],
        containerWidth: 1600,
        containerHeight: 720,
        recordedWidth: 1280,
        recordedHeight: 720,
      });

      expect(transformed).toEqual({
        x: 260, // 160 offset + 100
        y: 50,
        width: 200,
        height: 60,
        scaleX: 1,
        scaleY: 1,
        visible: true,
      });
    });

    it('detects off-screen elements and marks visible: false', () => {
      const transformed = transformCoordinates({
        bbox: [200, 3000, 300, 50], // element is way down page
        containerWidth: 1280,
        containerHeight: 720,
        recordedWidth: 1280,
        recordedHeight: 720,
        scrollY: 0, // not scrolled down yet
      });

      expect(transformed).not.toBeNull();
      expect(transformed?.visible).toBe(false);
    });

    it('returns null for missing, null, or invalid bbox', () => {
      expect(
        transformCoordinates({
          bbox: null,
          containerWidth: 1280,
          containerHeight: 720,
          recordedWidth: 1280,
          recordedHeight: 720,
        })
      ).toBeNull();
    });
  });

  describe('transformPoint', () => {
    it('scales cursor point accurately at 0.5x ratio', () => {
      const transformed = transformPoint(
        { x: 300, y: 400 },
        {
          containerWidth: 640,
          containerHeight: 360,
          recordedWidth: 1280,
          recordedHeight: 720,
        }
      );

      expect(transformed).toEqual({ x: 150, y: 200 });
    });

    it('accounts for scroll offset and letterboxing in point scaling', () => {
      const transformed = transformPoint(
        { x: 400, y: 1000 },
        {
          containerWidth: 1600,
          containerHeight: 720,
          recordedWidth: 1280,
          recordedHeight: 720,
          scrollY: 800,
        }
      );

      // scale: 1, offsetX: 160, offsetY: 0, viewportY: 1000 - 800 = 200
      expect(transformed).toEqual({ x: 560, y: 200 });
    });

    it('returns null for invalid or null point', () => {
      expect(
        transformPoint(null, {
          containerWidth: 1280,
          containerHeight: 720,
          recordedWidth: 1280,
          recordedHeight: 720,
        })
      ).toBeNull();
      expect(
        transformPoint(
          { x: NaN, y: 100 },
          {
            containerWidth: 1280,
            containerHeight: 720,
            recordedWidth: 1280,
            recordedHeight: 720,
          }
        )
      ).toBeNull();
    });
  });

  describe('extractRecordedDimensions', () => {
    it('extracts dimensions from type 4 Meta event', () => {
      const events: eventWithTime[] = [
        {
          type: 4,
          data: { href: 'http://test.local', width: 1920, height: 1080 },
          timestamp: 100,
        },
        {
          type: 0,
          data: {},
          timestamp: 200,
        },
      ];

      const dims = extractRecordedDimensions(events);
      expect(dims).toEqual({ width: 1920, height: 1080 });
    });

    it('falls back to 1280x720 when Meta event is absent', () => {
      const events: eventWithTime[] = [
        {
          type: 0,
          data: {},
          timestamp: 100,
        },
      ];

      const dims = extractRecordedDimensions(events);
      expect(dims).toEqual({ width: 1280, height: 720 });
    });

    it('falls back to custom fallback dimensions if specified', () => {
      const dims = extractRecordedDimensions([], { width: 800, height: 600 });
      expect(dims).toEqual({ width: 800, height: 600 });
    });
  });
});
