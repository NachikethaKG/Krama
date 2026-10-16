// The mock seam must be contract-valid (docs/architecture.md §4): every event the mock client can emit, and the
// plans / runs / tasks it returns, are validated against contracts/schemas with Ajv.
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import type { RunEvent } from "@krama/contracts-ts";

import { MockApiClient } from "@/lib/api";
import {
  giteaBlockedEventsFixture,
  giteaEventsFixture,
  giteaFailedEventsFixture,
  giteaPausedEventsFixture,
  giteaReplanEventsFixture,
  giteaReplanReviewEventsFixture,
  replanProposedPlanFixture,
} from "@/lib/fixtures";

const SCHEMAS_DIR = path.resolve(__dirname, "../../../contracts/schemas");
const UUID = "6f1c2a4e-9999-4b8a-9a1b-123456789abc";

function setupAjv(): Ajv2020 {
  const ajv = new Ajv2020({ allErrors: true, strict: true, allowUnionTypes: true, discriminator: true });
  addFormats(ajv);
  for (const file of readdirSync(SCHEMAS_DIR).filter((f) => f.endsWith(".schema.json")).sort()) {
    ajv.addSchema(JSON.parse(readFileSync(path.join(SCHEMAS_DIR, file), "utf-8")));
  }
  return ajv;
}

const ajv = setupAjv();
const validateEvent = ajv.getSchema("events.schema.json")!;
const validatePlan = ajv.getSchema("plan.schema.json")!;
const validateRun = ajv.getSchema("run.schema.json")!;
const validateTask = ajv.getSchema("task.schema.json")!;

function expectValid(validate: typeof validateEvent, data: unknown, label: string) {
  const ok = validate(data);
  expect(ok, `${label}: ${JSON.stringify(validate.errors, null, 2)}\n${JSON.stringify(data)}`).toBe(true);
}

const INLINE_FIXTURES: Record<string, RunEvent[]> = {
  success: giteaEventsFixture,
  paused: giteaPausedEventsFixture,
  failed: giteaFailedEventsFixture,
  replan: giteaReplanEventsFixture,
  "replan-review": giteaReplanReviewEventsFixture,
  blocked: giteaBlockedEventsFixture,
};

/** Mock route ids (e.g. "paused") are readable aliases, not UUIDs: swap them for a UUID to check the shape. */
function withUuidIds<T extends object>(obj: T, keys: string[]): T {
  const copy = { ...obj } as Record<string, unknown>;
  for (const k of keys) if (typeof copy[k] === "string") copy[k] = UUID;
  return copy as T;
}

describe("mock fixtures are contract-valid", () => {
  for (const [name, events] of Object.entries(INLINE_FIXTURES)) {
    it(`every inline "${name}" event validates against events.schema.json`, () => {
      expect(events.length).toBeGreaterThan(0);
      for (const event of events) expectValid(validateEvent, event, `${name} seq ${event.seq}`);
      const seqs = events.map((e) => e.seq);
      expect(seqs).toEqual([...seqs].sort((a, b) => a - b));
    });
  }

  it("contains no non-contract event types or fields", () => {
    const all = Object.values(INLINE_FIXTURES).flat();
    expect(all.some((e) => (e.type as string) === "run.stopped")).toBe(false);
    expect(all.some((e) => "expected_screenshot_url" in e)).toBe(false);
  });

  it("the blocked fixture is a policy stop: run.failed with details.reason policy_stop", () => {
    const last = giteaBlockedEventsFixture.at(-1)!;
    expect(last.type).toBe("run.failed");
    expect(last.type === "run.failed" && last.error.details).toMatchObject({ reason: "policy_stop", policy_reason: "captcha" });
  });

  it("the replan_review pause points at a contract-valid proposed plan", () => {
    const pause = giteaReplanReviewEventsFixture.at(-1)!;
    expect(pause.type === "run.paused" && pause.plan_id).toBe(replanProposedPlanFixture.id);
    expectValid(validatePlan, withUuidIds(replanProposedPlanFixture, ["task_id"]), "proposed plan");
  });

  it("the schema rejects the old non-contract shapes (drift guard)", () => {
    const failed = giteaFailedEventsFixture.find((e) => e.type === "step.failed")!;
    expect(validateEvent({ ...failed, expected_screenshot_url: "/x.png" })).toBe(false);
    expect(validateEvent({ type: "run.stopped", run_id: UUID, seq: 1, ts: "2026-10-06T12:00:00Z" })).toBe(false);
  });

  for (const scenario of ["default", "paused", "replan", "replan-review", "failed", "blocked"]) {
    it(`events the mock streams for "${scenario}" (incl. after allow) are contract-valid`, async () => {
      const client = new MockApiClient();
      const seen: RunEvent[] = [];
      for await (const event of client.streamRunEvents(scenario, { speed: 1000 })) {
        seen.push(event);
        if (event.type === "run.paused") void client.confirmRun(scenario, event.step_seq, "allow");
      }
      for (const event of seen) expectValid(validateEvent, event, `${scenario} seq ${event.seq}`);
      expect(["run.completed", "run.failed", "run.cancelled"]).toContain(seen.at(-1)?.type);
    });
  }

  it("deny produces a contract-valid run.cancelled", async () => {
    const client = new MockApiClient();
    const seen: RunEvent[] = [];
    for await (const event of client.streamRunEvents("paused", { speed: 1000 })) {
      seen.push(event);
      if (event.type === "run.paused") void client.confirmRun("paused", event.step_seq, "deny");
    }
    const last = seen.at(-1)!;
    expectValid(validateEvent, last, "cancelled");
    expect(last.type === "run.cancelled" && last.reason).toBe("confirmation_denied");
  });

  it("mock plans, runs and tasks have the contract shape", async () => {
    const client = new MockApiClient();
    expectValid(validatePlan, withUuidIds(await client.getPlan("paused"), ["id", "task_id"]), "plan");
    expectValid(validateRun, withUuidIds(await client.getRun("paused"), ["id", "plan_id"]), "run");
    expectValid(validateRun, withUuidIds(await client.approvePlan("default", 1), ["id", "plan_id"]), "approved run");
    expectValid(validateTask, withUuidIds(await client.createTask("Create a repo", "http://localhost:3001"), ["id"]), "task");
    expectValid(validateTask, withUuidIds(await client.getTask("mock-task-id"), ["id", "plan_id"]), "planned task");
  });
});
