# Validating fixtures against schemas with ajv

- **Phase:** F (Sprint F2)
- **Researched by:** Nachiketha (experiments run by Claude Code on Vishwas's laptop with Nachiketha present; decisions by Nachiketha)
- **Question(s):** How do you validate JSON fixtures against a schema with `ajv` (draft 2020-12 needs `ajv/dist/2020`)?

## Findings
- Versions: ajv **8.20.0**, ajv-formats **3.0.1** [verified locally]
- Setup that works: `new Ajv2020({ allErrors: true, strict: true, discriminator: true })` from `ajv/dist/2020.js`, `addFormats(ajv)`, then `ajv.addSchema(...)` for **every** schema file. Cross-file `$ref`s then resolve by `$id`, and you validate with `ajv.validate("workflow.schema.json", data)` [verified locally]
- Results [verified locally]:

| Case | Result |
|---|---|
| valid workflow | valid |
| `id: "nope"` | `/id must match format "uuid"` |
| extra field inside a nested step (through the cross-file `$ref`) | `/steps/0 must NOT have additional properties` |
| valid `run.paused` event | valid |
| `run.paused` without `reason` | `/ must have required property 'reason'` |
| unknown event `type` | `/ value of tag "type" must be in oneOf` |

- **Strict mode caught a real schema problem**: `strict mode: missing type "object" for keyword "discriminator" at "events.schema.json#"`. Adding `"type": "object"` to the union root fixed it, and both generators produced exactly the same output afterwards (Pydantic `RootModel` with `discriminator="type"`, TS `type RunEvent = StepVerified | RunPaused`) [verified locally]
- Without `ajv-formats`, `format: uuid` / `date-time` aren't checked; `strict` mode then errors on unknown formats [unverified: not run without ajv-formats]

## Recommendation
**Decision (Nachiketha): ajv strict mode on**, with `ajv-formats` and `discriminator: true`.
- Fixture test (#21) loads every file in `contracts/schemas/` with `addSchema`, then validates every file in `contracts/fixtures/` against the schema named in the fixture's file name or a small mapping.
- The test should also confirm that a deliberately broken fixture fails, so it can't silently pass.
- Schema rule for both sides: union roots declare `"type": "object"`.

## Open questions
- Fixture-to-schema mapping: by file name (`*.workflow.json`) or a `$schema`-style field in each fixture? Decide in #20 / #21.

## Links
- https://ajv.js.org/json-schema.html#draft-2020-12
- https://ajv.js.org/strict-mode.html
- https://ajv.js.org/json-schema.html#discriminator
- https://github.com/ajv-validator/ajv-formats
