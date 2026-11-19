import { describe, expect, it } from "vitest";
import type { Scene } from "@krama/contracts-ts";
import { VIDEO_MAX_ZOOM, computeLandscapeFraming } from "../src/framing/landscape.js";
import { PORTRAIT_ZOOM, computePortraitFraming } from "../src/framing/portrait.js";

const VIEWPORT = { width: 1280, height: 800 };

const MOCK_SCENE_WITH_TARGET: Scene = {
  id: "scene-1",
  step_seq: 1,
  title: "Click New Repo",
  start_ms: 0,
  duration_ms: 3000,
  action: { type: "click" },
  recording: { start_ms: 1000, end_ms: 2000 },
  highlight: {
    bbox: [600, 300, 120, 40],
    color: "#4f46e5",
    padding: 8,
    style: "pulsing_ring",
  },
  camera: {
    center: { x: 660, y: 320 },
    scale: 1.5,
    easing: "cubic-bezier(0.22, 1, 0.36, 1)",
    pan_duration_ms: 450,
  },
  scroll: { x: 0, y: 100 },
  caption: { text: "Click the New Repository button." },
};

const MOCK_SCENE_NO_TARGET: Scene = {
  id: "scene-2",
  step_seq: 2,
  title: "Navigate to Dashboard",
  start_ms: 3000,
  duration_ms: 2500,
  action: { type: "navigate", value: "https://git.local/dashboard" },
  recording: { start_ms: 3000, end_ms: 4500 },
  caption: { text: "Navigate to the dashboard." },
};

describe("Framing Calculators (Decision D7, D8)", () => {
  describe("Landscape 16:9 Framing (computeLandscapeFraming)", () => {
    it("fits 1280x800 viewport into 1920x1080 with 96px side bars when unzoomed", () => {
      const sceneUnzoomed: Scene = {
        ...MOCK_SCENE_NO_TARGET,
        camera: { center: { x: 640, y: 400 }, scale: 1.0 },
      };

      const framing = computeLandscapeFraming(sceneUnzoomed, VIEWPORT, { width: 1920, height: 1080 });

      expect(framing.scale).toBeCloseTo(1.35, 2);
      expect(framing.panX).toBe(96); // (1920 - 1280*1.35) / 2 = 96
      expect(framing.panY).toBe(0);
    });

    it("zooms gently towards the target, even when the spec's camera asks for more (#394)", () => {
      const framing = computeLandscapeFraming(MOCK_SCENE_WITH_TARGET, VIEWPORT, { width: 1920, height: 1080 });

      // The spec asks for 1.5x; the video caps it: 1.35 * 1.15
      expect(framing.scale).toBeCloseTo(1.35 * VIDEO_MAX_ZOOM, 4);
      expect(framing.panX).toBeLessThan(96);
      // nearly the whole page stays in frame
      expect(1920 / framing.scale / VIEWPORT.width).toBeGreaterThan(0.95);
      expect(1080 / framing.scale / VIEWPORT.height).toBeGreaterThan(0.85);
      // and the target (660, 320 - scroll 100) is in it
      const x = 660 * framing.scale + framing.panX;
      const y = (320 - 100) * framing.scale + framing.panY;
      expect(x).toBeGreaterThan(0);
      expect(x).toBeLessThan(1920);
      expect(y).toBeGreaterThan(0);
      expect(y).toBeLessThan(1080);
    });
  });

  describe("Portrait 9:16 Framing (computePortraitFraming)", () => {
    it("fits viewport horizontally and centers vertically for steps without a target element", () => {
      const framing = computePortraitFraming(MOCK_SCENE_NO_TARGET, VIEWPORT, { width: 1080, height: 1920 });

      // 1080 / 1280 = 0.84375
      expect(framing.scale).toBeCloseTo(0.84375, 4);
      expect(framing.panX).toBe(0);
      // (1920 - 800 * 0.84375) / 2 = 622.5
      expect(framing.panY).toBeCloseTo(622.5, 1);
    });

    it("follows the highlight with a gentle zoom, the whole page height in frame (#394)", () => {
      const framing = computePortraitFraming(MOCK_SCENE_WITH_TARGET, VIEWPORT, { width: 1080, height: 1920 });

      expect(framing.scale).toBeCloseTo(PORTRAIT_ZOOM, 4);
      // ~73% of the page's width is shown, never past its edges
      expect(1080 / framing.scale / VIEWPORT.width).toBeGreaterThan(0.7);
      expect(framing.panX).toBeLessThanOrEqual(0);
      expect(framing.panX).toBeGreaterThanOrEqual(1080 - VIEWPORT.width * framing.scale);
      // the page's full height fits, above the captions in the bottom third
      expect(framing.panY).toBeGreaterThanOrEqual(0);
      expect(framing.panY + VIEWPORT.height * framing.scale).toBeLessThan(1920 * 0.7);
      // the target is in frame
      const x = 660 * framing.scale + framing.panX;
      expect(x).toBeGreaterThan(0);
      expect(x).toBeLessThan(1080);
    });

    it("keeps a target at the page's right edge in frame", () => {
      const right: Scene = {
        ...MOCK_SCENE_WITH_TARGET,
        highlight: { ...MOCK_SCENE_WITH_TARGET.highlight!, bbox: [1150, 300, 120, 40] },
      };
      const framing = computePortraitFraming(right, VIEWPORT, { width: 1080, height: 1920 });

      expect((1150 + 120) * framing.scale + framing.panX).toBeLessThanOrEqual(1080);
    });
  });
});
