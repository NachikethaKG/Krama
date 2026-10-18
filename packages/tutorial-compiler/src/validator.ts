import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import {
  commonSchema,
  stepSchema,
  tutorialSpecSchema,
  workflowSchema,
} from "./schema/index.js";
import type { TutorialSpec } from "./types.js";

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

let compiledValidator: ((data: unknown) => boolean) & { errors?: Array<{ instancePath?: string; message?: string }> | null } | null = null;

function getValidator() {
  if (!compiledValidator) {
    // Instantiate Ajv2020 for JSON Schema Draft 2020-12
    const AjvConstructor = (Ajv2020 as unknown as { default?: typeof Ajv2020 }).default || Ajv2020;
    const addFormatsFn = (addFormats as unknown as { default?: typeof addFormats }).default || addFormats;

    const ajv = new AjvConstructor({
      allErrors: true,
      allowUnionTypes: true,
      strict: false,
    });
    addFormatsFn(ajv);

    ajv.addSchema(commonSchema, "common.schema.json");
    ajv.addSchema(stepSchema, "step.schema.json");
    ajv.addSchema(workflowSchema, "workflow.schema.json");
    compiledValidator = ajv.compile(tutorialSpecSchema);
  }
  return compiledValidator;
}

/**
 * Validates any data object against the canonical tutorial-spec.schema.json.
 * Returns { valid: boolean, errors: string[] }.
 */
export function validateTutorialSpec(spec: unknown): ValidationResult {
  const validator = getValidator();
  const valid = Boolean(validator(spec));

  if (valid) {
    return { valid: true, errors: [] };
  }

  const errors = (validator.errors ?? []).map(
    (err: { instancePath?: string; message?: string }) =>
      `${err.instancePath || "#"}: ${err.message ?? "validation failed"}`
  );

  return {
    valid: false,
    errors,
  };
}

/**
 * Asserts that the input conforms strictly to tutorial-spec.schema.json.
 * Throws a descriptive Error listing all schema violations if invalid.
 */
export function assertValidTutorialSpec(spec: unknown): asserts spec is TutorialSpec {
  const result = validateTutorialSpec(spec);
  if (!result.valid) {
    throw new Error(
      `TutorialSpec validation failed:\n${result.errors.map((e) => `  - ${e}`).join("\n")}`
    );
  }
}
