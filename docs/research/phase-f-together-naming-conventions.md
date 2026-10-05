# Naming conventions for contracts

- **Phase:** F (Sprint F2)
- **Researched by:** Together. Proposed by Vishwas; **agreed by Nachiketha** (2026-10-05, see PR #141).
- **Question(s):** Agree on naming: `snake_case` JSON, ids as UUID strings, timestamps as ISO-8601 UTC.

## Findings
- datamodel-code-generator maps `format: uuid` → `UUID` [verified locally, see phase-f-vishwas-pydantic-generation.md]
- FastAPI, Pydantic and Postgres are all `snake_case` by default. camelCase JSON would need aliases on every generated Python model [unverified: no camelCase generation was tested]
- The Gitea walkthrough showed that full URLs tie a workflow to one host (`localhost:3001`). Paths (`/repo/create`) work for any base URL [verified locally: all observed URLs are the same paths under the base URL]

## Recommendation
Agreed by Vishwas and Nachiketha:

| Thing | Convention | Example |
|---|---|---|
| JSON keys | `snake_case` | `run_id`, `instruction_text`, `expected_state` |
| Ids | UUID strings (`format: uuid`) | `"6f1c2a4e-1111-4b8a-9a1b-123456789abc"` |
| Timestamps | ISO-8601 **UTC** with `Z` (`format: date-time`) | `"2026-10-05T14:03:22Z"` |
| Durations / offsets | integer milliseconds, key ends in `_ms` | `start_ms`, `duration_ms` |
| Enum values | lowercase `snake_case`; event types dotted | `"needs_clarification"`, `"step.verified"` |
| URLs in `expected_state` | **path regex**, never scheme + host | `"url_matches": "^/repo/create$"` |
| Schema files | `<name>.schema.json`, `title` in PascalCase (becomes the class name) | `step.schema.json` → `Step` |
| Schema version | `"version": "<major>.<minor>"` const | `"1.0"` |

## Open questions
- None. Nachiketha chose snake_case in TS too (generated types match fixtures 1:1, no conversion layer).

## Links
- https://json-schema.org/understanding-json-schema/reference/string#dates-and-times
- https://www.rfc-editor.org/rfc/rfc3339
