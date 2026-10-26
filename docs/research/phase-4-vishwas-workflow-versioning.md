# Workflow versioning: copy-on-write rows vs a JSON diff, and what counts as a new version

- **Phase:** 4
- **Researched by:** Vishwas (research and checks run by Claude Code on Vishwas's laptop, 2026-10-26; decisions by Vishwas)
- **Question(s):** **Versioning:** how do you store workflow versions (copy-on-write rows vs a JSON diff)? What counts as a new version vs the same one?

## Findings

Measured on the local database: 123 verified workflows, 5 benchmark tasks with 19–22 stored runs each, all on the
same unchanged Gitea 1.22.6, Postgres 16.15. Script and raw results:
[`assets/phase-4-vishwas-checks/step_diff.py`](assets/phase-4-vishwas-checks/step_diff.py), `results-diff.json`, `output.txt`.

**What exists today** [verified by reading `app/db/models.py`, `app/runs/store.py`, `docs/database-schema.md`]
- `workflows` already has `version int default 1` ("Phase 4 versioning"), and `status` allows `outdated`. A
  workflow is tied 1:1 to the run that made it (`run_id` unique), and so to one recording (`recording_path`,
  `viewport`).
- `workflow_steps` are rows, keyed by `(workflow_id, seq)`, "so steps can be queried, compared across versions and
  re-verified". Each step's `target` jsonb holds the evidence of that run too: `bbox` and `scroll`, which the tutorial
  overlay draws on *that* recording.
- `RunStore.complete` makes a **new** `workflows` row for every completed task run. A reverify run stores nothing
  (`complete_reverify`).
- Things that point at a workflow by id: `tutorial_shares.workflow_id`, `runs.source_workflow_id`, the tutorial
  and share URLs in the frontend.
- The planned tables are `workflow_versions` and `validations (id, workflow_id, status, drift_details, ran_at)`, and
  the API is `GET /workflows/{id}/versions → WorkflowVersion[]` (`docs/api-contract.md`).

**Sizes: storage doesn't decide this** [verified locally]

| Task (runs) | step rows per version | version-defining JSON | RFC 6902 patch vs previous run |
|---|---|---|---|
| open an issue (22) | 3.3 KB | 0.9 KB | 0.55 KB (7 empty) |
| set description (21) | 3.3 KB | 1.0 KB | 0.48 KB |
| create branch (21) | 4.3 KB | 1.2 KB | 1.0 KB |
| create repository (19) | 4.1 KB | 1.2 KB | 0.08 KB (12 empty) |
| add file (19) | 5.0 KB | 1.4 KB | 0.44 KB |

- A patch saves ~3–4 KB per version. One run's **artifacts** (rrweb recording + step screenshots) are **~2.3 MB**
  (474 MB for 183 runs in `data/artifacts`). A tutorial version needs its own recording, because the bboxes belong to
  it. So the rows are ~0.2 % of a version's size. A JSON diff would save almost nothing, at the cost of
  replay-to-read, no SQL over old steps, and a broken chain if one patch is bad.

**Same task, no drift, still different** [verified locally: `results-diff.json`]
- Planning the same prompt again on the **unchanged** Gitea gave 2–4 different step lists per task. Examples: an
  extra `navigate /demo/bench-files` first; `click link "New Repository"` vs `navigate /repo/create`; the button
  name "Create new branch from" vs "…from main".
- Even with the same steps, fields differ between runs: `instruction_text` (5–24 times per task), `expected_state`
  (e.g. `\d+` vs `[0-9]+` in the same URL regex, or an extra `text_visible`), and `risk` (5 times on the settings task).
- So "a new plan came out different" **can't** be the rule for a new version. A regenerated plan is nearly always
  different, even when nothing on the site changed.
- But a **reverify/validation replays the stored steps** (no planner). Its definition can't change, only its
  evidence (screenshots, bboxes, verification confidence).

## Recommendation
**1. Copy-on-write rows, with the workflow id staying the stable identity.** No JSON diff.

```
workflows            id (stable: shares, tutorial URLs, reverify point here), task_id, user_id, title,
                     target_app, target_url, status (verified|outdated|…), current_version_id, version (= current number)
workflow_versions    id, workflow_id, version int (unique per workflow), source (initial|heal|regenerate|edit),
                     parent_version_id null, run_id (the run that recorded it), status (current|pending_review|superseded|rejected),
                     recording_path, viewport, confidence, change_summary jsonb (the step diff), created_by null, created_at
workflow_steps       + version_id fk → workflow_versions (unique with seq); a new version copies all its step rows
validations          id, workflow_id, version_id, run_id, status (passed|drifted|healed|failed|error), drift_details jsonb, ran_at
```

- Every version is immutable: its own step rows, its own recording. Old tutorials stay playable and diffable with
  plain SQL. Shares and tutorial URLs keep using `workflows.id` and resolve to `current_version_id`. A share could
  pin a version later, if we ever want that.
- Migration: one `workflow_versions` row (version 1, `source=initial`) per existing workflow, and backfill
  `workflow_steps.version_id`. Readers that load `workflow.steps` switch to the current version's steps in one place
  (`db/repositories.py`).
- Rejected alternative, "history snapshot": keep editing the `workflows` row and push the old one into
  `workflow_versions` as jsonb. Fewer reader changes, but old versions lose their step rows and recording link,
  which the diff view and "show me the old tutorial" need.

**2. What counts as a new version**

| Event | New version? | Why |
|---|---|---|
| Validation replay passes, steps unchanged | **No.** Write a `validations` row (`passed`) | Same definition; screenshots of a passing run are evidence, not a new tutorial |
| Validation finds drift, heal succeeds and the whole workflow re-verifies | **Yes**, `source=heal` | The definition changed (target name, maybe instruction text) and there's a new recording |
| Validation fails, no heal | **No.** Workflow `status=outdated`, `validations` row with `drift_details` | Nothing new was verified |
| "Regenerate" (#113): new plan, approved, run verified | **Yes**, `source=regenerate`, same `workflow_id` | It replaces the outdated tutorial for the same task. Today it would be a separate workflow |
| A brand-new task run for the same prompt | **No.** It's a new workflow (today's behaviour) | Different identity; merging by prompt text would be a guess |
| Only the evidence differs (bbox, scroll, confidence, wording) on a passing replay | **No** | Noise. Measured above: it changes on every run |

Rule of thumb: **a new version = a newly verified run of this workflow whose definition differs** (step added,
removed or reordered; `action` or `target.role/name/selector` or `expected_state` changed). A wording-only
difference (`instruction_text`) rides along with such a version but never makes one on its own.

**3. Contract and schema work** (for #108, as a `contract-change` PR first): `database-schema.md` (tables above),
`WorkflowVersion` in `contracts/schemas/workflow.schema.json`, and `GET /workflows/{id}/versions` in the OpenAPI
spec. No `architecture.md` change: `workflow_versions` and `validations` are already in the phase plan and the
schema doc's Phase 4 list.

## Open questions
- **Decision for Vishwas:** copy-on-write with `version_id` on `workflow_steps` (recommended) vs the
  history-snapshot shortcut.
- **Together (#107):** should a heal or regenerate become current right away, or wait in `pending_review`? The
  status column supports both. Who may accept or reject: only the workflow's owner?
- `workflows.version` vs `workflow.schema.json`'s `version` ("Workflow format version, e.g. 1.0"): two meanings of
  one word. Name the new one `revision` or `version_number` in the contract to avoid confusion.
- Retention: keep every version's recording forever? At ~2.3 MB each it's fine for the MVP. A later cleanup could
  drop recordings of `superseded` versions older than N days, keeping their step rows.
- `validations.status` values and `drift_details` shape are Nachiketha's (#110, #111). The fields above are a
  placeholder for that discussion.

## Links
- https://www.rfc-editor.org/rfc/rfc6902 (JSON Patch, used for the size comparison; `jsonpatch` 1.37)
- `backend/app/db/models.py`, `backend/app/runs/store.py` (`complete`, `complete_reverify`), `backend/app/runs/reverify.py`
- `docs/database-schema.md`, `docs/api-contract.md` (`/workflows/{id}/versions`, `/workflows/{id}/reverify`)
- `docs/research/phase-2-vishwas-reverify.md`, `docs/research/phase-4-vishwas-semantic-step-diff.md`
