import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { compileWorkflow } from "../src/compiler.js";
import type {
  TutorialSpec,
  VerifiedWorkflow,
} from "../src/types.js";
import { assertValidTutorialSpec, validateTutorialSpec } from "../src/validator.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const WORKFLOW_FIXTURE_PATH = path.resolve(
  __dirname,
  "../../../contracts/fixtures/gitea-create-repo-workflow.json",
);

const SPEC_FIXTURE_PATH = path.resolve(
  __dirname,
  "../../../contracts/fixtures/tutorial-spec/gitea-create-repo.json",
);

describe("compileWorkflow", () => {
  const rawWorkflow = readFileSync(WORKFLOW_FIXTURE_PATH, "utf-8");
  const workflowFixture: VerifiedWorkflow = JSON.parse(rawWorkflow);

  const rawSpec = readFileSync(SPEC_FIXTURE_PATH, "utf-8");
  const expectedSpecFixture: TutorialSpec = JSON.parse(rawSpec);

  it("compiles the canonical gitea-create-repo workflow to exactly match the canonical tutorial-spec fixture", () => {
    // Provide explicit word timings and scene durations matching the canonical fixture snapshot
    const compiled = compileWorkflow(workflowFixture, {
      wordTimings: {
        1: expectedSpecFixture.scenes[0].caption.words ?? null,
      },
      stepDurations: Object.fromEntries(
        expectedSpecFixture.scenes.map((s) => [s.step_seq, s.duration_ms]),
      ),
    });

    // 1. Assert exact equality with canonical snapshot fixture
    expect(compiled).toEqual(expectedSpecFixture);

    // 2. Assert schema validity against canonical JSON Schema
    const validation = validateTutorialSpec(compiled);
    expect(validation.valid).toBe(true);
    expect(validation.errors).toEqual([]);
    expect(() => assertValidTutorialSpec(compiled)).not.toThrow();
  });

  it("generates correct Bezier cursor trajectories and click ripples across scenes", () => {
    const compiled = compileWorkflow(workflowFixture);

    // Scene 1: starts from viewport center (640, 400) to element center (1174, 24)
    const scene1 = compiled.scenes[0];
    expect(scene1.cursor?.path[0]).toEqual({ x: 640, y: 400 });
    expect(scene1.cursor?.path[3]).toEqual({ x: 1174, y: 24 });
    expect(scene1.cursor?.click_type).toBe("single");
    expect(scene1.cursor?.ripple).toEqual({
      radius: 24,
      color: "rgba(99, 102, 241, 0.4)",
    });

    // Scene 2: starts from previous target (1174, 24) to new target (1122, 63)
    const scene2 = compiled.scenes[1];
    expect(scene2.cursor?.path[0]).toEqual({ x: 1174, y: 24 });
    expect(scene2.cursor?.path[3]).toEqual({ x: 1122, y: 63 });

    // Scene 3: fill step has click ripple to focus input
    const scene3 = compiled.scenes[2];
    expect(scene3.cursor?.path[0]).toEqual({ x: 1122, y: 63 });
    expect(scene3.cursor?.path[3]).toEqual({ x: 712, y: 281 });
    expect(scene3.cursor?.click_type).toBe("single");
    expect(scene3.cursor?.ripple?.radius).toBe(24);
  });

  it("generates highlight rects and focal auto-zoom camera keyframes", () => {
    const compiled = compileWorkflow(workflowFixture);

    for (let i = 0; i < compiled.scenes.length; i++) {
      const scene = compiled.scenes[i];
      const sourceStep = workflowFixture.steps[i];

      // Highlight bbox matches source step target bbox
      expect(scene.highlight?.bbox).toEqual(sourceStep.target.bbox);
      expect(scene.highlight?.style).toBe("pulsing_ring");
      expect(scene.highlight?.padding).toBe(8);
      expect(scene.highlight?.color).toBe("#4f46e5");

      // Camera scale and center match target element
      const bbox = sourceStep.target.bbox!;
      const expectedCenterX = Math.round((bbox[0] + bbox[2] / 2) * 10) / 10;
      const expectedCenterY = Math.round((bbox[1] + bbox[3] / 2) * 10) / 10;

      expect(scene.camera?.scale).toBe(1.35);
      expect(scene.camera?.center).toEqual({ x: expectedCenterX, y: expectedCenterY });
      expect(scene.camera?.easing).toBe("cubic-bezier(0.22, 1, 0.36, 1)");
      expect(scene.camera?.pan_duration_ms).toBe(450);
    }
  });

  it("preserves synchronous scroll coordinates on every step", () => {
    const compiled = compileWorkflow(workflowFixture);

    // Step 1..3 have scroll { x: 0, y: 0 }
    expect(compiled.scenes[0].scroll).toEqual({ x: 0, y: 0 });
    expect(compiled.scenes[1].scroll).toEqual({ x: 0, y: 0 });
    expect(compiled.scenes[2].scroll).toEqual({ x: 0, y: 0 });

    // Step 4 and 5 are scrolled below the fold
    expect(compiled.scenes[3].scroll).toEqual({ x: 0, y: 544 });
    expect(compiled.scenes[4].scroll).toEqual({ x: 0, y: 544 });
  });

  it("handles non-element steps (navigate, wait, key press) without target elements", () => {
    const workflowWithNavigate: VerifiedWorkflow = {
      ...workflowFixture,
      id: "77777777-7777-4000-8000-777777777777",
      steps: [
        {
          id: "step-nav-1",
          seq: 1,
          action: { type: "navigate", value: "/repo/create" },
          target: {},
          instruction_text: "Navigate to the repository creation page.",
          expected_state: {},
          observed_state: { url: "/repo/create" },
          verification: { result: "verified", method: ["url"], confidence: 1 },
          risk: "low",
          timing: { start_ms: 0, end_ms: 500 },
        },
      ],
    };

    const compiled = compileWorkflow(workflowWithNavigate);

    expect(compiled.scenes).toHaveLength(1);
    const scene = compiled.scenes[0];

    // Non-element steps must have null camera, cursor, and highlight per schema
    expect(scene.camera).toBeNull();
    expect(scene.cursor).toBeNull();
    expect(scene.highlight).toBeNull();
    expect(scene.scroll).toBeNull();
    expect(scene.action.type).toBe("navigate");
    expect(scene.action.value).toBe("/repo/create");

    assertValidTutorialSpec(compiled);
  });

  it("respects reduced motion mode (prefers-reduced-motion)", () => {
    const compiled = compileWorkflow(workflowFixture, {
      reducedMotion: true,
    });

    for (const scene of compiled.scenes) {
      // Camera scale clamped to 1.0, pan duration 0ms
      expect(scene.camera?.scale).toBe(1.0);
      expect(scene.camera?.pan_duration_ms).toBe(0);

      // Highlight uses solid_box instead of pulsing_ring
      expect(scene.highlight?.style).toBe("solid_box");

      // Cursor trajectory collapsed to instant jump
      expect(scene.cursor?.start_ms).toBe(0);
      expect(scene.cursor?.end_ms).toBe(0);
      const [p0, p1, p2, p3] = scene.cursor!.path;
      expect(p0).toEqual(p3);
      expect(p1).toEqual(p3);
      expect(p2).toEqual(p3);
    }

    assertValidTutorialSpec(compiled);
  });

  it("handles sensitive steps properly", () => {
    const sensitiveWorkflow: VerifiedWorkflow = {
      ...workflowFixture,
      id: "88888888-8888-4000-8000-888888888888",
      steps: [
        {
          ...workflowFixture.steps[0],
          sensitive: true,
          action: { type: "fill", value: "******" },
        },
      ],
    };

    const compiled = compileWorkflow(sensitiveWorkflow);

    expect(compiled.scenes[0].sensitive).toBe(true);
    expect(compiled.scenes[0].action.value).toBe("******");
    assertValidTutorialSpec(compiled);
  });

  it("generates heuristic word timings when generateWordTimings is enabled", () => {
    const compiled = compileWorkflow(workflowFixture, {
      generateWordTimings: true,
    });

    for (const scene of compiled.scenes) {
      expect(scene.caption.words).not.toBeNull();
      expect(scene.caption.words!.length).toBeGreaterThan(0);
      for (const w of scene.caption.words!) {
        expect(w.word).toBeTruthy();
        expect(w.end_ms).toBeGreaterThan(w.start_ms);
      }
    }

    assertValidTutorialSpec(compiled);
  });

  it("supports custom options (fps, cameraScale, panDuration, stepDurations)", () => {
    const compiled = compileWorkflow(workflowFixture, {
      fps: 60,
      cameraScale: 1.5,
      panDurationMs: 300,
      stepDurations: {
        1: 2000,
        2: 2500,
      },
    });

    expect(compiled.fps).toBe(60);
    expect(compiled.scenes[0].camera?.scale).toBe(1.5);
    expect(compiled.scenes[0].camera?.pan_duration_ms).toBe(300);
    expect(compiled.scenes[0].duration_ms).toBe(2000);
    expect(compiled.scenes[1].duration_ms).toBe(2500);

    assertValidTutorialSpec(compiled);
  });

  it("validates spec automatically when validate option is true", () => {
    const compiled = compileWorkflow(workflowFixture, { validate: true });
    expect(compiled.workflow_id).toBe(workflowFixture.id);
  });

  it("throws validation error for invalid workflow inputs", () => {
    // Missing steps
    expect(() =>
      compileWorkflow({ ...workflowFixture, steps: [] }),
    ).toThrowError(/Workflow must contain at least one step/);

    // Missing id
    expect(() =>
      compileWorkflow({ ...workflowFixture, id: "" }),
    ).toThrowError(/missing workflow id/);

    // Missing title
    expect(() =>
      compileWorkflow({ ...workflowFixture, title: "" }),
    ).toThrowError(/missing workflow title/);

    // Null object
    expect(() =>
      compileWorkflow(null as unknown as VerifiedWorkflow),
    ).toThrowError(/Invalid workflow/);
  });
});
