# "Do it for me": running a stored verified workflow for the user

- **Phase:** 6 (issue #129)
- **Researched by:** Vishwas (code reading by Claude Code on Vishwas's laptop, 2026-11-19; decisions by Vishwas)
- **Question(s):** Which workflows are safe to replay without re-planning? How do policy confirmations work for
  one-click execution? Plus: the user's own values, whose session, failure handling, contract shape, testing.

Nothing was run for this note. Everything below comes from reading the code, contracts and earlier research notes.
Anything not checked in code is tagged [unverified].

## Findings

### 1. What a replay already does (reverify, #77) [verified by reading code]

- A reverify turns the stored steps into an approved plan and runs it through the normal executor
  (`backend/app/runs/reverify.py:53-69` `plan_steps`, `:96-111` `create_reverify_run`). Policy, observer and
  verifier all run as for a task run. "Do it for me" can reuse exactly this path.
- `check_replayable` (`reverify.py:34-50`) refuses three kinds of workflow:
  - no steps;
  - any step with `risk == "high"`, because nobody watches a reverify and a destructive step could never be confirmed;
  - any step with `sensitive` or a masked `action.value` (`MASK`). Secrets are never stored (`executor.py:652-653`),
    so the value isn't there to replay.
- Before the replay, `create_reverify_run` calls the target's **reset** (`reverify.py:85-93`). For Gitea that
  **deletes** the repository/branch/file the workflow creates (`targets.py:151-186`). This is right for a test
  account and **must never run against a user's own account**.
- The executor changes behaviour by `job.kind`:
  - `_pause` fails a reverify run instead of pausing (`executor.py:611-617`);
  - only a reverify run self-heals a missing locator (`executor.py:354-366`, `_heal` at `:540-580`), and a heal can
    ask Gemini (`heal_chooser`);
  - only a `task` run gets the "did the steps do the whole task?" LLM check (`_missing_part`, `executor.py:485`);
  - completion: `task` stores a new workflow, `reverify` stores nothing (`complete_reverify`, `store.py:221-239`)
    or a new version after a heal (`complete_heal`, `executor.py:279-296`).
- Every step, in every kind of run, goes through `_allowed` (`executor.py:515-538`): the policy is asked first, and
  a step the plan marks `high` **pauses for a human even if the policy says allow** (`:521-524`). So AGENTS.md §4
  holds for a do-it run without new code, as long as the run is allowed to pause (unlike reverify).
- Retry budget: `fill/select/navigate/wait` are retried once; a click never is, since the first click may have
  worked (`IDEMPOTENT`, `executor.py:786`).
- The run's steps live in the plan row: the worker loads them from `plans.steps` (`store.py:91-94`). Anything put
  into a do-it plan is **written to the database**.

### 2. Which workflows are safe to replay

| Workflow | Safe for do-it? | Why |
|---|---|---|
| status `verified`, no high-risk step, no sensitive step | yes | what reverify already accepts |
| has a high-risk step | yes, **with a pause at that step** | the user is watching, so the existing pause works; reverify refuses only because nobody watches |
| has a sensitive (masked) step | not in v1 | the value isn't stored; a run-time secret has no safe way to the worker (§4 below) |
| status `outdated` / pending review / last validation failed | no (or warn) | the stored steps are known not to work; replaying them on real data can leave a half-done change |
| depends on the test account's own objects (e.g. the practice repo `krama-bench/bench-branches`) | only if that object becomes an input | see §3: account and repo names are baked into URLs and navigate values |

Workflow status values: `draft|approved|running|verified|failed|outdated` (`contracts/schemas/workflow.schema.json:79-82`).

### 3. The user's own values ("inputs")

**Where a typed value appears in stored steps** [verified: `contracts/fixtures/gitea-create-repo-workflow.json`]

The fixture "Create a repository" types `demo-repo` in step 3. The same string appears again in:

| Step | Field | Content |
|---|---|---|
| 3 | `action.value` | `demo-repo` |
| 3 | `expected_state.field_values[0].value` | `demo-repo` |
| 3 | `instruction_text` | "Enter demo-repo as the repository name." (newer runs: "…, for example “demo-repo-4821”", `planner/instructions.py:70-82`) |
| 5 | `expected_state.url_matches` | `^/demo/demo-repo$` (a **regex**) |
| 5 | `expected_state.title_contains` | `demo/demo-repo` |
| 5 | `expected_state.visible[0].name` | heading `demo-repo` |

The account name `demo` also appears (URL, title). Tests and benchmarks show the same pattern:
`f"^/{user}/{name}$"`, `^/demo/r/src/branch/feature-docs$` (grep of `backend/tests`, `benchmarks`). GitHub tasks put
the org and practice repo in navigate values and URLs (`benchmarks/tasks/github-create-branch.yaml`).

So an input is not just one `fill`. The value has to be substituted in: `fill`/`select` values, `navigate` paths,
`url_matches` (escaped with `re.escape`), `title_contains`, `field_values`, `visible`/`absent`/`checked` names, later
`target.name`s (e.g. a click on link "demo-repo"), and `instruction_text`.

**How values get there today** [verified: `planner/prompt.py:44-56`, `planner/service.py:129`]
- The planner makes up example names ending in a random 4-digit suffix (`demo-repo-4821`). Values the request names
  are used exactly. The planner does **not** mark which values are user choices. No field for that exists in
  `PlannedStep` (`contracts/schemas/plan.schema.json:37-51`).
- The tutorial text already treats every short `fill` value as "your own choice, shown as an example"
  (`instructions.py:31-35`, `:58-60`). It skips sensitive fills and long or multi-line text (`:54-57`).
- The Gitea reset already finds "what this workflow creates" from `fill` steps whose label says
  "Repository name / Branch name / File name" (`targets.py:155-172`).

**Options for finding inputs**

| Option | How | Pros | Cons |
|---|---|---|---|
| A. Every non-sensitive `fill` is an input | derive at request time from stored steps | no contract change for detection; works for all existing workflows; same rule as the tutorial text | also offers fills that aren't really choices (a search box); short values like `r` or `main` are risky to substitute |
| B. Planner marks inputs (`PlannedStep.input` with a name) | new optional field, planner prompt change | exact; the planner knows which values came from the request | contract change; only new workflows have it; costs prompt tokens; LLM can mislabel |
| C. Values that appear in the request text | compare `task.prompt` with fill values | free | misses made-up example names (most tutorials now, #325) |

**Labels:** `instructions.py` already turns a field label into a noun: "Repository Name *" → "repository name"
(`_clean`, `_example`). The same helper gives the form label. The recorded value becomes the placeholder
("for example demo-repo-4821"), not the default, so the user can't create a clash with our test value by accident.

**Values that change on the way to the URL** [unverified]: GitHub turns spaces and some characters into `-` in a new
repository's name. Then the substituted `url_matches` fails **after** the repository was created. A simple guard:
accept only values in the same character class as the recorded one (e.g. `^[A-Za-z0-9._-]+$` when the example
fits it). The site's own validation still decides the rest; a duplicate name fails the step's `absent` check
("The repository name is already used.") as a `state_mismatch`.

**Account name:** the recording account (`demo`, `krama-bench`) is baked into URLs, but it isn't stored with the
workflow: `workflows.preconditions` is `{}` (`docs/research/phase-2-vishwas-reverify.md`, "What's stored").
`TargetSetup.signed_in_as` (`targets.py:51`, `:93`, `:120`) is known at run time. To act in another account, the
recording identity must be stored with the version, and then substituted like an input (owner part of paths only).

### 4. Secrets typed at run time

- A sensitive fill is masked before storing (`executor.py:652-653`), and `looks_sensitive` decides that from the
  field's label.
- The worker reads steps from `plans.steps` (`store.py:91-94`). A password put into a do-it plan would be stored in
  Postgres. The arq worker is a separate process (#95), so there is no in-memory path from the API request to it.
- A safe path would need an ephemeral, encrypted hand-off (e.g. Fernet with `KRAMA_STORAGE_KEY`, Redis key with a
  short TTL, deleted on first read) and masking in every event and row [unverified design]. That is real work and
  risk for a rare case: login is already handled by the stored session, not by typed passwords.

### 5. Whose browser session [verified: `targets.py:87-131`, `agent/stored_session.py:64-113`, `cli.py:6,65-106`]

- **Gitea:** a scripted login as `settings.gitea_demo_user` with its password from settings (`targets.py:88-97`).
- **GitHub:** one encrypted Playwright `storage_state` **per site**, file `data/sessions/<site>.session`
  (`stored_session.py:76-79`). It is captured once by hand with `uv run krama session capture github`, on the
  machine that runs Krama. It belongs to the **test account**, and every Krama user's runs use it.
- Krama users (`UserRow`, `api/accounts.py`) are separate from site accounts. There is no per-user session store.
  The `browser_profiles` table from the Phase 3 note (`phase-3-vishwas-logged-in-sessions.md`, Recommendation 1) was
  never built (no match in `backend/app` or `docs/database-schema.md`).
- So today **"do it for me" can only act in the test account**. "In my account" needs per-user, per-site sessions:
  a `browser_profiles` row (user_id, site, encrypted state, expires_at), capture from the UI (a headed browser only
  works on the same laptop as the server [unverified for a remote deploy]; that's the #131 takeover question), and
  `TargetSetup` built per run's user. The existing expiry and signed-in checks (`sign_in_problem`,
  `signed_in_check`, `executor.py:234-250`) work unchanged per profile.
- Ownership: runs hang off a task and its owner (`api/owner.py`). A do-it run made by the workflow owner can reuse the
  workflow's task, like reverify. A run by someone else (from a shared tutorial) would need its own task row.

### 6. Policy confirmations in one click [verified: `executor.py:515-538`, `:599-646`; `api-contract.md:39`]

- Pauses already exist: `run.paused` (reason, step_seq, message) → `POST /runs/{id}/confirm` allow/deny →
  `run.resumed` or `cancelled (confirmation_denied)`. The frontend shows them in `PolicyConfirmationModal` from the
  live view (`frontend/components/execution/live-execution-view.tsx:241`).
- The policy adds checks a stored `risk` can't: CAPTCHA, auth wall (stop), danger-zone URLs on GitHub, denylist words
  in the **current** target name (`policy/service.py:43-63`, `policy/risk.py:258-335`). With substituted values a
  later target can change (a repo named "delete-me" turns a link click into a denylist hit → a pause). That's on the
  safe side.
- GitHub's delete-repository dialog asks to type the repo name (`phase-3-nachiketha-github-danger-zones.md` §1). In a
  do-it run that step would be a parameterized fill inside a high-risk flow: the pause still comes at the step.

| Option | How | Fits AGENTS.md §4? |
|---|---|---|
| A. Confirm all risky steps up front | one dialog before the run, then no pauses | **No.** §4 says destructive actions "pause for human confirmation". An up-front yes is given before the page shows what will really be deleted (e.g. which repo the dialog names). |
| B. Pause at each risky step | the run's start is the plan approval; every high-risk / policy-flagged step pauses in the live view | Yes. No new code in the executor. |
| C. B plus a preview | before "Run", show the steps with the user's values and mark the steps that will pause | Yes. Same as B, the user isn't surprised by the pause. |

### 7. Failure handling

- A do-it run is the user's real change. A failed step can leave half a change behind (repo created, settings
  not set). The run must say which steps ran.
- **No reset**, ever (§1). **No automatic retry of the whole run**: a "create" isn't idempotent; a second try fails
  on "name already used" (`phase-2-vishwas-reverify.md`, results table).
- Replan: the env has a planner (`api/services.py:91`); a `task` run replans and pauses for `replan_review`. For
  do-it that costs Gemini and turns a deterministic replay into a new plan. A planned rerun ("plan it fresh with my
  values") is a separate task the user can start.
- Human takeover (#131) is the natural "finish it by hand" path later. The existing `recovery_exhausted` pause
  ("allow tries once more") already lets the watching user retry a step.
- Learning from it: a do-it failure is evidence the workflow drifted. The validation flow (#110,
  `runs/validation_backend.py`) checks workflows with a reset on the test account; it could be asked to re-check the
  workflow, instead of the do-it run changing the workflow status itself.

### 8. LLM calls during a replay [verified: `api/services.py:71-100`, `runs/steps.py:95-98`, `agent/executor.py:269,310-312`, `policy/risk.py:311-313`]

With `LLM_PROVIDER=gemini`, a replay of stored steps can still call Gemini in four edge cases:

| Where | When | Do-it needs it? |
|---|---|---|
| policy classifier (`LLMClassifier`) | target/instruction has a denylist verb with a local scope ("delete draft") | keep: safety; without an answer it falls back to HIGH (= a pause) |
| vision verifier (`GeminiVisionJudge`) | the cheap checks return `skipped` | no: the step pauses as `verification_unclear` and the watching user decides |
| vision locator (`GeminiVisionLocator`) | several elements match the target | optional; without it the step fails `ambiguous_target` |
| heal chooser (`GeminiHealChooser`) | only `kind == "reverify"` | no (keep heals for validation) |

The task check runs only for `kind == "task"` (`executor.py:485`). With the fake provider none of these call a real
model. So a do-it run with vision and heal-chooser off makes **zero LLM calls** except the rare ambiguous-verb policy
check.

## Options compared (run shape)

| Option | How | Pros | Cons |
|---|---|---|---|
| 1. New `RunKind` value `do_it` | `POST /workflows/{id}/run` with `{inputs}` → `202 Run (kind: "do_it", source_workflow_id)` | clear in history and UI; executor switches on kind (pause yes, heal deterministic only, store nothing) | contract change (enum value: additive for the backend, the frontend must handle a new value) |
| 2. Reuse `kind: "reverify"` with a flag | same endpoint, flag in body | no enum change | reverify means "headless, fails instead of pausing, may reset": the opposite behaviour; confusing |
| 3. Reuse a `task` run | make a task + plan from the steps, approve it | no new kind | stores a new workflow and runs the LLM task check; wrong for the user's data |

## Recommendation (proposals, not decisions)

1. **New run kind `do_it`** through the existing executor. Build the plan with `plan_steps` plus substituted inputs.
   Never call `reset`. Pause normally (only reverify fails on a pause). No replan, no Gemini heal chooser, no vision.
   On success store **no** workflow and no version; `run.completed` names the source workflow, as for reverify.
2. **Eligibility:** status `verified`, no sensitive step, no pending review. High-risk steps are allowed and pause.
3. **Inputs (option A):** every non-sensitive, single-line `fill` is an input, grouped by equal value, labelled with
   the `instructions.py` noun, placeholder = recorded example, required. Substitute the exact string in the fields
   listed in §3 (`re.escape` in `url_matches`). Refuse (`409 input_unsafe`) values shorter than 3 characters or
   values that occur in places we don't substitute (to avoid half-replaced steps). Allow only the recorded
   value's character class. Revisit option B when planner marking is cheap.
4. **Confirmations: option C.** A preview with the user's values marks the steps that will pause. "Run" = approve.
   Every high-risk or policy-flagged step pauses in the live view (AGENTS.md §4). No up-front blanket yes.
5. **Failure:** stop at the first failed step after the existing one retry of idempotent steps. Show steps done /
   not run. Offer "Plan it fresh" (new task from the request, user's values) and, after #131, "finish by hand".
   Ask validation to re-check the workflow.
6. **Accounts:** v1 runs in the account Krama is signed in to (test account / Gitea demo), and the UI says so.
   "My account" is a separate, larger task: per-user `browser_profiles` + capture flow, plus storing the recording
   identity with the version so the owner part of paths can be substituted. That needs an ADR (architecture.md §4,
   session storage).
7. **Secrets:** v1 refuses sensitive steps. A run-time secret hand-off is a later task with its own research.

## Contract sketch (additive, contracts 1.15)

- `run.schema.json` v1.2: `RunKind` += `do_it`; `source_workflow_id` description "reverify and do_it".
- `workflow.schema.json` v1.3: `WorkflowInput` {`key`, `label`, `example`, `kind: "text"`, `pattern`?, `steps: int[]`}
  and `WorkflowInputList`; `RunWorkflowRequest` {`inputs`: {key: string}, `revision`: int} (revision so the user
  runs the version they previewed, like `PlanApproveRequest`).
- Endpoints (`docs/api-contract.md`): `GET /workflows/{id}/inputs` → `WorkflowInputList` (or `409` with the refusal
  reason), `POST /workflows/{id}/run` → `202 Run (kind "do_it")`; `409` reasons `secret_not_stored`,
  `not_verified`, `input_unsafe`, `stale_revision`.
- Events: none new. `run.paused`/`run.resumed`/`step.*`/`run.failed` (with `locator_miss|action_failed|state_mismatch`
  in `error.details`, as reverify) cover it.
- DB: `RUN_KINDS` comes from the generated enum (`db/models.py:40`), so the check constraint needs a new Alembic
  migration (Vishwas's area).
- Frontend (Nachiketha's area, or Vishwas under the redesign agreement): a "Do it for me" button on the tutorial page
  (`frontend/app/(app)/tutorials/[id]/page.tsx` → `WorkflowTutorial`) opening an input form + step preview, then
  redirect to `/runs/{id}/live`, which already handles pauses.

## Cheap testing

- Same pattern as `backend/tests/api/test_reverify.py`: fake LLM, real Postgres + Chromium on the local test site;
  plan → approve → run → stored workflow, then `POST /workflows/{id}/run` with a new name, read the SSE stream.
- Unit tests for input detection and substitution on `contracts/fixtures/gitea-create-repo-workflow.json` (value in
  5 places, regex escape, a value with `.`).
- A pause test: a stored step with `risk: high` → `run.paused destructive_action` → confirm allow → completes;
  deny → `cancelled`.
- Assert zero LLM calls: run with a fake provider that fails the test on any call except the policy classifier.
- Local Gitea (docker) for one manual check; real GitHub/Gemini only at the phase checkpoint.

## Proposed decisions

| # | Proposal | Options considered | Recommendation | Applies to |
|---|---|---|---|---|
| P1 | Run kind | new `do_it` / reuse reverify / reuse task | new `do_it` kind, same executor | contracts, runs |
| P2 | Eligible workflows | as reverify / + high risk with pause / any | verified, no sensitive step, no pending review; high risk allowed and pauses | runs |
| P3 | Which values are inputs | all non-sensitive fills / planner-marked / from request | all non-sensitive single-line fills (A), planner marking later | runs, planner |
| P4 | Substituting inputs | value only / every place it reappears / relax checks | exact string in every listed field, `re.escape` in regex; refuse unsafe values | runs |
| P5 | Value validation | none / recorded value's character class / per-site rules | recorded value's character class + min length 3 | runs |
| P6 | Confirmations | up front / pause each / pause each + preview | pause at each risky step + preview (C) | runs, frontend |
| P7 | On a failed step | fail / replan / pause for takeover | fail after the existing one retry; offer "plan it fresh"; takeover after #131 | runs, frontend |
| P8 | Reset before run | as reverify / never | never on a do-it run | runs, targets |
| P9 | Result stored | nothing / new version / validation row | nothing on the workflow; the run is the record; failure asks validation to re-check | runs, validation |
| P10 | LLM use | as task run / none / policy only | policy classifier only; no vision, no heal chooser, no replan, no task check | runs, services |
| P11 | Whose account | test account / per-user sessions now | test account in v1, labelled; per-user `browser_profiles` as its own task + ADR | targets, db, docs |
| P12 | Run-time secrets | refuse / ephemeral encrypted hand-off | refuse in v1 | runs |
| P13 | Who may run it | owner only / anyone with a share link | owner only in v1 | api |

## Task issues it would split into

1. **Contract: `do_it` run kind, workflow inputs, run request** (S, **contract change**).
2. **Input detection + substitution** (`runs/inputs.py`, pure functions + unit tests on fixtures) (M, no).
3. **`POST /workflows/{id}/run` + `GET /workflows/{id}/inputs`, executor `do_it` behaviour, migration for the kind
   check** (M, uses #1).
4. **Frontend: "Do it for me" button, input form, step preview, redirect to the live view** (M, uses #1; Nachiketha
   or Vishwas under the redesign agreement).
5. **Per-user site sessions (`browser_profiles`, capture flow, per-user `TargetSetup`, recording identity on the
   version)** (L, contract change + ADR). Needed for "my account".
6. **Later: run-time secret hand-off** (M, research first) and **"finish by hand"** (belongs to #131).

## Open questions

- Should the screenshots and rrweb recording of a do-it run be kept? They show the user's own data. Probably
  keep step screenshots for the run page, skip or expire the recording [unverified need].
- GitHub's exact renaming of new repository names (spaces, unicode) [unverified]; check once on the test account.
- Selects (e.g. a license) as inputs: offer only the recorded option in v1, or read the options from the page?
- Does a deterministic heal during a do-it run help (fixes the run) or hurt (acts on a guessed element in the
  user's account)? Proposal: off in v1.

## Links
- `backend/app/runs/reverify.py`, `backend/app/runs/executor.py`, `backend/app/runs/store.py`
- `backend/app/targets.py`, `backend/app/agent/stored_session.py`, `backend/app/api/services.py`
- `backend/app/planner/instructions.py`, `backend/app/planner/prompt.py`
- `backend/app/policy/service.py`, `backend/app/policy/risk.py`
- `contracts/schemas/run.schema.json`, `events.schema.json`, `plan.schema.json`, `common.schema.json`
- `docs/research/phase-2-vishwas-reverify.md`, `phase-3-vishwas-logged-in-sessions.md`,
  `phase-1-nachiketha-destructive-actions.md`, `phase-3-nachiketha-github-danger-zones.md`
