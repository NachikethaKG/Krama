import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { commonSchema, stepSchema, tutorialSpecSchema, workflowSchema } from "../src/schema/index.js";

// The validator embeds copies of the contract schemas (no filesystem access in the browser). They had drifted
// from contracts 1.1 to 1.21 unnoticed (#471): this keeps them equal to contracts/schemas.
const SCHEMAS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../contracts/schemas");

const read = (name: string): unknown => JSON.parse(readFileSync(path.join(SCHEMAS, name), "utf-8"));

describe("embedded schemas", () => {
  it.each([
    ["common.schema.json", commonSchema],
    ["step.schema.json", stepSchema],
    ["workflow.schema.json", workflowSchema],
    ["tutorial-spec.schema.json", tutorialSpecSchema],
  ])("%s matches contracts/schemas", (name, embedded) => {
    expect(embedded).toEqual(read(name));
  });
});
