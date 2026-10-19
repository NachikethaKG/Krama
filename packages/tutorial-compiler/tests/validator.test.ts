import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { TutorialSpec } from "../src/types.js";
import { assertValidTutorialSpec, validateTutorialSpec } from "../src/validator.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const FIXTURE_PATH = path.resolve(
  __dirname,
  "../../../contracts/fixtures/tutorial-spec/gitea-create-repo.json",
);

describe("validateTutorialSpec", () => {
  it("validates the canonical gitea-create-repo fixture successfully", () => {
    const raw = readFileSync(FIXTURE_PATH, "utf-8");
    const fixture: TutorialSpec = JSON.parse(raw);

    const result = validateTutorialSpec(fixture);
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual([]);

    expect(() => assertValidTutorialSpec(fixture)).not.toThrow();
  });

  it("fails when top-level required properties are missing", () => {
    const invalid = {
      version: "1.0",
      title: "Missing fields",
    };

    const result = validateTutorialSpec(invalid);
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
    expect(result.errors.some((e) => e.includes("workflow_id"))).toBe(true);

    expect(() => assertValidTutorialSpec(invalid)).toThrowError(
      /TutorialSpec validation failed/,
    );
  });

  it("fails when scenes array is empty", () => {
    const invalid = {
      version: "1.0",
      workflow_id: "6f1c2a4e-1111-4b8a-9a1b-123456789abc",
      title: "No scenes",
      viewport: { width: 1280, height: 800 },
      total_duration_ms: 0,
      scenes: [],
    };

    const result = validateTutorialSpec(invalid);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("scenes"))).toBe(true);
  });

  it("fails when an invalid click_type is given", () => {
    const raw = readFileSync(FIXTURE_PATH, "utf-8");
    const fixture = JSON.parse(raw);
    fixture.scenes[0].cursor.click_type = "invalid_click_type";

    const result = validateTutorialSpec(fixture);
    expect(result.valid).toBe(false);
    expect(result.errors.some((e) => e.includes("click_type") || e.includes("enum"))).toBe(true);
  });
});
