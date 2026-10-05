# Generating Pydantic models from JSON Schema

- **Phase:** F (Sprint F2)
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** How does `datamodel-code-generator` turn JSON Schema (draft 2020-12) into Pydantic v2 models? Which flags give clean output? Does it handle `$ref` across files?

## Findings
- Tested with datamodel-code-generator **0.83.0**, Pydantic **2.13.5**, mypy **2.4.0**, Python 3.12 [verified locally]
- Test schemas: `step` (enums, nested object, local `$defs`), `workflow` (`$ref` to `step.schema.json` in another file, `const` version), `events` (`oneOf` + `discriminator` on `type`) [verified locally]
- Output with the flags below [verified locally]:
  - one module per schema file (`step_schema.py`, `workflow_schema.py`, …); a `$ref` across files becomes an import (`from . import step_schema`)
  - enums become `Literal[...]`, `format: uuid` becomes `UUID`, `minimum`/`maximum` become `Field(ge=, le=)`
  - `additionalProperties: false` becomes `ConfigDict(extra="forbid")`, also in nested objects
  - `oneOf` + `discriminator` becomes `RootModel[A | B]` with `Field(discriminator="type")`
- Generated code passes **`mypy --strict` with the pydantic plugin** [verified locally]
- Runtime validation rejects: an unknown enum value, a bad UUID, `confidence > 1`, an unknown event `type`, and an extra field inside a nested step [verified locally]
- Output is **deterministic**: two runs give identical files. Only ruff's `.ruff_cache/` differs, and that's already git-ignored [verified locally]
- Without `--formatters`, version 0.83 prints a FutureWarning that default formatters will change. `--formatters ruff-format ruff-check` needs the `datamodel-code-generator[ruff]` extra [verified locally]
- The reverse direction (Pydantic → `model_json_schema()`) also produces a correct `oneOf` + `discriminator.mapping`, but no `$schema` / `$id` [verified locally]

Command that worked:

```
datamodel-codegen --input contracts/schemas --input-file-type jsonschema --output backend/app/contracts_gen \
  --output-model-type pydantic_v2.BaseModel --target-python-version 3.12 \
  --use-annotated --enum-field-as-literal all --use-union-operator --use-standard-collections \
  --field-constraints --use-double-quotes --disable-timestamp --use-title-as-name --extra-fields forbid \
  --formatters ruff-format ruff-check
```

## Recommendation
**Decision (Vishwas): JSON Schema is the source of truth.** Hand-written schemas in `contracts/schemas/`; Pydantic and TypeScript are both generated from them. It's language-neutral, Nachiketha can edit schemas without Python, and every schema keeps its `$id` and `version`. This matches the existing plan, so no ADR is needed.

- Give every schema a `title`. With `--use-title-as-name` it becomes the class name.
- Put shared enums (e.g. `Risk`) in `$defs`, so they become reusable types.
- Add `datamodel-code-generator[ruff]` as a backend dev dependency in a separate `build(deps)` PR.

## Open questions
- For Nachiketha's TS side: does `json-schema-to-typescript` handle the same cross-file `$ref` and `discriminator`? (His research, #11)
- Shared `$defs` across files (e.g. one `common.schema.json` for `Risk`, `Uuid`): not tested yet. Try it when writing the real schemas.

## Links
- https://github.com/koxudaxi/datamodel-code-generator
- https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions
- https://json-schema.org/draft/2020-12
