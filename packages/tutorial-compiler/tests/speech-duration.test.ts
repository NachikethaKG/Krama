import { describe, expect, it } from "vitest";
import { compileWorkflow } from "../src/compiler.js";
import {
  estimateSpeechDurationMs,
  MAX_STEP_DURATION_MS,
  MIN_STEP_DURATION_MS,
  MS_PER_WORD,
  SENTENCE_END_BUFFER_MS,
} from "../src/timing/speech.js";
import type { VerifiedWorkflow } from "../src/types.js";
import { assertValidTutorialSpec } from "../src/validator.js";

describe("estimateSpeechDurationMs", () => {
  it("uses default constants: ~375ms/word, 400ms buffer, min 1500ms, max 14000ms", () => {
    expect(MS_PER_WORD).toBe(375);
    expect(SENTENCE_END_BUFFER_MS).toBe(400);
    expect(MIN_STEP_DURATION_MS).toBe(1500);
    expect(MAX_STEP_DURATION_MS).toBe(14000);
  });

  it("clamps empty or whitespace-only instructions to MIN_STEP_DURATION_MS (1500ms)", () => {
    expect(estimateSpeechDurationMs("")).toBe(1500);
    expect(estimateSpeechDurationMs("   ")).toBe(1500);
    expect(estimateSpeechDurationMs("\n\t  \r\n")).toBe(1500);
  });

  it("clamps very short instructions (1-2 words) to MIN_STEP_DURATION_MS (1500ms)", () => {
    // 1 word: 1 * 375 + 400 = 775ms -> clamped to 1500ms
    expect(estimateSpeechDurationMs("Save")).toBe(1500);

    // 2 words: 2 * 375 + 400 = 1150ms -> clamped to 1500ms
    expect(estimateSpeechDurationMs("Click Save.")).toBe(1500);
    expect(estimateSpeechDurationMs("Click **Save**.")).toBe(1500);
  });

  it("calculates speech duration proportionally for medium and long instructions", () => {
    // 3 words: 3 * 375 + 400 = 1525ms
    const shortText = "Click on Save.";
    const shortDuration = estimateSpeechDurationMs(shortText);
    expect(shortDuration).toBe(1525);

    // 20 words: 20 * 375 + 400 = 7900ms
    const longText =
      "In the left navigation menu, open the branch settings and change the default branch to main and click confirm save.";
    const words20 = longText.trim().split(/\s+/).filter(Boolean);
    expect(words20.length).toBe(20);
    const longDuration = estimateSpeechDurationMs(longText);
    expect(longDuration).toBe(7900);

    // Verify proportional scaling: long is significantly greater than short
    expect(longDuration).toBeGreaterThan(shortDuration * 4);
  });

  it("compares realistic short instruction vs long instruction from prompt", () => {
    const shortInstruction = "Click **Save**.";
    const longInstruction =
      "In the left navigation menu, open the branch settings and change the default branch to main.";

    const shortMs = estimateSpeechDurationMs(shortInstruction);
    const longMs = estimateSpeechDurationMs(longInstruction);

    // Short instruction is clamped to minimum 1500ms
    expect(shortMs).toBe(1500);

    // 16 words: 16 * 375 + 400 = 6400ms
    expect(longMs).toBe(6400);
    expect(longMs).toBeGreaterThan(shortMs * 3);
  });

  it("clamps overly verbose instructions to MAX_STEP_DURATION_MS (14000ms)", () => {
    // 50 words: 50 * 375 + 400 = 19150ms -> clamped to 14000ms
    const verboseText = Array(50).fill("word").join(" ");
    expect(estimateSpeechDurationMs(verboseText)).toBe(14000);

    // 100 words: well exceeds max ceiling
    const extremeText = Array(100).fill("instruction").join(" ");
    expect(estimateSpeechDurationMs(extremeText)).toBe(14000);
  });

  it("respects custom speech duration options", () => {
    const text = "One two three four"; // 4 words
    const custom = estimateSpeechDurationMs(text, {
      msPerWord: 300,
      sentenceEndBufferMs: 200,
      minStepDurationMs: 1000,
      maxStepDurationMs: 8000,
    });
    // 4 * 300 + 200 = 1400ms
    expect(custom).toBe(1400);

    // Custom min clamp
    expect(estimateSpeechDurationMs("", { minStepDurationMs: 2000 })).toBe(2000);

    // Custom max clamp
    const long = Array(30).fill("word").join(" ");
    expect(estimateSpeechDurationMs(long, { maxStepDurationMs: 5000 })).toBe(5000);
  });
});

