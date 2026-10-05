# contracts/

The source of truth between `backend/` and `frontend/`. Changing anything here is a **contract change**: open a `contract-change` issue and get both owners' approval ([process](../docs/development-workflow.md#7-contract-changes)). Human-readable version: [`docs/api-contract.md`](../docs/api-contract.md).

| Path | What |
|---|---|
| `schemas/*.schema.json` | JSON Schema (draft 2020-12), hand-written. Pydantic and TypeScript types are generated from these. |
| `openapi.json` | REST contract, exported from FastAPI (#18) |
| `fixtures/` | Example data, validated against the schemas in CI (#20, #21) |
| `CHANGELOG.md` | Every contract change, with its version |

## Schemas

| File | Contents | Owner of the issue |
|---|---|---|
| `common.schema.json` | Shared building blocks: `Action`, `Target`, `ElementRef`, `ExpectedState`, `Risk`, `VerificationMethod`, `BoundingBox`, `ApiError`, `ErrorResponse` | both |
| `task.schema.json` | `Task` + request bodies | #14 |
| `plan.schema.json` | `Plan`, `PlannedStep` + request bodies | #14 |
| `run.schema.json` | `Run`, `RunPage`, `RunConfirmRequest` | #14 |
| `events.schema.json` | `RunEvent`: union of the 9 live-view event types | #14 |
| `workflow.schema.json`, `step.schema.json` | Verified workflow and executed steps | #15 |

## Rules (each one came out of research; see `docs/research/phase-f-*`)

1. **Draft 2020-12**, `$id` = the file name, cross-file references as `other.schema.json#/$defs/Name`.
2. **Every schema and every `$defs` entry has a `title`.** It becomes the class / type name in Python and TypeScript; without it, names get lost.
3. **Shared pieces go in `common.schema.json`**, never copied between files.
4. **Union roots** (`oneOf` + `discriminator`) also declare `"type": "object"` (ajv strict mode requires it).
5. **Objects are closed**: `"additionalProperties": false`.
6. **Nullable fields** use a type list, `"type": ["string", "null"]`, or `oneOf: [{$ref}, {type: null}]` for objects.
7. **Naming** ([agreed](../docs/research/phase-f-together-naming-conventions.md)): `snake_case` keys, UUID string ids, ISO-8601 UTC timestamps with `Z`, `*_ms` integer durations, lowercase enum values, dotted event types (`step.verified`), **URL paths, not full URLs**, in `expected_state`.
8. The **schema version** lives in each file's `$comment` (`v1.0`) and in `CHANGELOG.md`. Additive change = minor bump; breaking change = major bump + ADR.

## Known limits of the generated code

- `minProperties` (e.g. "`ExpectedState` needs at least one condition") is enforced by ajv but **not** by the generated Pydantic models. Backend code must check it where it matters (planner, verifier).
- Numeric ranges and formats (`uuid`, `date-time`, `uri`) are runtime checks; TypeScript types only say `string` / `number`.

## Validators and generators

- **ajv** (fixtures, #21): `new Ajv2020({ strict: true, allowUnionTypes: true, discriminator: true })` + `ajv-formats`. `allowUnionTypes` is needed for rule 6.
- **Python** (#16): `datamodel-code-generator` with `--use-title-as-name --use-type-alias --enum-field-as-literal all --extra-fields forbid`. `--use-type-alias` makes `Risk` a plain `Literal` alias, so `step.risk == "low"` works.
- **TypeScript** (#17): `json-schema-to-typescript`, one bundled root over all files, so every type is emitted once.
