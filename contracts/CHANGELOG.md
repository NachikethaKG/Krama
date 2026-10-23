# Contracts changelog

Every change to `contracts/` is listed here. Additive change = minor version bump; breaking change = major bump + ADR.

## 1.8 (Phase 3 API)

Accounts, share links and the metrics summary (#94, #96, #102). Additive.

- New `auth.schema.json` v1.0: `User` (no password field, ever) and `LoginRequest` (password at most 128 characters, so argon2 work stays bounded). No sign-up schema: accounts are seeded in the MVP.
- New `share.schema.json` v1.0: `ShareLink` (never the token), `ShareLinkCreated` (`link` + `url`, the only time the token is returned) and `ShareLinkList`.
- New `metrics-summary.schema.json` v1.0: `MetricsSummary` + `TaskMetrics`, the shape of the benchmark reporter's `summary.json` (mirrors `BenchmarkReportData` in `benchmarks/reporter/models.py`).
- `common.schema.json` v1.2: `ErrorCode` gains `unauthorized` (401) and `forbidden` (403, CSRF).
- `docs/api-contract.md`: auth and CSRF conventions; `/auth/login|logout|me`, `/workflows/{id}/shares`, `/shared/{token}` (returns a `Workflow` with `task_id`/`run_id` null), `/metrics/summary`.
- `docs/database-schema.md`: `users`, `sessions`, owners on `tasks`/`workflows`, `tutorial_shares.token_hash` (migrations in #94, #96).

## 1.7 (#253)

Runs that re-verify a stored workflow (#77). Additive.

- `run.schema.json` v1.1: `Run.kind` (new enum `RunKind`: `task` | `reverify`, default `task`) and
  `Run.source_workflow_id` (the stored workflow a reverify run replays). `workflow_id` is documented: null until a
  task run is verified, always null for a reverify run, which stores no new workflow.
- `events.schema.json` v1.3: `RunCompletedEvent.workflow_id` is documented as the re-verified workflow for a reverify
  run (description only).
- `docs/api-contract.md`: `POST /workflows/{id}/reverify` returns a `kind: "reverify"` run; `404` / `409` cases.
- `docs/database-schema.md`: `runs.kind`, `runs.source_workflow_id` (migration in #77).

## 1.6 (#71)

The tutorial spec, plus the scroll a step's bbox was measured at. Additive.

- New `tutorial-spec.schema.json` v1.0: `TutorialSpec` = the output of `packages/tutorial-compiler`
  (`Workflow → TutorialSpec`), read by the player now and the Remotion export in Phase 5. One `Scene` per step with
  `start_ms` on the tutorial timeline, `action`, `caption` (`words` optional), `recording` slice (ms since the
  recording's first event), optional `scroll`, and nullable `camera` / `cursor` / `highlight` (steps without an
  element have none). All times are integer ms; geometry is page CSS px. Based on the #70 design note, moved into
  the contract rules (draft 2020-12, titles, shared `BoundingBox`), with `step_index` renamed `step_seq`.
- `common.schema.json` v1.1: new `ScrollOffset` (`{x, y}`, window scroll in CSS px).
- `step.schema.json` v1.1: `StepTarget.scroll` (optional): the window scroll when the action ran, so a replay places
  the bbox without relying on rrweb's scroll events (they can land just after the click;
  `docs/research/phase-2-vishwas-coordinates.md`). Stored inside `workflow_steps.target` (jsonb): no migration.
- Fixtures: `fixtures/tutorial-spec/gitea-create-repo.json` (compiled by hand from `gitea-create-repo-workflow.json`,
  in a subfolder because every top-level fixture is validated as a `Workflow`); the workflow fixture's steps now
  carry `target.scroll` (step 4 is below the fold: bbox y 936, scroll 544).

## 1.5 (#216)

More reasons a run can pause for a human, and the plan to review after a replan. Additive.

- `events.schema.json` v1.2:
  - `PauseReason` adds `verification_unclear` (a step nothing proved, #45/#53), `replan_review` and `recovery_exhausted` (#55), `sensitive_data` and `prompt_injection` (Policy port pauses, #59).
  - `RunPausedEvent` adds optional `plan_id`: for `replan_review`, the plan with the proposed steps.
- `docs/api-contract.md`: `/runs/{id}/confirm` answers any pause; what allow/deny mean.

## 1.4 (#203)

Two new live-view events and looser keep-alive wording. Additive: no existing event changed.

- `events.schema.json` v1.1:
  - `RunCancelledEvent` (`run.cancelled`): `reason` (new enum `CancelReason`: `user` | `confirmation_denied`), optional `step_seq` (null before the first step). Final event.
  - `RunResumedEvent` (`run.resumed`): `step_seq`, `decision: "allow"`. A paused run continues after `POST /runs/{id}/confirm`.
- `docs/api-contract.md`: the keep-alive is "an SSE comment line", not the exact text `: keep-alive` (FastAPI's built-in SSE sends `: ping`). Lists which events are final.

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
