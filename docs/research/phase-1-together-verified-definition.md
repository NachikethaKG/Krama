# What "verified" means: signals per action type and the confidence threshold

- **Phase:** 1
- **Researched by:** Together. Prepared by Vishwas (experiments run by Claude Code on Vishwas's laptop); **decisions to confirm with Nachiketha**
- **Question(s):** What does "verified" mean? Agree on the confidence threshold and on which signals are enough per action type.

> **Status: proposal.** #45 is a "together" question. Vishwas prepared the evidence and a proposal; nothing here is final until Nachiketha agrees (comment on the PR or #45). His failure-injection benchmark (sprint 1.2) is the place to measure it.

## Findings
Experiments ran on 2026-10-11 against local Gitea 1.22.6 with the **real** `ActionExecutor`, `PageObserver` and `RuleVerifier` from `main`. Scripts: [`assets/phase-1-together-policy-and-verification/`](assets/phase-1-together-policy-and-verification/)

**What we have today** [verified locally: `backend/app/verifier/verifier.py`]
- The contract `StepVerification` is `{result: verified|failed|skipped, method[], confidence 0..1}`.
- `RuleVerifier` checks `url_matches` (method `url`), `title_contains` (`dom`), and `visible`/`absent`/`field_values`/`checked` against the ARIA snapshot (`aria`).
- Today a step is `failed` if any condition fails (confidence 1.0), `skipped` if a condition couldn't be checked (0.5), and otherwise `verified` (1.0). **Any one passing condition is enough to verify.**

**What the planner asks for** (the 3 Gemini-planned runs from #37; small sample) [verified locally: run logs in `data/artifacts/runs/`]

| Action, target role | Conditions Gemini chose |
|---|---|
| navigate | `url_matches` (2/2) |
| fill, textbox | `field_values` (4/4) |
| click, checkbox | `checked` (3/3) |
| click, link | `url_matches` + `visible` (2/2) |
| click, button | `url_matches` (4), `visible` only (1) |

**A step that "ran" but did nothing: which conditions notice?** We created a repository whose name was already taken. Every action succeeded (fill, click "Create Repository"), but no repository was created and the page stayed on `/repo/create` with an error. The same observed state was checked against different expected states [verified locally: `weak_signals.py`]:

| Expected state | Verifier result | Correct? |
|---|---|---|
| `title_contains: "Gitea"` | verified | ❌ true on every Gitea page |
| `visible: button "Create Repository"` | verified | ❌ it was already there before the click |
| `absent: text "The repository name is already used"` (wrong role) | verified | ❌ **vacuous**: the error is a `paragraph`, so nothing matched the role and "absent" passed |
| `absent: paragraph "The repository name is already used"` | failed | ✅ |
| `url_matches: ^/demo/policy-fixture$` | failed | ✅ |
| `visible: link "policy-fixture"` | failed | ✅ |
| `visible: link "Explore"` (top navigation) | failed | ⚠️ it **is** on screen, but outside `main` |

What this shows:
1. **Weak signals verify broken steps.** A title or an element that was already on the page before the action says nothing about whether the action worked.
2. **`absent` can pass by accident.** A wrong role or a slightly different name means "not found", so it passes. `absent` is good for catching error banners, but it can't be the only evidence.
3. **The verifier only sees the `main` region**, because the observer's ARIA excerpt is `main` (Phase 0 decision). Header, navigation and some dialogs are invisible to it, so a condition on them fails even when it's true. Gitea's confirmation modals also sit outside `main` (see [phase-1-together-destructive-gitea-actions](phase-1-together-destructive-gitea-actions.md)).
4. **There's a mechanical fix for point 1:** the contract `Step` already has `before_state`. An element that was already visible *before* the step can't count as evidence that the step worked.

## Recommendation (proposal)
**Definition.** A step is **verified** when all of these hold:
1. The action itself succeeded (`ActionResult.ok`).
2. Every expected condition passes. Any failure → `failed`.
3. **At least one *effect signal* for its action type passes** (table below). A condition counts as an effect signal only if it was **not already true before the step** (compare with `before_state`).
4. Confidence ≥ **0.8**.

If 1 and 2 hold but 3 doesn't (no effect signal could be checked), the result is `skipped`. A run with a `skipped` step can't produce a Verified Workflow: it **pauses for a human** to look, instead of failing.

**Effect signal required per action type**

| Action (target) | Required effect signal | Also allowed |
|---|---|---|
| `navigate` | `url_matches` | — |
| `fill` (textbox, searchbox) | `field_values` with the exact value. For sensitive fields, compare in memory only and never store the value | — |
| `select` (combobox, listbox) | `field_values` with the selected option | — |
| `click` (checkbox, radio, switch) | `checked` (the right state) | — |
| `click` / `press` that submits or navigates | `url_matches` with a **changed** URL, **or** a `visible` element that was not present before | `absent` of an error banner (extra only) |
| `click` / `press` that opens something (menu, dialog, tab) | `visible` of a new element (menuitem, dialog text, tab panel) | — |
| `wait` | `visible` of the awaited element | — |

Never sufficient on their own: `title_contains`, `absent`, or anything already true before the step.

**Confidence per method**

| Method | Confidence | When |
|---|---|---|
| `url`, `aria`, `dom` (exact match) | 1.0 | today's rule checks |
| `network` (sprint 1.2: e.g. the POST returned 2xx/3xx) | 0.9 | layered verifier |
| `vision` (Gemini looks at the screenshot) | 0.7 | last resort; **below the 0.8 threshold on its own**, so a vision-only step is `skipped` → human review |
| a condition that couldn't be checked | 0.5 | e.g. no ARIA snapshot |

- **Step confidence = the highest confidence among its passing effect signals.** A failing condition always means `failed` (confidence 1.0, as today).
- **Workflow confidence = the minimum over its steps** (`workflows.confidence`). A **Verified Workflow** requires every step `verified`.
- The 0.8 threshold sits between vision (0.7) and network (0.9), so "verified" always rests on at least one mechanical check. Vision can confirm but never verify on its own. We'd revisit this if the failure-injection benchmark shows vision is reliable enough.

**Changes this implies** (Vishwas's area unless noted)
- `verifier/`: implement rule 3 (effect signals + `before_state`) and the confidence table, in sprint 1.2's layered verifier.
- `planner/` prompt: require an effect signal per action type, and only use elements inside `main` (or the URL) for conditions.
- `observer/` (**Nachiketha**): decide whether the ARIA excerpt used for *verification* should be the whole `body`, while the planner keeps getting `main`. Dialogs and navigation are outside `main` today.
- Contracts: none. `StepVerification` and `before_state` already exist.

## Open questions (for the call)
- Is **0.8** the right threshold, and **0.7** right for vision? (Proposal above; Nachiketha's failure-injection benchmark can measure both.)
- Should `skipped` pause the run (proposal) or continue and mark the workflow "unverified"?
- ARIA excerpt for verification: `main` only, or the whole page? This trades token size for coverage.

## Links
- `backend/app/verifier/verifier.py`, `contracts/schemas/step.schema.json` (`before_state`, `verification`)
- [phase-1-vishwas-vision-grounding](phase-1-vishwas-vision-grounding.md), [phase-1-vishwas-agent-recovery](phase-1-vishwas-agent-recovery.md) (on the #43 PR)
