# API contract (v1 draft, freeze after both approve)

> The human-readable contract between `backend/` and `frontend/`. The machine-readable version lives in `contracts/` (JSON Schemas, plus `openapi.json` exported from FastAPI). If they disagree, **`contracts/` wins** and this doc gets fixed.
> Changing an endpoint or payload follows the contract-change protocol in [`development-workflow.md`](development-workflow.md#7-contract-changes).

## Conventions

- Base URL: `http://localhost:8000/api/v1` (`NEXT_PUBLIC_API_URL`).
- JSON, `snake_case` fields, UUID ids, ISO-8601 UTC timestamps.
- Long operations return **`202 Accepted`** with a resource the client polls, or streams over SSE.
- Every error uses one shape (`ErrorResponse` in `contracts/schemas/common.schema.json`):
  ```json
  { "error": { "code": "plan_not_editable", "message": "Plan is already approved", "details": {} } }
  ```
  Codes in use: `validation_error` (422), `not_found` (404), `conflict` (409), `plan_not_editable` (409), `run_not_active` (409), `rate_limited` (429), `llm_unavailable` (503), `internal` (500).

## Endpoints

| Phase | Method | Path | Body → Response | Notes |
|---|---|---|---|---|
| F | GET | `/health` | → `{status, version}` | |
| 1 | POST | `/tasks` | `{prompt, target_url}` → `202 Task` | Starts interpretation and planning |
| 1 | GET | `/tasks/{id}` | → `Task` | Poll until `status` is `planned`, `needs_clarification` or `failed` |
| 1 | POST | `/tasks/{id}/clarify` | `{answer}` → `202 Task` | When the interpreter asked a question |
| 1 | GET | `/plans/{id}` | → `Plan` | |
| 1 | PATCH | `/plans/{id}` | `{revision, steps}` → `Plan` | Edit steps. Re-runs the risk check and bumps `revision`. `409` if the revision is stale or the plan is approved |
| 1 | POST | `/plans/{id}/approve` | `{revision}` → `201 Run` | Approves exactly the revision the user saw |
| 1 | POST | `/plans/{id}/reject` | `{reason?}` → `Plan` | |
| 1 | GET | `/runs` | `?limit&cursor` → `{items: Run[], next_cursor}` | Run history |
| 1 | GET | `/runs/{id}` | → `Run` | |
| 1 | GET | `/runs/{id}/events` | → `text/event-stream` | Live view, see below. Supports `Last-Event-ID` |
| 1 | POST | `/runs/{id}/cancel` | → `Run` | |
| 1 | POST | `/runs/{id}/confirm` | `{step_seq, decision: "allow"\|"deny"}` → `Run` | Answers a paused run (any `run.paused` reason). `allow` continues (`run.resumed`): run the destructive step, accept an unclear step, run the replanned steps, or retry once more. `deny` ends the run as `cancelled` (`confirmation_denied`). `409 run_not_active` if it isn't paused at `step_seq` |
| 1 | GET | `/workflows/{id}` | → `Workflow` | The verified workflow (main output) |
| 1 | GET | `/workflows` | `?target_app&limit&cursor` → page of `WorkflowSummary` | |
| 2 | GET | `/workflows/{id}/recording` | → rrweb event JSON | Masked before storage |
| 1 | GET | `/artifacts/{path}` | → image/json | Screenshots, read-only |
| 2 | POST | `/workflows/{id}/reverify` | → `202 Run` (`kind: "reverify"`) | Replays the stored workflow's steps headlessly, without the planner; the run stores no new workflow. `404` unknown workflow; `409 conflict` if a step is high risk, a step typed a secret (never stored), or the target can't be reset to the workflow's starting state (`error.details.reason`). A step that no longer works fails the run: `locator_miss`, `action_failed` or `state_mismatch` in `error.details` |
| 2 | GET | `/workflows/{id}/guide.md` | → `text/markdown` | Text guide: the tutorial's step texts, numbered, one screenshot each (absolute image URLs) |
| 3 | POST | `/runs/{id}/takeover` | → `Run` | The user finishes manually after a CAPTCHA/bot wall |
| 3 | POST | `/auth/*`, `/tutorials/{id}/share` | — | Specified in Phase 3 |
| 4 | GET | `/workflows/{id}/versions` | → `WorkflowVersion[]` | Drift and self-healing |
| 5 | POST | `/workflows/{id}/exports` | `{format: "mp4", preset}` → `202 Export` | |

The tutorial itself has **no endpoint**: the frontend compiles `Workflow → TutorialSpec` with `packages/tutorial-compiler`. The spec's shape is `contracts/schemas/tutorial-spec.schema.json`.

## Core objects (full schemas in `contracts/schemas/`)

```jsonc
// Task
{ "id": "…", "prompt": "Create a repository", "target_url": "http://localhost:3001",
  "status": "planning|needs_clarification|planned|failed",
  "interpretation": { "app": "gitea", "goal": "create_repository", "parameters": {"name": "demo-repo"} },
  "clarification_question": null, "plan_id": "…", "error": null }

// Plan
{ "id": "…", "task_id": "…", "revision": 2, "status": "proposed|approved|rejected",
  "risk": "low|medium|high", "expected_result": "A new repository page is shown",
  "steps": [ { "seq": 1, "action": {"type": "click", "value": null},
               "target": {"role": "button", "name": "New Repository"},
               "instruction_text": "Click “New Repository”.",
               "expected_state": {"url_matches": "/repo/create"}, "risk": "low" } ] }

// Run (kind "reverify": a replay of source_workflow_id; workflow_id stays null)
{ "id": "…", "plan_id": "…", "kind": "task|reverify", "source_workflow_id": null,
  "status": "queued|running|paused|verified|failed|cancelled",
  "current_seq": 3, "retry_count": 1, "workflow_id": null, "error": null,
  "started_at": "…", "finished_at": null }
```
`Workflow` and `Step` follow the sketch in [`phases/README.md` §3.1](phases/README.md) and [`database-schema.md`](database-schema.md).

## Live view: SSE events (`GET /runs/{id}/events`)

Each message has `id: <seq>`, `event: <type>` and a JSON `data` field. Every `data` contains `run_id`, `seq` (monotonic), `ts`.

| Event | Extra data |
|---|---|
| `run.started` | `plan_id`, `total_steps` |
| `step.started` | `step_seq`, `instruction_text` |
| `step.action_done` | `step_seq`, `screenshot_url`, `bbox` |
| `step.verified` | `step_seq`, `method[]`, `confidence` |
| `step.failed` | `step_seq`, `expected`, `observed`, `screenshot_url` |
| `run.replanning` | `reason`, `attempt` |
| `run.paused` | `reason: "destructive_action"\|"captcha"\|"auth_wall"\|"rate_limited"\|"verification_unclear"\|"replan_review"\|"recovery_exhausted"\|"sensitive_data"\|"prompt_injection"`, `step_seq`, `message?`, `plan_id?` (replan_review: the proposed steps) |
| `run.completed` | `workflow_id`, `verified_steps`, `failed_actions` |
| `run.failed` | `error` |
| `run.cancelled` | `reason: "user"\|"confirmation_denied"`, `step_seq` (null before the first step) |
| `run.resumed` | `step_seq`, `decision: "allow"` (after `/runs/{id}/confirm` allowed a paused step) |

`run.completed`, `run.failed` and `run.cancelled` are final: the server closes the stream after them.

Keep-alive: after 15 s of silence the server sends an SSE comment line (a line starting with `:`), not an event. `EventSource` ignores it. Clients must not depend on the comment's text.
