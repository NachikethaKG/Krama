# Database schema (v1 draft)

> Both people agree on the **schema**. Only the backend owner (Vishwas) writes **migrations** (`backend/alembic/`), so migration files never conflict.
> To change a table: open a `contract-change` issue, update this doc in the contract PR, and the backend owner then writes the migration.

PostgreSQL 16. All ids are UUID, timestamps are `timestamptz` (UTC), and every table has `created_at` and `updated_at`.

## Tables (Phase 1)

### `tasks`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk → users, null | null until Phase 3 |
| prompt | text | raw user request |
| target_url | text | |
| status | text | `planning\|needs_clarification\|planned\|failed` |
| interpretation | jsonb | `{app, goal, parameters}` |
| clarification_question | text null | |
| error | jsonb null | |

### `plans`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| task_id | uuid fk → tasks | |
| revision | int | bumped on every edit; approve must match it |
| status | text | `proposed\|approved\|rejected` |
| risk | text | `low\|medium\|high` (max of the step risks) |
| expected_result | text | |
| steps | jsonb | array of planned steps (an editable document, so jsonb rather than rows) |
| approved_at | timestamptz null | |

### `runs`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| plan_id | uuid fk → plans | |
| plan_revision | int | the exact revision that was approved |
| status | text | `queued\|running\|paused\|verified\|failed\|cancelled` |
| current_seq | int | |
| retry_count | int | |
| browser_session | text null | worker/session id |
| error | jsonb null | |
| started_at / finished_at | timestamptz null | |
| duration_ms | int null | |

### `run_events`
The persisted SSE stream, so the live view can resume and old runs can be replayed in the UI.
| column | type | notes |
|---|---|---|
| run_id | uuid fk → runs | pk part 1 |
| seq | int | pk part 2, monotonic |
| type | text | event type from the API contract |
| data | jsonb | |
| ts | timestamptz | |

### `workflows`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| task_id | uuid fk → tasks | |
| run_id | uuid fk → runs | the run that produced it |
| title | text | |
| target_app | text | `gitea`, `github`, … |
| target_url | text | |
| status | text | `verified\|failed\|outdated` |
| version | int | Phase 4 versioning |
| confidence | real | |
| preconditions | jsonb | e.g. `{logged_in_as: "demo"}` |
| recording_path | text null | rrweb JSON in the artifact store |
| viewport | jsonb | `{width, height, device_scale_factor}` |

### `workflow_steps`
Stored as rows (not jsonb) so steps can be queried, compared across versions and re-verified.
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| workflow_id | uuid fk → workflows | unique with `seq` |
| seq | int | |
| action | jsonb | `{type, value}` (value masked if sensitive) |
| target | jsonb | `{role, name, selector, bbox}` |
| instruction_text | text | |
| before_state / expected_state / observed_state | jsonb | |
| verification | jsonb | `{result, method[], confidence}` |
| risk | text | |
| sensitive | bool | |
| screenshot_path | text null | |
| start_ms / end_ms | int | offsets into the recording |

## Later phases
- **Phase 3:** `users (id, email, password_hash, created_at)`, `tutorial_shares (id, workflow_id, token, created_by)`, `browser_profiles` (encrypted storage-state reference, never raw passwords).
- **Phase 4:** `workflow_versions`, `validations (id, workflow_id, status, drift_details, ran_at)`.
- **Phase 5:** `exports (id, workflow_id, format, preset, status, path)`.

## Indexes
`runs(plan_id)`, `runs(status)`, `workflows(target_app, status)`, `workflow_steps(workflow_id, seq)` unique, `tasks(user_id)`.
