import { describe, expect, it } from "vitest";

import type {
  ActionType,
  BoundingBox,
  HealthResponse,
  Risk,
  RunEvent,
  Step,
  VerificationResult,
  Workflow,
  WorkflowStatus,
} from "@krama/contracts-ts";

describe("Contracts TypeScript Types", () => {
  it("allows constructing a complete valid Workflow matching the contract schema", () => {
    const step: Step = {
      id: "11111111-1111-4111-8111-111111111111",
      seq: 1,
      action: {
        type: "click" as ActionType,
        value: null,
      },
      target: {
        role: "button",
        name: "Create Repository",
        bbox: [100, 200, 80, 40] as BoundingBox,
      },
      instruction_text: "Click Create Repository button.",
      expected_state: {
        url_matches: "^/repo/created$",
        visible: [{ role: "heading", name: "Welcome" }],
      },
      observed_state: {
        url: "/repo/created",
        title: "Repository Created",
        screenshot: "artifacts/step-1.png",
      },
      verification: {
        result: "verified" as VerificationResult,
        method: ["aria", "url"],
        confidence: 0.99,
      },
      risk: "low" as Risk,
      sensitive: false,
      timing: {
        start_ms: 100,
        end_ms: 500,
      },
    };

    const workflow: Workflow = {
      id: "6f1c2a4e-1111-4b8a-9a1b-123456789abc",
      title: "Create a repository in Gitea",
      status: "verified" as WorkflowStatus,
      target: {
        app: "gitea",
        base_url: "http://localhost:3001",
      },
      confidence: 0.99,
      steps: [step],
    };

    expect(workflow.id).toBe("6f1c2a4e-1111-4b8a-9a1b-123456789abc");
    expect(workflow.status).toBe("verified");
    expect(workflow.steps).toHaveLength(1);
    expect(workflow.steps[0].action.type).toBe("click");
    expect(workflow.steps[0].target.bbox).toEqual([100, 200, 80, 40]);
  });

  it("discriminates RunEvent union variants properly", () => {
    function processEvent(event: RunEvent): string {
      switch (event.type) {
        case "step.verified":
          return `verified with confidence ${event.confidence} via ${event.method.join(",")}`;
        case "step.failed":
          return `failed on step ${event.step_seq}`;
        case "run.paused":
          return `paused: ${event.reason}`;
        case "run.started":
          return `started plan ${event.plan_id}`;
        case "step.started":
          return `starting ${event.instruction_text}`;
        case "step.action_done":
          return `action done on step ${event.step_seq}`;
        case "run.replanning":
          return `replanning attempt ${event.attempt}`;
        case "run.completed":
          return `completed ${event.workflow_id}`;
        case "run.failed":
          return `failed: ${event.error.code}`;
        default: {
          const _exhaustiveCheck: never = event;
          return _exhaustiveCheck;
        }
      }
    }

    const verifiedEvent: RunEvent = {
      type: "step.verified",
      run_id: "6f1c2a4e-1111-4b8a-9a1b-123456789abc",
      seq: 3,
      ts: "2026-10-06T12:00:00Z",
      step_seq: 1,
      method: ["url", "aria"],
      confidence: 0.95,
    };
    expect(processEvent(verifiedEvent)).toBe("verified with confidence 0.95 via url,aria");

    const pausedEvent: RunEvent = {
      type: "run.paused",
      run_id: "6f1c2a4e-1111-4b8a-9a1b-123456789abc",
      seq: 4,
      ts: "2026-10-06T12:00:01Z",
      step_seq: 2,
      reason: "captcha",
    };
    expect(processEvent(pausedEvent)).toBe("paused: captcha");
  });

  it("validates HealthResponse shape", () => {
    const health: HealthResponse = {
      status: "ok",
      version: "0.1.0",
    };
    expect(health.status).toBe("ok");
    expect(health.version).toBe("0.1.0");
  });
});
