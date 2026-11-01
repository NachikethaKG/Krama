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
  Codes in use: `validation_error` (422), `not_found` (404), `conflict` (409), `plan_not_editable` (409), `run_not_active` (409), `rate_limited` (429), `llm_unavailable` (503), `unauthorized` (401), `forbidden` (403), `internal` (500).
- **Auth (Phase 3):** every endpoint except `/health`, `/auth/login` and `/shared/*` needs the `krama_session`
  cookie (HTTP-only, `SameSite=Lax`, `Path=/`; `Secure` outside local dev), else `401 unauthorized`. Another
  user's task, plan, run or workflow answers `404`, never `403`, so ids can't be probed.
- **CSRF (Phase 3):** `POST`/`PUT`/`PATCH`/`DELETE` need the header `X-Krama: 1` and `Content-Type:
  application/json` (when there is a body); a request with `Sec-Fetch-Site: cross-site` or an `Origin` outside
  `CORS_ORIGINS` is refused. All of these answer `403 forbidden` (`docs/research/phase-3-vishwas-accounts-and-csrf.md`).

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
| 3 | POST | `/auth/login` | `LoginRequest` → `User` + `Set-Cookie` | Seeded accounts only, no sign-up in the MVP. `401 unauthorized` with one generic message for a wrong email or password; repeated failures are slowed down (`429`). A new session id on every login |
| 3 | POST | `/auth/logout` | → `204` | Revokes the session on the server and clears the cookie |
| 3 | GET | `/auth/me` | → `User` | `401` when signed out (the frontend's route guard) |
| 3 | POST | `/workflows/{id}/shares` | → `201 ShareLinkCreated` | Owner only. `url` holds the token and is shown only here (only its SHA-256 is stored) |
| 3 | GET | `/workflows/{id}/shares` | → `ShareLinkList` | Owner only; never the tokens |
| 3 | DELETE | `/workflows/{id}/shares/{share_id}` | → `ShareLink` | Owner only. Revokes (sets `revoked_at`); the link stops working at once |
| 3 | GET | `/shared/{token}` | → `Workflow` | Public, read-only. `task_id`/`run_id` are null and file URLs point under `/shared/{token}/`. Unknown, revoked and expired tokens all answer the same `404`. Sent with `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex, nofollow`, `Cache-Control: private, no-store` |
| 3 | GET | `/shared/{token}/recording`, `/shared/{token}/artifacts/{path}` | → rrweb JSON / image | Only the shared workflow's own files |
| 3 | GET | `/metrics/summary` | → `MetricsSummary` | The last benchmark's `benchmarks/results/summary.json`; `404` before any benchmark has run |
| 4 | POST | `/workflows/{id}/regenerate` | → `202 Task` | Re-plans a workflow that can't heal, from its original prompt and URL: a new task with `regenerates_workflow_id` set, planned like `POST /tasks` (poll it, then review and approve its plan as usual). When its run verifies, the steps become the workflow's next version (`source: regenerate`, current); no new workflow. Owner only, `404` otherwise |
| 4 | GET | `/workflows/{id}/versions` | → `WorkflowVersionList` | Every version of the workflow, newest first, each with its `change_summary` (step diff vs its parent; null for the first). Owner only, like `GET /workflows/{id}`; `404` otherwise. `GET /workflows/{id}` returns the `current` version's steps and recording, and its `revision` |
| 5 | POST | `/workflows/{id}/exports` | `CreateExportRequest {preset: "landscape"\|"portrait"}` → `202 Export`, or `200 Export` | Exports the workflow's current version with the fixed voice (ADR 0004). `200` returns the existing export when the same version, preset and voice is `queued`, `rendering` or `ready`; a `failed` or `expired` one is rendered again (`202`). Owner only (`404`). `409 conflict` with `error.details.reason = workflow_not_verified` if the workflow isn't `verified` or a heal is pending |
| 5 | GET | `/exports/{id}` | → `Export` | `status`: `queued\|rendering\|ready\|failed\|expired`, `progress` 0–100, `error` when failed, `download_url`/`captions_url` when ready. The UI polls every 2 s. Owner of the workflow only (`404`) |
| 5 | GET | `/exports/{id}/download` | → `video/mp4` | Supports `Range` (206/416); `Content-Disposition: attachment`. `409 conflict` (`export_not_ready`) unless `ready`. Owner only |
| 5 | GET | `/exports/{id}/captions.vtt` | → `text/vtt` | Captions from the Piper word timings. `404` if the export has none. Owner only |

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