describe("compileWorkflow with dynamic speech duration sizing", () => {
  const baseMockWorkflow: VerifiedWorkflow = {
    id: "12345678-1234-4000-8000-1234567890ab",
    title: "Test Workflow",
    task: "Verify dynamic duration sizing",
    status: "verified",
    viewport: { width: 1280, height: 800, device_scale_factor: 1 },
    steps: [
      {
        id: "step-1",
        seq: 1,
        instruction_text: "Click **Save**.",
        action: { type: "click" },
        target: { bbox: [100, 100, 80, 30] },
        expected_state: {},
        observed_state: { url: "https://example.com" },
        verification: { result: "verified", method: ["url"], confidence: 1 },
        risk: "low",
        timing: { start_ms: 0, end_ms: 800 }, // 800ms action
      },
      {
        id: "step-2",
        seq: 2,
        instruction_text:
          "In the left navigation menu, open the branch settings and change the default branch to main.",
        action: { type: "click" },
        target: { bbox: [200, 200, 120, 40] },
        expected_state: {},
        observed_state: { url: "https://example.com" },
        verification: { result: "verified", method: ["url"], confidence: 1 },
        risk: "low",
        timing: { start_ms: 1000, end_ms: 1800 }, // 800ms action
      },
    ],
  };

  it("sizes step duration_ms dynamically based on instruction text length", () => {
    const compiled = compileWorkflow(baseMockWorkflow);

    expect(compiled.scenes).toHaveLength(2);

    const scene1 = compiled.scenes[0];
    const scene2 = compiled.scenes[1];

    // Step 1: "Click **Save**." (2 words) -> speech estimate 1500ms > action duration 800ms
    expect(scene1.duration_ms).toBe(1500);

    // Step 2: 16 words -> speech estimate 6400ms > action duration 800ms
    expect(scene2.duration_ms).toBe(6400);

    // Scene 2 starts exactly when Scene 1 ends
    expect(scene1.start_ms).toBe(0);
    expect(scene2.start_ms).toBe(1500);

    // Total duration is sum of scene durations (1500 + 6400 = 7900ms)
    expect(compiled.total_duration_ms).toBe(7900);

    assertValidTutorialSpec(compiled);
  });

  it("lower bounds duration_ms by the underlying UI action duration", () => {
    const workflowWithLongAction: VerifiedWorkflow = {
      ...baseMockWorkflow,
      steps: [
        {
          id: "step-long-action",
          seq: 1,
          instruction_text: "Click **Save**.", // speech estimate: 1500ms
          action: { type: "click" },
          target: { bbox: [100, 100, 80, 30] },
          expected_state: {},
          observed_state: { url: "https://example.com" },
          verification: { result: "verified", method: ["url"], confidence: 1 },
          risk: "low",
          timing: { start_ms: 0, end_ms: 4500 }, // UI action took 4500ms
        },
      ],
    };

    const compiled = compileWorkflow(workflowWithLongAction);
    const scene = compiled.scenes[0];

    // Action duration (4500ms) exceeds speech estimate (1500ms) -> lower bounded by 4500ms
    expect(scene.duration_ms).toBe(4500);
    expect(compiled.total_duration_ms).toBe(4500);
  });

  it("allows explicit stepDurations overrides to take precedence", () => {
    const compiled = compileWorkflow(baseMockWorkflow, {
      stepDurations: {
        1: 2200,
        2: 3300,
      },
    });

    expect(compiled.scenes[0].duration_ms).toBe(2200);
    expect(compiled.scenes[1].duration_ms).toBe(3300);
    expect(compiled.total_duration_ms).toBe(5500);
  });
});
