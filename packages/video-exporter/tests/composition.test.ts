import { describe, expect, it } from "vitest";
import type { TutorialSpec } from "@krama/contracts-ts";
import { calculateTotalFrames } from "../src/compositions/TutorialComposition.js";

const TEST_SPEC: TutorialSpec = {
  version: "1.0",
  workflow_id: "wf-calc",
  title: "Test Spec",
  viewport: { width: 1280, height: 800 },
  total_duration_ms: 7000,
  scenes: [
    {
      id: "s1",
      step_seq: 1,
      start_ms: 0,
      duration_ms: 3000, // 3s = 90 frames @ 30fps
      action: { type: "click" },
      recording: { start_ms: 0, end_ms: 3000 },
      caption: { text: "Step 1" },
    },
    {
      id: "s2",
      step_seq: 2,
      start_ms: 3000,
      duration_ms: 4000, // 4s = 120 frames @ 30fps
      action: { type: "fill", value: "test" },
      recording: { start_ms: 3000, end_ms: 7000 },
      caption: { text: "Step 2" },
    },
  ],
};

describe("Remotion Tutorial Composition", () => {
  it("calculates exact total duration in frames including intro and outro (Decision D4, D9)", () => {
    // Intro: 60 frames (2s)
    // Scene 1: 90 frames (3s)
    // Scene 2: 120 frames (4s)
    // Outro: 60 frames (2s)
    // Total = 60 + 90 + 120 + 60 = 330 frames (11 seconds)
    const totalFrames = calculateTotalFrames(TEST_SPEC, 30, 60, 60);
    expect(totalFrames).toBe(330);
  });
});
