# Exporting openapi.json from FastAPI

- **Phase:** F (Sprint F2)
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** How do you export `app.openapi()` to a file? How do we make route response models be the generated models, so OpenAPI and the schemas can't drift?

## Findings
- Tested with FastAPI **0.142.2**, Pydantic **2.13.5** [verified locally]
- `app.openapi()` returns a dict; dumping it with `json.dumps(spec, indent=2, sort_keys=True)` gives **identical output on every call** [verified locally]
- FastAPI emits **OpenAPI 3.1.0** [verified locally]
- A route annotated `-> Workflow` (a generated model) produces `{"$ref": "#/components/schemas/Workflow"}`. Nested generated types (`Step`, `Action`, `Risk`) and the discriminated `RunEvent` union all appear under `components.schemas` [verified locally]
- FastAPI adds its own `HTTPValidationError` / `ValidationError` components. Its 422 body is `{"detail": [...]}`, which **differs from our `api-contract.md`** error shape `{"error": {code, message, details}}` [verified locally]
- SSE streams (`text/event-stream`) aren't described by OpenAPI, so event types stay covered by `events.schema.json` [verified locally: no event schema appears unless a route returns it]

## Recommendation
**Decision (Vishwas): export from FastAPI, check in CI.**
- `just export-openapi` writes `contracts/openapi.json` from `app.openapi()` (sorted keys, 2-space indent).
- Routes use generated contract models as return types, never hand-written duplicates.
- The CI `contracts-drift` job re-runs the export and fails on `git diff`.

**Decision (Vishwas): keep our contract's error format.** Add exception handlers for `RequestValidationError` (→ `validation_error`, 422), `HTTPException` and app errors, so every error returns `{"error": {code, message, details}}`. Also define an `ErrorResponse` schema in `contracts/` and use it in route `responses=`, so `openapi.json` documents the real shape instead of FastAPI's default.

Suggested plan change (needs confirmation): add the error handlers + `ErrorResponse` schema to issue #18 ("Export openapi.json from FastAPI"), or as a new small issue in Sprint F2.

## Open questions
- Whether to remove FastAPI's default `HTTPValidationError` from the spec once our handler replaces it (custom `openapi()` override), or leave it.

## Links
- https://fastapi.tiangolo.com/how-to/extending-openapi/
- https://fastapi.tiangolo.com/tutorial/handling-errors/#override-the-default-exception-handlers
