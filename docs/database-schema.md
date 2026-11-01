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
| regenerates_workflow_id | uuid fk → workflows, null | Phase 4 (#113): this task re-plans that workflow; its verified run becomes the workflow's next version |

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
| kind | text not null default 'task' | `task\|reverify` (#253) |
| source_workflow_id | uuid fk → workflows, null | reverify only: the stored workflow being replayed |
| status | text | `queued\|running\|paused\|verified\|failed\|cancelled` |
| current_seq | int | |
| retry_count | int | |
| last_event_seq | int not null default 0 | seq of the last `run_events` row for this run, bumped in the same UPDATE that writes the event (gapless, race-free) |
| browser_session | text null | worker/session id |
| error | jsonb null | |
| started_at / finished_at | timestamptz null | |
| duration_ms | int null | |

### `run_events`
The persisted SSE stream, so the live view can resume and old runs can be replayed in the UI.
| column | type | notes |
|---|---|---|
| run_id | uuid fk → runs | pk part 1 |
| seq | int | pk part 2, monotonic, taken from `runs.last_event_seq` |
| type | text | event type from the API contract |
| data | jsonb | |
| ts | timestamptz | |

### `workflows`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| task_id | uuid fk → tasks | |
| run_id | uuid fk → runs | the run that produced its first version |
| title | text | |
| target_app | text | `gitea`, `github`, … |
| target_url | text | |
| status | text | `verified\|failed\|outdated` |
| revision | int | the current version's number (Phase 4; was `version`) |
| current_version_id | uuid fk → workflow_versions | the version shown (status `current`); set in the same transaction as the insert |
| confidence | real | the current version's |
| preconditions | jsonb | e.g. `{logged_in_as: "demo"}` |
| recording_path | text null | rrweb JSON in the artifact store (the current version's) |
| viewport | jsonb | `{width, height, device_scale_factor}` (the current version's) |

`run_id` aside, `confidence`, `recording_path` and `viewport` are copies of the current version's values, made when a
version becomes current, so every reader of a workflow keeps reading one row.

### `workflow_versions`
Every version of a workflow, immutable once written except for `status` (Phase 4,
`docs/research/phase-4-decisions-alignment.md` D1, D5). Each version has its own step rows and recording.
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| workflow_id | uuid fk → workflows | on delete cascade; unique with `revision` |
| revision | int | 1, 2, … per workflow |
| source | text | `initial\|heal\|regenerate\|edit` |
| status | text | `current\|pending_review\|superseded\|rejected`; at most one `current` per workflow (partial unique index) |
| parent_version_id | uuid fk → workflow_versions, null | the version it was made from; null for the first |
| run_id | uuid fk → runs, null | the run that recorded it |
| created_by | uuid fk → users, null | who asked for it (regenerate, edit); null for the first and for heals |
| confidence | real null | |
| recording_path | text null | |
| viewport | jsonb null | |
| change_summary | jsonb null | `StepDiff` vs the parent version (contract); null for the first |

### `workflow_steps`
Stored as rows (not jsonb) so steps can be queried, compared across versions and re-verified.
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| workflow_id | uuid fk → workflows | |
| version_id | uuid fk → workflow_versions | on delete cascade; unique with `seq`. A new version copies all its steps |
| seq | int | |
| action | jsonb | `{type, value}` (value masked if sensitive) |
| target | jsonb | `{role, name, selector, bbox, scroll}`; `scroll` = `{x, y}` window scroll when the action ran. Phase 4 adds an internal `fingerprint` key (D2) |
| instruction_text | text | |
| before_state / expected_state / observed_state | jsonb | |
| verification | jsonb | `{result, method[], confidence}` |
| risk | text | |
| sensitive | bool | |
| screenshot_path | text null | |
| start_ms / end_ms | int | offsets into the recording |

### `validations`
One row per validation of a stored workflow (Phase 4, #110 writes them).
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| workflow_id | uuid fk → workflows | on delete cascade |
| version_id | uuid fk → workflow_versions, null | the version that was validated |
| run_id | uuid fk → runs, null | the reverify run (the last one, after a confirm re-run) |
| status | text | `passed\|healed\|heal_pending\|outdated\|blocked\|skipped` (`ValidationStatus`) |
| drift_details | jsonb null | failing step, reason, healing candidates (#109, #111) |
| ran_at | timestamptz | |

## Later phases
- **Phase 3:**
  - `users (id, email unique lower-cased, password_hash argon2id, display_name, created_at)`: seeded, no sign-up.
  - `sessions (id, user_id, token_hash unique, created_at, last_seen_at, expires_at, revoked_at)`: the cookie holds a random token, only its SHA-256 is stored; idle 7 days, absolute 30 days.
  - `tasks.user_id` and `workflows.user_id` (owner; null for rows from before Phase 3).
  - `tutorial_shares (id, workflow_id, created_by, token_hash unique, created_at, expires_at null, revoked_at null, last_used_at null)`.
  - Signed-in browser sessions for real sites (#87) are Fernet-encrypted files under `data/sessions/`, not a table, while there is one test account per site.
- **Phase 4:** `workflow_versions`, `validations`, `workflow_steps.version_id`, `workflows.revision` +
  `current_version_id`: see the tables above.
- **Phase 5:** `exports (id, workflow_id, format, preset, status, path)`.

## Indexes
`runs(plan_id)`, `runs(status)`, `workflows(target_app, status)`, `workflow_steps(version_id, seq)` unique, `workflow_steps(workflow_id)`, `workflow_versions(workflow_id, revision)`
unique, `workflow_versions(workflow_id) where status = 'current'` unique, `validations(workflow_id, ran_at)`, `tasks(user_id)`.
