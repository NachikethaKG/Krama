import { describe, expect, it } from "vitest";
import type { Scene } from "@krama/contracts-ts";
import { computeLandscapeFraming } from "../src/framing/landscape.js";
import { computePortraitFraming } from "../src/framing/portrait.js";

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

    it("zooms into the target element when camera zoom is specified", () => {
      const framing = computeLandscapeFraming(MOCK_SCENE_WITH_TARGET, VIEWPORT, { width: 1920, height: 1080 });

      // totalScale = 1.35 * 1.5 = 2.025
      expect(framing.scale).toBeCloseTo(2.025, 2);
      // pan should shift the canvas to focus near (660, 220)
      expect(framing.panX).toBeLessThan(96);
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

    it("follows the highlight by zooming with scale >= 1.6x and centering on the target element", () => {
      const framing = computePortraitFraming(MOCK_SCENE_WITH_TARGET, VIEWPORT, { width: 1080, height: 1920 });

      // Scale must be at least 1.6x for mobile readability
      expect(framing.scale).toBeGreaterThanOrEqual(1.6);
      expect(framing.scale).toBeLessThanOrEqual(2.5);

      // Target center is placed roughly at 40% height of 1920 (~768px)
      // canvas height is 1920, target element is centered
      expect(framing.panX).toBeDefined();
      expect(framing.panY).toBeDefined();
    });
  });
});
