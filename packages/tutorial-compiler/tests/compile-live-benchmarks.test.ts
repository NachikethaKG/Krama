import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { compileWorkflow } from "../src/compiler.js";
import type { VerifiedWorkflow } from "../src/types.js";
import { assertValidTutorialSpec, validateTutorialSpec } from "../src/validator.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "../../..");
const RUNS_DIR = path.resolve(ROOT_DIR, "data/artifacts/runs");
const OUTPUT_DIR = path.resolve(ROOT_DIR, "data/artifacts/tutorial-specs");

interface RunLogStep {
  seq: number;
  section?: string;
  instruction_text: string;
  action: {
    type: string;
    value: string | null;
  };
  target: {
    role: string | null;
    name: string | null;
    selector: string | null;
  };
  result?: {
    action: string;
    ok: boolean;
    duration_ms: number;
    bbox: [number, number, number, number] | null;
    scroll: { x: number; y: number } | null;
  };
  observed?: {
    url: string;
    title: string;
    screenshot_path?: string;
  };
  verification?: {
    verification?: {
      result: string;
      confidence?: number;
    };
  };
}

interface RunLog {
  run_id: string;
  task: string;
  target_url: string;
  status: string;
  steps: RunLogStep[];
}

function runLogToVerifiedWorkflow(runLog: RunLog): VerifiedWorkflow {
  // Only include task steps (skip precondition login steps)
  const taskSteps = runLog.steps.filter((s) => s.section !== "precondition");

  const workflowSteps = taskSteps.map((s, index) => {
    const seq = index + 1;
    const bbox = s.result?.bbox ?? null;
    const scroll = s.result?.scroll ?? { x: 0, y: 0 };

    return {
      id: `00000000-0000-4000-8000-${String(seq).padStart(12, "0")}`,
      workflow_id: runLog.run_id,
      seq,
      action: {
        type: s.action.type as any,
        value: s.action.value ?? null,
      },
      target: {
        role: s.target.role ?? null,
        name: s.target.name ?? null,
        selector: s.target.selector ?? null,
        bbox,
        scroll,
      },
      instruction_text: s.instruction_text,
      before_state: {
        url: s.observed?.url ?? "/",
        title: s.observed?.title ?? "Gitea",
        screenshot: s.observed?.screenshot_path ?? null,
      },
      observed_state: {
        url: s.observed?.url ?? "/",
        title: s.observed?.title ?? "Gitea",
        screenshot: s.observed?.screenshot_path ?? null,
      },
      verification: {
        result: (s.verification?.verification?.result ?? "verified") as any,
        confidence: s.verification?.verification?.confidence ?? 1.0,
      },
      timing: {
        start_ms: index * 1500,
        end_ms: (index + 1) * 1500,
      },
    };
  });

  return {
    id: runLog.run_id,
    version: "1.0",
    task_id: runLog.run_id,
    run_id: runLog.run_id,
    title: runLog.task,
    task: runLog.task,
    status: "verified",
    confidence: 1.0,
    viewport: {
      width: 1280,
      height: 800,
      device_scale_factor: 1.0,
    },
    target_app: "gitea",
    target_url: runLog.target_url,
    steps: workflowSteps as any,
  };
}

describe("Compile Live Benchmark Workflows to Tutorial Specs", () => {
  const liveRunIds = [
    { id: "72a23429-38f2-4c2a-a784-32ca2e5e3387", task: "create-repo" },
    { id: "72f89363-569f-4be8-acb2-b6df81bdb41e", task: "create-issue" },
    { id: "c65a9093-8c87-434d-a672-a2eca1812c8a", task: "create-branch" },
    { id: "5de44648-b0c7-4a01-b62c-fe36f54610a1", task: "add-file" },
    { id: "0005bf56-72cb-41eb-84c5-c065d7347acc", task: "repo-settings" },
  ];

  if (!existsSync(OUTPUT_DIR)) {
    mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  for (const { id: runId, task: taskName } of liveRunIds) {
    it(`compiles live run ${taskName} (${runId}) into a validated TutorialSpec`, () => {
      const logPath = path.join(RUNS_DIR, runId, "run-log.json");
      expect(existsSync(logPath), `Log must exist at ${logPath}`).toBe(true);

      const raw = readFileSync(logPath, "utf-8");
      const runLog: RunLog = JSON.parse(raw);
      expect(runLog.status).toBe("verified");

      const workflow = runLogToVerifiedWorkflow(runLog);
      expect(workflow.steps.length).toBeGreaterThan(0);

      // Compile to TutorialSpec using pure TS compiler
      const spec = compileWorkflow(workflow, { generateWordTimings: true });

      // Assert spec structure
      expect(spec.version).toBe("1.0");
      expect(spec.workflow_id).toBe(workflow.id);
      expect(spec.scenes.length).toBe(workflow.steps.length);
      expect(spec.viewport).toEqual({
        width: 1280,
        height: 800,
        device_scale_factor: 1.0,
      });

      // Verify each scene has required properties
      for (const scene of spec.scenes) {
        expect(scene.id).toBeDefined();
        expect(scene.step_seq).toBeGreaterThan(0);
        expect(scene.caption.text.length).toBeGreaterThan(0);

        if (scene.highlight && scene.cursor) {
          // Verify cubic Bezier trajectory has 4 points
          expect(scene.cursor.path.length).toBe(4);
          expect(scene.cursor.click_type).toBeDefined();
          expect(scene.cursor.ripple).toBeDefined();

          // Verify camera zoom keyframe exists
          expect(scene.camera).toBeDefined();
          if (scene.camera) {
            expect(scene.camera.scale).toBeGreaterThanOrEqual(1.0);
            expect(scene.camera.center.x).toBeGreaterThan(0);
            expect(scene.camera.center.y).toBeGreaterThan(0);
          }
        }
      }

      // Assert full JSON schema validation against tutorial-spec.schema.json
      const validation = validateTutorialSpec(spec);
      expect(validation.valid, `Validation errors: ${validation.errors.join(", ")}`).toBe(true);
      assertValidTutorialSpec(spec);

      // Write compiled spec to artifacts directory
      const outPath = path.join(OUTPUT_DIR, `${taskName}.json`);
      writeFileSync(outPath, JSON.stringify(spec, null, 2), "utf-8");
      expect(existsSync(outPath)).toBe(true);
    });
  }
});
