# Drift rules: when to auto-heal, mark OUTDATED or ask a human, and who gets notified

- **Phase:** 4
- **Researched by:** Vishwas, alone (Nachiketha was busy; written by Claude Code on Vishwas's laptop, 2026-10-29).
  Vishwas decided every proposal below on 2026-10-30, including the ones marked **Nachiketha** (Nachiketha was
  fully busy). The decisions are recorded in `phase-4-decisions-alignment.md`.
- **Question(s):** Agree on the rules: what triggers auto-heal vs OUTDATED vs human review, and who gets notified.

Builds on `phase-4-vishwas-self-healing-locators.md`, `phase-4-vishwas-workflow-versioning.md`,
`phase-4-vishwas-semantic-step-diff.md` and `phase-2-vishwas-reverify.md`. Nachiketha's #106 notes (drift signals,
classification, scheduling, review queues) don't exist yet, so where they would decide something, this note
proposes a default and says so.

## Findings

**What a validation run can already tell us** [verified by reading `app/runs/executor.py`, `app/ports/models.py`,
`app/targets.py`, `app/runs/reverify.py`]
- A reverify run stops at the first step that no longer works and names why: `locator_miss` (the element wasn't
  found or is ambiguous), `action_failed` (the action itself failed), or `state_mismatch` (it ran, but the expected
  state didn't hold) (`_fail_reverify`).
- The policy layer can stop it for reasons that say nothing about the tutorial: `captcha`, `auth_wall`,
  `rate_limited` (and `destructive_action` / `sensitive_data` / `prompt_injection`). A reverify never pauses: a
  pause becomes a failure with that reason.
- Some runs never reach step 1: the reset fails (`reset_failed`, e.g. "Gitea isn't reachable"), the stored GitHub
  session expired (`sign_in_problem`), or reverify refuses the workflow (`high_risk_step`, `secret_not_stored`).
- There's no notification system: no e-mail or push code in the backend [verified by search]. The only live
  channel is the run's SSE stream, which nobody watches during a scheduled validation.

**Does a validation fail when nothing changed?** [verified locally: `assets/phase-4-together-checks/`]
Replayed the newest stored workflow of each of the 5 Gitea benchmark tasks 4 times, with the real reset, executor,
observer and verifier, no LLM, run defaults (5 s action / 5 s verify timeouts):

| | Replays | Passed | Failed | Time per replay |
|---|---|---|---|---|
| No drift (5 tasks × 4) | 20 | **20** | 0 | 2.6–7.8 s, mean 4.1 s |
| Drift control: "Create Repository" renamed "Make repo" | 4 | 0 | **4**, all `locator_miss` at step 4 | 6.5–8.5 s |

- On local Gitea a validation is deterministic both ways: no false failure in 20 runs, and real drift fails at the
  same step with the same reason every time. One re-run to confirm a failure costs ~5–8 s and no LLM calls.
- The stored history is less clean: 2 of the 9 reverify runs in the database failed (`state_mismatch`,
  `locator_miss`, both 2026-10-18 while #77 was being built). And GitHub needed longer timeouts for slow dialogs
  in #89: a slow page looks exactly like a `state_mismatch`. So **one failure isn't proof of drift**, especially on
  GitHub. [verified: `runs` table, #308]
- From #105: healing is only safe after a `locator_miss`. A `state_mismatch` means the app *behaves* differently,
  and there's no element to re-locate. Gemini can be unavailable for a whole day (15/15 attempts failed on
  2026-10-26).

## Recommendation (rules; decided 2026-10-30, see `phase-4-decisions-alignment.md`)

**1. Confirm before deciding.** A failed validation is re-run once right away (same target, fresh reset). Only a
failure at the **same step with the same reason** counts as drift. A different result the second time is a flake:
record it, change nothing. Two flakes on the same workflow within a week go to the review queue as "unstable".

**2. Never mark OUTDATED because of the environment.** If the target, the session, the policy or the LLM quota is
the problem, the validation result is `blocked`, the workflow keeps its status, and the run tries again on the next
schedule.

**3. Decision table** (after the confirm re-run)

| What happened | Result | Workflow status | New version? | Human? |
|---|---|---|---|---|
| All steps verified | `passed` | stays `verified` (or back to `verified`) | no | no |
| `locator_miss`, deterministic heal wins by the margin, the rest of the workflow verifies | `healed` | `verified` | **yes**, `source=heal`, current right away | no. The owner sees an "auto-updated" badge and the diff |
| `locator_miss`, deterministic heal declines, Gemini picks a candidate, the rest verifies | `heal_pending` | `outdated` until accepted | yes, `pending_review` | **yes**: accept → current; reject → stays outdated |
| `locator_miss`, nothing passes the gate, or Gemini unavailable/declines | `outdated` | `outdated` | no | yes: review queue (regenerate / retry heal) |
| A heal worked on its own step, but a later step fails | `outdated` (changed flow) | `outdated` | no (the heal is thrown away) | yes |
| `state_mismatch` or a repeated `action_failed` | `outdated` | `outdated` | no (never healed) | yes |
| Healed target is risky: policy says `destructive_action`, or the step is high risk | `outdated` | `outdated` | no | yes. Never auto-heal into a destructive control |
| `captcha`, `auth_wall`, `rate_limited`, `reset_failed`, sign-in expired, Gitea/GitHub down | `blocked` | unchanged | no | only if it lasts (see 4) |
| Not replayable: high-risk step or a typed secret | `skipped` | unchanged; UI shows "not auto-checked" | no | no |

- A visual-only change (Nachiketha's #111 "cosmetic"; all steps pass but the screenshots look different) is
  `passed`. Whether to offer "refresh the recording" (a new version with the same steps) is an open question
  below.
- The exit criteria fit this table: the renamed button → `healed` + new version. A removed page → the next step
  misses with no candidate → `outdated` in the review queue.

**4. Who gets notified, and how** (in-app only for the MVP: there's no mail infrastructure, and free tiers only)
- **The workflow's owner** (`workflows.user_id`) is the only one notified. Review-queue items: `outdated`,
  `heal_pending`, "unstable". A count badge in the nav; the workflow list shows the status badge.
- **`healed`:** no queue item, just the "auto-updated" badge and the version diff (FYI, no action needed).
- **`blocked` 3 runs in a row** (or a GitHub session expiry, which only a human can fix: log in again) → one
  queue item "can't check this workflow: <reason>". Never one item per run.
- **Share-link viewers** aren't notified. They see a banner on an `outdated` tutorial: "The site changed since this
  tutorial was recorded".
- E-mail / digest: later, if ever. Not needed for the exit criteria.

**5. Budget limits** (so validation doesn't slow normal use, per the exit criteria)
- One browser at a time (`MAX_CONCURRENT_RUNS=1`); validation jobs wait behind user runs.
- Gemini heal calls: at most a few per day (e.g. 5) from a separate budget, so planning keeps its quota. When it's
  used up, the case is treated as "Gemini unavailable" → `outdated` with a "retry the AI fix" action.
- GitHub: the Phase 3 volume rules apply. A confirm re-run counts as a run.

No `architecture.md` change: this is behaviour inside `validation/` and `agent/`, with statuses in the schema.
The result values and the version `status` are contract additions (in #108's contract PR, together with
`validations`).

## Open questions
- **Nachiketha:** OK with these `validations.status` values (`passed | healed | heal_pending | outdated | blocked |
  skipped`) and with the confirm re-run happening inside the validation job (#110)? Or should the scheduler
  re-queue it?
- **Nachiketha:** the review queue UI (#115): the item kinds above, accept/reject on `heal_pending` with the step
  diff, "regenerate" and "retry heal" actions, and the nav badge. Does that fit the queue design from #106?
- **Nachiketha:** should a `cosmetic` drift (#111) offer "refresh recording", creating a version with the same steps
  and new screenshots? Not needed for the exit criteria; it can wait.
- Should the owner be able to turn auto-heal off per workflow (always review)? Cheap to add as a flag, but not
  needed for the MVP.
- Re-check "one re-run is enough" on GitHub once validation runs there. Gitea gave 0 false failures in 20 runs;
  GitHub hasn't been measured.

## Links
- `backend/app/runs/executor.py` (`_fail_reverify`, `_pause`), `backend/app/ports/models.py` (`DecisionReason`),
  `backend/app/targets.py` (`_gitea_reset`, `ResetError`), `backend/app/runs/reverify.py` (`check_replayable`)
- `docs/phases/phase-4-reliability.md` (exit criteria), `docs/research/phase-3-vishwas-github-automation-rules.md` (volume rules)
- `docs/research/phase-4-vishwas-*.md` (#105)
