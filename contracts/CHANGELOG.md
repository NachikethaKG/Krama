# Contracts changelog

Every change to `contracts/` is listed here. Additive change = minor version bump; breaking change = major bump + ADR.

## 1.0 (#14)

First version of the API schemas.

- `common.schema.json`: `Action`, `ActionType`, `Target`, `ElementRef`, `FieldValue`, `ExpectedState` (`url_matches`, `title_contains`, `visible`, `absent`, `field_values`, `checked`), `Risk`, `VerificationMethod`, `BoundingBox`, `ErrorCode`, `ApiError`, `ErrorResponse`
- `task.schema.json`: `Task`, `TaskStatus`, `Interpretation`, `TaskCreateRequest`, `TaskClarifyRequest`
- `plan.schema.json`: `Plan`, `PlanStatus`, `PlannedStep`, `PlanUpdateRequest`, `PlanApproveRequest`, `PlanRejectRequest`
- `run.schema.json`: `Run`, `RunStatus`, `RunPage`, `RunConfirmRequest`
- `events.schema.json`: `RunEvent` = `run.started`, `step.started`, `step.action_done`, `step.verified`, `step.failed`, `run.replanning`, `run.paused`, `run.completed`, `run.failed`

Changes from the draft in `docs/api-contract.md`:
- `POST /runs/{id}/confirm` takes `step_seq` (not `step_id`), matching the events, which identify steps by `seq`.
- SSE keep-alives are comment lines (`: keep-alive`), not a `heartbeat` event. `EventSource` ignores comments, so the frontend needs no handling.
- `Task`, `Plan` and `Run` have `created_at`.
