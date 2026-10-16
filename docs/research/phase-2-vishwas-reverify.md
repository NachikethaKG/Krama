# Re-verification: replaying a stored workflow without the planner

- **Phase:** 2
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** **Re-verification:** replay a stored workflow headlessly using stored locators, without the planner. What should happen when one step's locator no longer matches?

## Findings
Experiments ran on 2026-10-16 against local Gitea 1.22.6, replaying the stored workflow
`c4a44aac-…` ("Create a repository called my-test-1", 3 steps, from the Phase 1 gate). The replay used Krama's real
pieces: `ActionExecutor`, `PageObserver`, `LayeredVerifier` (no vision) and `runs.steps.act_and_verify`, with
`action_timeout_ms` 5000 as in `SessionConfig`. Script and raw results:
[`assets/phase-2-vishwas-reverify/`](assets/phase-2-vishwas-reverify/).

**What's stored is enough to replay** [verified locally]
- Each `workflow_steps` row has `action` (`type`, `value`), `target` (`role`, `name`, `selector`, `bbox`),
  `instruction_text`, `expected_state` and `risk`. That maps 1:1 onto `PlannedStep`, so the replay is "run an
  approved plan made of the stored steps".
- The sign-in isn't stored (`preconditions` is `{}`); it comes from `targets.py` at run time, as for normal runs.
- Masked values: a step with `sensitive: true` stores a masked `action.value`, so it **can't be replayed as is**. None
  of the stored Gitea workflows has one. A reverify of such a step needs the value from the target's secret config
  (like the sign-in) or must stop with a clear reason.

**Results per scenario** (`results.json`)

| Scenario | Step 1 `link "New Repository"` | Step 2 `textbox "Repository Name *"` | Step 3 `button "Create Repository"` |
|---|---|---|---|
| as stored (the repo still exists) | verified 0.6 s | verified 0.5 s | **failed** after 7.4 s: action ok, URL stays `/repo/create` (name taken) |
| reset first (repo deleted by API) | verified 0.4 s | verified 0.2 s | verified 0.3 s |
| stored name doesn't exist (`"Add Repository"`) | **failed** 5.3 s, `target_not_found` | not run | not run |
| UI renamed the button to "Make repo" | verified | verified | **failed** 7.1 s, `target_not_found` |
| UI only grew the label ("Create Repository now") | verified | verified | verified (substring match) |

What this shows:
1. **"Create" workflows are not idempotent.** Replaying one against the same state fails on the last step for a
   reason that has nothing to do with UI drift. Reverify must start from the workflow's starting state: delete what
   the workflow creates (Gitea API), the same reset the benchmark needs (see `phase-2-vishwas-gitea-tasks.md`).
   Substituting a fresh name instead is fragile: the value appears in `action.value`, in `field_values` and in the
   `url_matches` regex of a later step.
2. **A locator miss is cheap and clear:** one action timeout (5 s), then `target_not_found`. The fallback chain
   (role → label → text → selector) runs inside that one wait, so a miss costs 5 s, not 5 s per strategy.
3. **Two different failures** need different follow-ups, and the run already tells them apart:
   - *locator miss*: `ActionResult.ok = false` with `target_not_found` / `ambiguous_target`, the UI changed;
   - *state mismatch*: the action ran, but `expected_state` didn't hold (wrong starting state, or the app behaves
     differently). Phase 4's #109 ("Expose locator-miss and state-mismatch details") builds on exactly this split.
4. **Small label drift is tolerated.** Names match as case-insensitive substrings, so "Create Repository now" still
   matched. The verifier still checks the result, so the tolerance doesn't make a wrong click pass.
5. Steps after a failed step can't run meaningfully. After step 1 missed, the page was still `/`, and step 2's
   "Repository Name *" doesn't exist there. Stop at the first failed step and mark the rest as not run.

**How it fits the current code** [verified by reading `app/runs/`]
- `RunEnvironment.planner = None` already means "no replans; pause for the human instead". Reverify wants neither a
  replan nor a long pause, so a failed step should **end** the reverify run (`failed`), not pause it for 30 min
  (`pause_timeout_s`).
- The policy check (`_allowed`) runs before every step, so a destructive step in a stored workflow still pauses for
  confirmation. A headless reverify with nobody watching would wait there.
- `RunStore.complete` always creates a **new `workflows` row** for a completed run (`app/runs/store.py:169`). A reverify
  run through the same path would duplicate the workflow on success.
- `runs.plan_id` is a required FK. A reverify run needs a plan row: an approved copy of the stored steps, made by the
  server, not edited by a human.

## Recommendation
For #77 (`POST /workflows/{id}/reverify` → `202 Run`):
1. **Reuse the run executor**, with no new replay engine: build an approved plan from the stored steps, start a run
   with `planner=None`, and replay through the same `act_and_verify` / policy / observer path. Per-step results then
   come for free as the existing SSE events (`step.verified`, `step.failed`) and `run_events` rows, which the UI can
   already show.
2. **Fail fast:** on the first failed step, end the run as `failed` with a typed reason (`locator_miss` vs
   `state_mismatch`, plus `step_seq`). Don't run the rest (report them as not run) and don't replan.
3. **Reset first:** reverify only makes sense from the starting state. For Gitea, a target-level reset hook (delete
   the repo the workflow creates) runs before step 1, the same code as the benchmark setup in #78. Without a reset
   the result is meaningless for "create" workflows, so the endpoint should refuse (`409`) workflows whose target
   has no reset.
4. **Don't create a new workflow on success.** Mark the run as a reverify of workflow X, and on completion update
   nothing but the run (Phase 4 adds `workflow_versions` and `validations` for the history).
   This needs a small schema/contract addition, e.g. `runs.kind` (`task` | `reverify`) and
   `runs.source_workflow_id`. That touches `database-schema.md` and `run.schema.json` → **contract change,
   decision for Vishwas + Nachiketha** (could go into #71's contract PR).
5. **Destructive steps:** keep the policy pause (never skip it). Simplest for Phase 2: refuse reverify for workflows
   with a high-risk step, or let the pause time out quickly. **Decision for Vishwas.**

No `architecture.md` change: reverify reuses the existing run pipeline. `api-contract.md` already lists the
endpoint (`POST /workflows/{id}/reverify` → `202 Run`, "Replays the stored workflow headlessly").

## Open questions
- Should a failed reverify set `workflows.status = outdated` right away? Phase 4 (#110, #111) owns drift
  classification; setting it in Phase 2 could fight that design. My suggestion: Phase 2 records only the run result.
- Vision fallback during reverify: allowed (same as a normal run, only for ambiguity), or off to keep reverify free
  of LLM calls? Leaving it on matches normal runs; off makes reverify fully deterministic and quota-free.

## Links
- `backend/app/runs/executor.py` (`RunEnvironment.planner`, `_allowed`, `_Recovery`), `backend/app/runs/store.py` (`complete`)
- `docs/phases/phase-4-reliability.md` (drift detection and self-healing build on this)
- `docs/research/phase-1-vishwas-agent-recovery.md` (the retry/replan budget this reuses)
