# Generating TypeScript types from JSON Schema

- **Phase:** F (Sprint F2)
- **Researched by:** Nachiketha (experiments run by Claude Code on Vishwas's laptop with Nachiketha present; decisions by Nachiketha)
- **Question(s):** Compare `json-schema-to-typescript`, `quicktype` and `openapi-typescript`. Which handles `$ref` across files and `oneOf` (for event types) best?

## Findings
- Versions tested: json-schema-to-typescript **16.0.0**, quicktype **26.0.0**, openapi-typescript **7.13.0**, TypeScript **5.9.3** (the frontend's major version) [verified locally]
- Same test schemas as the Python research: `step` (enums, local `$defs`), `workflow` (`$ref` to `step.schema.json`), `events` (`oneOf` + `discriminator`) [verified locally]
- The deciding test was a `switch (e.type)` that reads `e.reason` / `e.confidence`, compiled with `tsc --strict` [verified locally]:

| Tool | Event union narrows? | Cross-file `$ref` | Notes |
|---|---|---|---|
| json-schema-to-typescript (one file per schema) | ✅ | ⚠️ inlines a **copy** of `Step` into `workflow.d.ts`; the copy loses the `Risk` name | two `Step` declarations clash if re-exported together |
| json-schema-to-typescript (**one bundled root**) | ✅ | ✅ every type emitted **once** | a tiny root schema that `$ref`s every file; output in one file |
| quicktype | ❌ | ✅ | merges the union into one interface with **all fields optional**: `error TS18048: 'e.reason' is possibly 'undefined'` |
| openapi-typescript (from FastAPI's `openapi.json`) | ✅ | ✅ | also types every route (`paths`), but only sees types used by routes, so live events are missing |

- Without a `title`, a shared enum in `$defs` becomes an inline union in json-schema-to-typescript; **with `"title": "Risk"` it becomes `export type Risk = …`** [verified locally]. This is the same rule as the Python generator (`--use-title-as-name`).
- Number constraints (`minimum`/`maximum`) and `format: uuid` aren't expressible in TS types (they become `number` / `string`); runtime validation covers them (see phase-f-nachiketha-fixture-validation-ajv.md) [verified locally]

Bundled generation that worked (Node, `json-schema-to-typescript` API):

```js
const files = readdirSync("contracts/schemas").filter((f) => f.endsWith(".schema.json"));
const root = {
  title: "KramaContracts", type: "object", additionalProperties: false,
  properties: Object.fromEntries(files.map((f) => [f.replace(".schema.json", ""), { $ref: f }])),
};
const ts = await compile(root, "KramaContracts", {
  cwd: "contracts/schemas", additionalProperties: false, unreachableDefinitions: true,
  bannerComment: "// GENERATED - do not edit. Run `just gen-contracts`.",
});
writeFileSync("packages/contracts-ts/src/index.ts", ts);
```

## Recommendation
**Decision (Nachiketha): json-schema-to-typescript with one bundled root**, writing every contract type once to `packages/contracts-ts/src/index.ts`. The API client in `frontend/lib/api.ts` stays a small hand-written class typed with these types. No openapi-typescript for now; revisit if the client grows large enough that typed route paths are worth a second generator.

Schema rules for both sides (agreed with the Python research):
- every shared `$defs` entry and every schema file has a **`title`** (it becomes the type/class name)
- union roots (`oneOf` + `discriminator`) also declare **`"type": "object"`** (required by ajv strict mode; Python and TS output unchanged, see the ajv note)

## Open questions
- `KramaContracts` (the helper root type) appears in the output; harmless, but we could strip it in the generator script.

## Links
- https://github.com/bcherny/json-schema-to-typescript
- https://github.com/glideapps/quicktype
- https://openapi-ts.dev/
