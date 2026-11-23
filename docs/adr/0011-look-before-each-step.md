# 0011 — Look before each step: an approved outline, then one decision per step

- **Status:** accepted
- **Deciders:** Vishwas (2026-11-23; Nachiketha away)
- **Issue:** #465 · Research: [`phase-7-vishwas-any-website-spike.md`](../research/phase-7-vishwas-any-website-spike.md),
  decisions W1–W8 in [`phase-7-decisions-alignment.md`](../research/phase-7-decisions-alignment.md)

## Context
Krama plans every step of a task up front from the first page, including the expected state of pages it has not
seen yet, then executes and verifies the plan. Hand-written site hints made that work on Gitea and GitHub. On five
sites without hints (spike #457) every action hit the right element (8/8), yet three runs failed on a guessed
expectation (a URL query, a URL prefix, a dialog name), and each replan then paused for review. Guessing the future
is the failure; acting is not.

## Decision
1. **Outline, then steps.** One LLM call writes an outline (the goal and rough ordered intentions, no selectors and
   no expected states). The user approves the outline. Then the run repeats: observe the page → decide one action
   (one LLM call) → act → verify.
2. **Verify by what changed.** After an action, the observed change (URL with query, elements that appeared or went,
   field values, checked state) becomes that step's `expected_state`. Only when nothing visible changed does one LLM
   call ask whether the action did what was intended. One "is the whole task done?" check ends the run.
3. **No replan reviews in step mode.** The next decision is the recovery. Limits: 20 steps and 25 LLM calls per task;
   3 decisions in a row without visible progress pause the run and offer a takeover (ADR 0008).
4. **Safety is unchanged.** Every action passes the policy; risky steps pause for confirmation (AGENTS.md §4). Page
   text stays untrusted data.
5. **Replays need no LLM.** The stored workflow is the steps actually taken with their observed expected states;
   do-it-for-me and reverify replay it as before.
6. **One agent for every site.** New tasks on Gitea and GitHub use it too; their hints become seed site notes.
7. **Transition.** The plan-up-front planner stays behind `PLANNER_MODE=upfront` for v1.4, then is removed.

## Alternatives considered
- **Keep planning up front and fix the gaps.** Rejected: the main failure (guessed expectations) remains.
- **Steps without an outline.** Rejected: the user would approve nothing before Krama acts.
- **Screenshots with every decision.** Rejected: ARIA text was enough in every spike case, at a fraction of the tokens;
  vision stays the fallback when an element can't be found.

## Consequences
- More LLM calls per task (about one per step plus a check: 3–6 in the spike's tasks, capped at 25), measured by
  `llm_calls` (#464). Step decisions get their own model order (`GEMINI_MODELS_STEP`).
- Tutorials describe what happened, not what was planned; their text is still written by code (ADR 0003).
- Plan review for new tasks becomes outline review (frontend, #472).
- `architecture.md` §2 pipeline: plan → approve → execute becomes outline → approve → (decide → act → verify)*.
