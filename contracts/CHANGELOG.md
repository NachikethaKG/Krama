# Contracts changelog

Every change to `contracts/` is listed here. Additive change = minor version bump; breaking change = major bump + ADR.

## 1.3 (#20)

Added hand-crafted, realistic sample fixtures for the "create a repository in local Gitea" workflow.

- Added `contracts/fixtures/gitea-create-repo-workflow.json`:
  - Complete 5-step Verified Workflow (`Workflow` schema v1) based on Together research walkthrough (`assets/phase-f-gitea-create-repo/walkthrough.json`).
  - Covers navigating the `+` menu, clicking "New Repository", filling repo name (`demo-repo`), selecting "Initialize Repository", and clicking "Create Repository".
  - Full viewport bounding boxes, aria/url/dom verification states, and timings.
- Added `contracts/fixtures/gitea-create-repo-events.sse`:
  - Matching SSE event stream (`RunEvent` schema v1) in wire format (`event: <type>\nid: <seq>\ndata: {...}\n\n`).
  - Spans `run.started`, per-step `step.started` -> `step.action_done` -> `step.verified`, and `run.completed`.
- Added `contracts/fixtures/screenshots/*.png`:
  - Hand-captured viewport screenshots for initial dashboard, steps 1-5, and duplicate-name negative case.

## 1.2 (#15)

Initial release/v1 of the Verified Workflow and Step schemas.

- Added `step.schema.json`:
  - `Step`: executed and verified step of a workflow.
  - `StepVerification`: verification outcome with `result` enum (`verified`, `failed`, `skipped`), `method` array (`url`, `dom`, `aria`, `network`, `vision`), and numeric `confidence`.
  - `StepTarget`: target element with optional `bbox` (referencing `common.schema.json#/$defs/BoundingBox`).
  - `StepTiming`: execution timing offsets (`start_ms`, `end_ms`).
  - `ObservedState`: captured page state (`url`, `title`, `headings`, `aria_excerpt`, `screenshot`, `screenshot_path`, `captured_at`).
- Added `workflow.schema.json`:
  - `Workflow`: core verified workflow object, referencing `step.schema.json` via `$ref` in `steps`.
  - `WorkflowStatus` enum: `draft`, `approved`, `running`, `verified`, `failed`, `outdated`.
  - `WorkflowTarget`: target application (`app`, `base_url`).
  - `WorkflowViewport`: recording viewport dimensions (`width`, `height`, `device_scale_factor`).
  - `WorkflowRecording`: recording artifact metadata (`rrweb`, `path`, `event_count`, `started_at`, `ended_at`).
  - `WorkflowSummary` and `WorkflowPage`: paginated summary list models for `GET /workflows`.
- Enums:
  - `status`: `draft`, `approved`, `running`, `verified`, `failed`, `outdated`
  - `action.type`: `click`, `fill`, `select`, `navigate`, `press`, `wait` (from `common.schema.json`)
  - `verification.result`: `verified`, `failed`, `skipped`
  - `risk`: `low`, `medium`, `high` (from `common.schema.json`)

## 1.1 (#22)

- Added `health.schema.json`: `HealthResponse` (`status: "ok"`, `version`), the response of `GET /health`. Additive.

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
