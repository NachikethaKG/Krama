# Phase 4 Decisions & Alignment: drift rules, versioning and self-healing

- **Phase:** 4 (Reliability: UI drift)
- **Document type:** Decision record + research summary (for Nachiketha to read; for both agents to build on)
- **Decided by:** Vishwas, 2026-10-30. Nachiketha was fully busy, so Vishwas also took the decisions that touch
  Nachiketha's modules (`validation/`, the version/review UI); they are marked **[N]** below. Nachiketha: if you
  disagree with one, raise it on the issue it applies to before that issue's coding starts.
- **Written by:** Claude Code on Vishwas's laptop.
- **References:**
  - `phase-4-vishwas-self-healing-locators.md`, `phase-4-vishwas-workflow-versioning.md`,
    `phase-4-vishwas-semantic-step-diff.md` (#105, merged in #309)
  - `phase-4-together-drift-rules.md` (#107)
  - `docs/phases/phase-4-reliability.md`

Not covered here: Nachiketha's own research (#106: drift signals, pixelmatch/SSIM, arq scheduling, how docs tools
flag staleness). It's still open, and #110/#111 build on it.

---

## 1. Research in five minutes

**Self-healing (#105).** Healenium scores a broken locator's candidates mostly by page structure (DOM path + tag =
200 of 450 points, text 30, position 0) and never checks the margin to the second-best. On Gitea's settings page,
with the real "Update Settings" button renamed or removed, it picks *another* "Update Settings" button at a perfect
1.0. Our role+name locator already survives restyled and moved elements, so healing is only needed when the
accessible name changes or the element is gone. A safe heal needs the same role, a structural anchor (same form, same
`id`/`name=`), a clear margin over the second-best, a fresh policy check, and the whole rest of the workflow
re-verifying. Gemini can help with "renamed among look-alikes", but it was unavailable for a whole day during the
research (429/503), so healing must work without it.

**Versioning (#105).** Copy-on-write rows. A JSON diff would save ~3–4 KB per version while each version's recording
+ screenshots are ~2.3 MB. Re-planning the same task on an unchanged site gave 2–4 different step lists, so "the plan
came out different" can't define a new version.

**Step diff (#105).** Align steps by meaning (action, role, name, value) with an LCS, pair leftovers by similarity,
and report `same / changed(fields) / added / removed` in the categories behaviour / check / wording / risk. Tested on
123 stored workflows plus a simulated heal and a simulated extra step.

**Drift rules (#107).** On local Gitea, 20 no-drift replays all passed (mean 4.1 s) and a renamed button failed 4 of 4
times at the same step for the same reason: a confirm re-run is cheap and real drift is consistent. GitHub isn't
measured yet.

---

## 2. Decisions

| # | Decision | Applies to | Owner |
|---|---|---|---|
| D1 | **Copy-on-write versions.** `workflow_versions` (version, source, parent, run, status, recording, `change_summary`) + `workflow_steps.version_id`. `workflows.id` stays the stable identity for share links and tutorial URLs, resolving to `current_version_id`. | #108 | Vishwas |
| D2 | **Fingerprint inside `workflow_steps.target` jsonb** (role, name, `element_context`, form signature, `id`/`name=` attribute, bbox), recorded when a workflow is saved. The contract `Target` stays `{role, name, selector}`. | #108, #112 | Vishwas |
| D3 | **Regenerate = a new version of the same workflow** (`source=regenerate`), not a new workflow. | #113 | Vishwas |
| D4 | **#112 covers `agent/`, `runs/` and `db/`**: heal, verify and save the version in one PR. | #112 | Vishwas |
| D5 | **A new version** = a newly verified run of this workflow whose definition differs (step added/removed/reordered, `action`, `target.role/name/selector`, `expected_state`). A passing validation writes only a `validations` row. Wording-only changes never make a version on their own. | #108, #110, #112 | both |
| D6 | **[N] `validations.status`:** `passed \| healed \| heal_pending \| outdated \| blocked \| skipped`. `workflow_versions.status`: `current \| pending_review \| superseded \| rejected`. Both go into #108's contract PR. | #108, #110, #114 | both |
| D7 | **[N] Confirm re-run inside the validation job:** a failed validation re-runs once right away; only the same step failing for the same reason twice counts as drift. One `validations` row per job. | #110 | Nachiketha |
| D8 | **[N] Only deterministic heals go live without a human.** A margin-winning code heal whose whole workflow re-verifies publishes right away with an "auto-updated" badge. A Gemini-chosen heal is saved as `pending_review` and the workflow stays `outdated` until the owner accepts it. | #112, #114, #115 | both |
| D9 | **[N] Never OUTDATED because of the environment.** CAPTCHA, auth wall, rate limit, failed reset, expired sign-in or the site being down → `blocked`; the workflow keeps its status. | #110, #111 | Nachiketha |
| D10 | **[N] Cosmetic drift is `passed`.** No "refresh recording" action in Phase 4. | #111 | Nachiketha |
| D11 | **[N] Full review queue, in-app only.** Items: `outdated`, `heal_pending` (accept/reject with the step diff), "unstable" (2 flakes in a week), "can't check: <reason>" (3 `blocked` in a row, or the GitHub session expired). Actions: accept, reject, regenerate, retry AI fix. A count badge in the nav. Only the workflow's owner is notified; no e-mail. Share-link viewers of an outdated tutorial see a "site changed" banner. | #114, #115 | Nachiketha |
| D12 | **Gemini heal budget: 5 calls per day**, separate from planning. When it's used up → `outdated` with "retry AI fix". | #112 | Vishwas |

### The decision table (from D5–D12)

| What the validation found (after the confirm re-run) | Result | Workflow status | New version | Human |
|---|---|---|---|---|
| All steps verified | `passed` | `verified` | no | no |
| `locator_miss`, deterministic heal wins, rest verifies | `healed` | `verified` | yes, `current` | no (badge + diff) |
| `locator_miss`, Gemini heal, rest verifies | `heal_pending` | `outdated` until accepted | yes, `pending_review` | yes |
| `locator_miss`, no candidate passes / Gemini unavailable or out of budget | `outdated` | `outdated` | no | yes |
| Heal worked but a later step fails (changed flow) | `outdated` | `outdated` | no, heal thrown away | yes |
| `state_mismatch`, or `action_failed` twice | `outdated` | `outdated` | no, never healed | yes |
| Healed target is destructive, or the step is high risk | `outdated` | `outdated` | no | yes |
| CAPTCHA, auth wall, rate limit, reset/sign-in failure, site down | `blocked` | unchanged | no | after 3 in a row |
| High-risk step or typed secret (not replayable) | `skipped` | unchanged, "not auto-checked" | no | no |

---

## 3. What this means for each issue

- **#108 (Vishwas):** the contract-change PR first: tables from D1, the status values from D6, `WorkflowVersion`
  with `change_summary` (diff shape in `phase-4-vishwas-semantic-step-diff.md`), `validations.version_id` + `run_id`.
  Name the version number `revision` (or similar) in the contract: `workflow.schema.json` already uses `version` for
  the format version.
- **#109 (Vishwas):** validation results carry the failing step, the reason, and for a `locator_miss` the top
  candidates with their scores (in `drift_details`), so the review queue can show "almost matched X".
- **#110 (Nachiketha):** scheduled re-runs through the `Validator` port, with the confirm re-run inside the job
  (D7), one browser at a time behind user runs, GitHub under the Phase 3 volume rules (a re-run counts as a run).
- **#111 (Nachiketha):** classification maps onto the table above: cosmetic → `passed` (D10); a moved element found
  by role+name needs no heal at all; `locator_miss` → heal path; `state_mismatch` / changed flow → `outdated`;
  environment → `blocked` (D9).
- **#112 (Vishwas):** scope from D4; the heal gate and order are in `phase-4-vishwas-self-healing-locators.md`
  (deterministic score → Gemini within the D12 budget → policy check → act → verify the rest → save the version).
  The 10 drift scenarios in `assets/phase-4-vishwas-checks/heal_scores.py` are the test fixtures; the settings-page
  pair is the "never heal onto a look-alike" regression test.
- **#113 (Vishwas):** regenerate from the review queue creates a version (D3) through the normal plan approval.
- **#114 / #115 (Nachiketha):** badges `verified`, `auto-updated`, `outdated`, `not auto-checked`; the version
  history with the stored `change_summary` (wording changes collapsed); the review queue from D11.

---

## 4. Still open

- **#106** (Nachiketha's research) isn't done. #110/#111 need its findings on visual diff and scheduling frequency.
- **GitHub flake rate:** measure before trusting "one re-run is enough" there (#89 showed that slow dialogs look like
  `state_mismatch`).
- **Gemini on look-alike renames** is `[unverified]`: re-run `heal_scores.py --vision` on a day with quota (3 requests).
- The healing weights and margin come from 10 Gitea scenarios. Add GitHub pages to the fixtures before trusting the
  numbers.
