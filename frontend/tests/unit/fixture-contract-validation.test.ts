import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const ROOT = path.resolve(__dirname, "../../..");
const SCHEMAS_DIR = path.resolve(ROOT, "contracts/schemas");
const FIXTURES_DIR = path.resolve(ROOT, "contracts/fixtures");

function setupAjv(): Ajv2020 {
  const ajv = new Ajv2020({ allErrors: true, strict: true, discriminator: true });
  addFormats(ajv);

  const schemaFiles = readdirSync(SCHEMAS_DIR)
    .filter((f) => f.endsWith(".schema.json"))
    .sort();

  for (const file of schemaFiles) {
    const raw = readFileSync(path.join(SCHEMAS_DIR, file), "utf-8");
    const schema = JSON.parse(raw);
    ajv.addSchema(schema);
  }

  return ajv;
}

describe("Fixture contract validation (Ajv Draft 2020-12)", () => {
  const ajv = setupAjv();
  const workflowValidator = ajv.getSchema("workflow.schema.json")!;
  const eventValidator = ajv.getSchema("events.schema.json")!;

  it("compiles workflow and events schemas successfully", () => {
    expect(workflowValidator).toBeDefined();
    expect(eventValidator).toBeDefined();
  });

  it("validates every workflow JSON fixture in contracts/fixtures/ without error", () => {
    const fixtureFiles = readdirSync(FIXTURES_DIR)
      .filter((f) => f.endsWith(".json"))
      .sort();

    expect(fixtureFiles.length).toBeGreaterThan(0);

    for (const fixtureFile of fixtureFiles) {
      const fullPath = path.join(FIXTURES_DIR, fixtureFile);
      const raw = readFileSync(fullPath, "utf-8");
      const data = JSON.parse(raw);

      const valid = workflowValidator(data);
      expect(valid, `Validation failed for ${fixtureFile}: ${JSON.stringify(workflowValidator.errors, null, 2)}`).toBe(
        true
      );
      expect(workflowValidator.errors).toBeNull();
    }
  });

  it("validates every event frame in gitea-create-repo-events.sse against events.schema.json", () => {
    const ssePath = path.join(FIXTURES_DIR, "gitea-create-repo-events.sse");
    const rawSse = readFileSync(ssePath, "utf-8");
    const blocks = rawSse
      .trim()
      .split("\n\n")
      .map((b) => b.trim())
      .filter(Boolean);

    expect(blocks.length).toBe(17);

    for (const block of blocks) {
      const lines = block.split("\n");
      const dataLine = lines.find((l) => l.startsWith("data: "));
      expect(dataLine, `Missing 'data: ' line in SSE frame: ${block}`).toBeDefined();

      const eventData = JSON.parse(dataLine!.slice("data: ".length));
      const valid = eventValidator(eventData);
      expect(
        valid,
        `Validation failed for event frame:\n${block}\nErrors: ${JSON.stringify(eventValidator.errors, null, 2)}`
      ).toBe(true);
      expect(eventValidator.errors).toBeNull();
    }
  });

  describe("Negative tests (drift detection)", () => {
    it("fails when workflow is missing a required top-level property (status)", () => {
      const validFixture = JSON.parse(readFileSync(path.join(FIXTURES_DIR, "valid_workflow.json"), "utf-8"));
      const broken = { ...validFixture };
      delete broken.status;

      const valid = workflowValidator(broken);
      expect(valid).toBe(false);
      expect(workflowValidator.errors?.some((e) => e.params.missingProperty === "status")).toBe(true);
    });

    it("fails when workflow has an invalid enum value for status", () => {
      const validFixture = JSON.parse(readFileSync(path.join(FIXTURES_DIR, "valid_workflow.json"), "utf-8"));
      const broken = { ...validFixture, status: "completed" };

      const valid = workflowValidator(broken);
      expect(valid).toBe(false);
      expect(workflowValidator.errors?.some((e) => e.keyword === "enum")).toBe(true);
    });

    it("fails when a step has an invalid risk enum", () => {
      const validFixture = JSON.parse(
        readFileSync(path.join(FIXTURES_DIR, "gitea-create-repo-workflow.json"), "utf-8")
      );
      const broken = JSON.parse(JSON.stringify(validFixture));
      broken.steps[0].risk = "critical";

      const valid = workflowValidator(broken);
      expect(valid).toBe(false);
      expect(workflowValidator.errors?.some((e) => e.instancePath.includes("risk"))).toBe(true);
    });

    it("fails when step target bounding box has incorrect number of elements", () => {
      const validFixture = JSON.parse(
        readFileSync(path.join(FIXTURES_DIR, "gitea-create-repo-workflow.json"), "utf-8")
      );
      const broken = JSON.parse(JSON.stringify(validFixture));
      broken.steps[0].target.bbox = [100, 200, 300]; // requires 4 elements

      const valid = workflowValidator(broken);
      expect(valid).toBe(false);
    });

    it("fails when workflow contains unexpected additional properties on closed objects", () => {
      const validFixture = JSON.parse(readFileSync(path.join(FIXTURES_DIR, "valid_workflow.json"), "utf-8"));
      const broken = { ...validFixture, extra_property: "not_allowed" };

      const valid = workflowValidator(broken);
      expect(valid).toBe(false);
      expect(workflowValidator.errors?.some((e) => e.keyword === "additionalProperties")).toBe(true);
    });

    it("fails when an SSE event has an unrecognized discriminator type", () => {
      const brokenEvent = {
        type: "unknown.event",
        run_id: "6f1c2a4e-2222-4b8a-9a1b-123456789abc",
        seq: 1,
        ts: "2026-10-06T12:00:00Z",
      };

      const valid = eventValidator(brokenEvent);
      expect(valid).toBe(false);
    });

    it("fails when a run.paused event has an invalid pause reason", () => {
      const brokenEvent = {
        type: "run.paused",
        run_id: "6f1c2a4e-2222-4b8a-9a1b-123456789abc",
        seq: 4,
        ts: "2026-10-06T12:00:01Z",
        step_seq: 2,
        reason: "unsupported_reason",
      };

      const valid = eventValidator(brokenEvent);
      expect(valid).toBe(false);
      expect(eventValidator.errors?.some((e) => e.keyword === "enum")).toBe(true);
    });
  });
});
