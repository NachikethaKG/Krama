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
| 1 | GET | `/workflows` | `?target_app&status&limit&cursor` → page of `WorkflowSummary`; with `?q=` (#135): `?q&status&limit&offset` | Without `q`: newest first, keyset `cursor`. `status` filters by workflow status. With `q`: Postgres full-text + trigram search over title, app, request and step text (all words first, then any word), ranked by text × status (verified 1.0, auto-updated 0.95, outdated 0.6, failed 0.3) × freshness (0.8 + 0.2·e^(−days since last validation / 30)); each item carries `score`, `match` {step_seq, snippet with `<mark>`} and `last_validated_at`; paging by `offset` (`limit` ≤ 50), `next_cursor` is the next offset as text |
| 2 | GET | `/workflows/{id}/recording` | → rrweb event JSON | Masked before storage |
| 1 | GET | `/artifacts/{path}` | → image/json | Screenshots, read-only |
| 2 | POST | `/workflows/{id}/reverify` | → `202 Run` (`kind: "reverify"`) | Replays the stored workflow's steps headlessly, without the planner; the run stores no new workflow. `404` unknown workflow; `409 conflict` if a step is high risk, a step typed a secret (never stored), or the target can't be reset to the workflow's starting state (`error.details.reason`). A step that no longer works fails the run: `locator_miss`, `action_failed` or `state_mismatch` in `error.details` |
| 6 | GET | `/workflows/{id}/inputs` | → `WorkflowInputList` | "Do it for me" (#129): the values the owner chooses before running the current version (every non-sensitive single-line value the recorded run typed; the recorded value is the `example`), and the site `account` the run acts in. Owner only, `404` otherwise. `409 conflict` with `error.details.reason`: `not_verified` (status isn't `verified`), `pending_review` (a version waits for review), `secret_not_stored` (a step typed a secret; `details.step_seq`) |
| 6 | POST | `/workflows/{id}/run` | `RunWorkflowRequest {revision, inputs}` → `202 Run` (`kind: "do_it"`, `source_workflow_id`) | Runs the stored steps for the owner with their values replacing the example everywhere it reappears. Starting it approves the steps; it never resets the site, and every high-risk or policy-flagged step pauses (`run.paused`, answer with `/runs/{id}/confirm`). No replan, no self-heal; the first step that fails after its one retry fails the run (`locator_miss`, `action_failed` or `state_mismatch` in `error.details`). Stores no workflow. Owner only (`404`). The same `409` reasons as `/inputs`, plus `stale_revision` (the current version is newer than `revision`). `422 validation_error` with `error.details.reason = input_unsafe` and `details.key` when a value is missing, unknown, shorter than `min_length` or doesn't match `pattern` |
| 2 | GET | `/workflows/{id}/guide.md` | → `text/markdown` | Text guide: the tutorial's step texts, numbered, one screenshot each (absolute image URLs) |
| 6 | POST | `/runs/{id}/takeover` | → `Run` (`takeover` set) | Human takeover (ADR 0008): the run's owner takes control of the paused run's page; `run.paused.takeover_available` says when it's offered (auth_wall, captcha, recovery_exhausted, verification_unclear, a failed do-it step; never rate_limited, reverify or validation runs). Emits `takeover.started`; the run stays `paused`. Owner only (`404`). `409 run_not_active` unless paused with a takeover available; `409 conflict` (`takeover_active`) when someone already has control |
| 6 | POST | `/runs/{id}/handback` | `RunHandBackRequest {step_seq, done: "barrier"\|"step"\|"rest"}` → `Run` | Ends the takeover (`takeover.ended`, `handed_back`). barrier: Krama re-checks and retries the step; step: verifies its expected state without acting (`step.verified` with `performed_by: "human"`); rest: runs the final task check. Not verified → `run.paused` again with the reason. `409 run_not_active` without an active takeover at `step_seq` |
| 6 | WS | `/runs/{id}/screen` | binary JPEG frames ↓, `TakeoverInput` JSON ↑, `TakeoverServerMessage` JSON ↓ | The live page while a takeover is active: frames only when the page changes, at most 15 fps, 1280×800. Checks the session cookie, `Origin` (in `CORS_ORIGINS`) and the run's owner; closes with 4403 otherwise and 4409 for a second controller. Navigation outside the target and its sign-in domains is blocked (`blocked`). 5 min without input ends the takeover (`ended`, `idle`); the run stays paused. Frames are never stored |
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
| 4 | GET | `/reviews` | → `ReviewItemList` | The signed-in owner's review queue (D11), newest first: `heal_pending` (an AI-chosen fix waits, D8), `outdated` (no longer works, nothing waits), `cant_check` (last 3 validations `blocked`), `unstable` (2+ flaky validations in 7 days). Derived from versions and validations; nothing stored per item |
| 4 | GET | `/reviews/count` | → `ReviewCount` | The nav badge |
| 4 | POST | `/reviews/{id}/accept` | → `ReviewActionResult` | `heal_pending` items only: the waiting version becomes current, the old one `superseded`, the workflow `verified` (D8). `404` unknown or not the owner's; `409 conflict` if the version no longer waits |
| 4 | POST | `/reviews/{id}/reject` | → `ReviewActionResult` | `heal_pending` items only: the version becomes `rejected`; the workflow stays `outdated` (regenerate or retry the AI fix) |
| 4 | POST | `/workflows/{id}/retry-ai-fix` | → `202 Run` (`kind: "reverify"`) | Replays the workflow with the Gemini heal allowed (D12). `429 rate_limited` when today's AI fix budget (5) is used up; otherwise the same refusals as `/reverify` |
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
| `step.verified` | `step_seq`, `method[]`, `confidence`, `performed_by?` (`human` after a hand-back, ADR 0008) |
| `step.failed` | `step_seq`, `expected`, `observed`, `screenshot_url` |
| `run.replanning` | `reason`, `attempt` |
| `run.paused` | `takeover_available?` (ADR 0008), `reason: "destructive_action"\|"captcha"\|"auth_wall"\|"rate_limited"\|"verification_unclear"\|"replan_review"\|"recovery_exhausted"\|"sensitive_data"\|"prompt_injection"`, `step_seq`, `message?`, `plan_id?` (replan_review: the proposed steps) |
| `run.completed` | `workflow_id`, `verified_steps`, `failed_actions` |
| `run.failed` | `error` |
| `run.cancelled` | `reason: "user"\|"confirmation_denied"`, `step_seq` (null before the first step) |
| `run.resumed` | `step_seq`, `decision: "allow"` (after `/runs/{id}/confirm` allowed a paused step) |
| `takeover.started` | `step_seq` (the owner took control of the paused page, ADR 0008) |
| `takeover.ended` | `step_seq`, `reason: "handed_back"\|"idle"\|"closed"\|"cancelled"`, `done?: "barrier"\|"step"\|"rest"` |

`run.completed`, `run.failed` and `run.cancelled` are final: the server closes the stream after them.

Keep-alive: after 15 s of silence the server sends an SSE comment line (a line starting with `:`), not an event. `EventSource` ignores it. Clients must not depend on the comment's text.
