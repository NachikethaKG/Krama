# Instruction text: what a good UI step says, and where to write it

- **Phase:** 2
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** **Instruction text:** what makes a good UI instruction? (Imperative, quote the exact label, say where on screen: "Click **New Repository** in the top-right `+` menu.") Write a prompt and compare outputs.

## Findings
Experiments ran on 2026-10-16 on local Gitea 1.22.6. Test set: **22 real executed steps from 5 tasks** (create repo,
plus the 4 new tasks from `phase-2-vishwas-gitea-tasks.md`), captured through Krama's `ActionExecutor`. Each step has
its action, role, exact accessible name, typed value, URL path, bbox → coarse screen region, and its DOM context
(enclosing dialog / dropdown menu / top bar, nearest section heading). Scripts, inputs, every output and the
side-by-side table: [`assets/phase-2-vishwas-instruction-text/`](assets/phase-2-vishwas-instruction-text/)
(`comparison.md`).

**What the style guides say** [verified: Microsoft and Google style guides, links below]
- Start each step with an **imperative verb**, one action per step, a complete sentence ending in a period (both).
- Say **where before what**: "On the **Design** tab, select **Header Row**." / "In the Google Cloud console, go to
  the **Monitoring** page" (both).
- **Bold** UI element names, exactly as shown (both).
- **Google: avoid directional language** ("above", "below", "right-hand side") and "please". So "in the top-right `+`
  menu" from the issue is better said as a *container* ("In the top bar, open the **+** menu"). In an interactive
  tutorial the highlight shows the position anyway. Screen position is also wrong on mobile and at other zoom levels.
- Put the result or the reason after the action, or leave it out when the next step shows it (Google).

**Today's text (written by the planner at plan time)** breaks most of these. From the stored Phase 1 workflow and
the live plans for the new tasks [verified locally: `comparison.md` "Before"]:
"Click the New Repository link." · "Enter my-test-1 into the repository name input." ·
"Fill the 'Title' field with 'Login page shows a blank screen'." · "Click the 'Update Settings' button to save the
new description." · "Navigate to the new file creation page for the main branch."
Problems: labels not marked up and sometimes paraphrased ("the repository name input"), reasons appended, URLs or
abstract pages instead of names, and no location even inside a dialog. The planner can't do better at that
point: it only sees the start page (`PlanningService` plans from `/`), so it can't know that "Confirm" sits in a dialog.

**A rewrite after the run, from the executed steps**: one call per workflow, rules from the style guides in the
system prompt, step data (labels come from the page) as an untrusted block. Prompt: `instruct.py` `SYSTEM`.
Compared with a **template in plain code** (no LLM). Automatic checks per step: imperative start, exact label in
bold, exact value in backticks, multi-line values not pasted, dialog named first, ≤ 20 words, no
direction words, no invented bold labels [verified locally: `out-*.json`]:

| Provider | All checks pass | Time for 5 workflows |
|---|---|---|
| Template (no LLM) | 22/22 | 0 s |
| gemini-2.5-flash | 9/9 answered (13 steps lost: free-tier quota ran out mid-test) | 39.6 s incl. errors |
| gemini-3.8-flash, gemini-3.5-flash | not measured: daily quota already used up (`429`) | — |
| Llama 3.1 8B (Ollama, RTX 4050) | 19/22 | 56 s |

Reading the outputs (my judgement, check `comparison.md` yourself):
- **On structured step data the LLMs write almost exactly what the template writes.** Example, all providers:
  "In the **Create new branch** dialog, click **Confirm**." / "Enter `team-docs` in **Repository Name**." /
  "Select the **Initialize Repository** checkbox."
- The LLMs' own errors: Llama 3.1 wrote "enter **Description** with `Docs for the team`" and pasted the multi-line
  file content into the sentence. Gemini 2.5 copied page titles verbatim ("Go to the **Issues - krama-research-tasks**
  page").
- **The remaining bad steps come from the input data, and no provider fixed them:** "Under **Labels Milestones**,
  click **New Issue**" (those are tab links that my heading detection took for a section title), "Under **Commit
  Changes**, click **Commit Changes**" (heading = button label), "Go to the **Repository** page" for Settings (page
  title), and "**Editor content**" (Monaco's accessible name, meaningless to a person). Better context extraction in
  code fixes these. A better prompt doesn't, because the model has no more information than the template.
- Location: **containers worked better than screen regions.** A container (dialog or dropdown menu) was detected on 4
  of 18 targeted steps and a section heading on 6 more. All 4 containers and 4 of the 6 sections read naturally;
  the 2 bad sections are the ones listed above. The bbox → "top-right" region is available but conflicts with the
  Google rule, and the highlight already shows where.

**Security:** the step data is page text (labels, headings, titles), so it must stay an untrusted block, as tested.
The rewrite must never change the action, only the words. Its output only goes to `instruction_text`, never into
what runs.

## Recommendation
For #73 (`planner/`, mine):
1. **Fix the plan-time text in the planner prompt** (it's what the human approves): add the style rules (imperative,
   exact label in bold, value in backticks, no reasons, name the page, not the URL). Zero extra calls.
2. **Add a post-run rewrite in code** (a template like `instruct.py::template`) from the executed step + DOM context:
   container first (dialog / menu / top bar / section), exact label, value. It's deterministic, free, offline and
   testable. It should write the workflow step's `instruction_text`; the plan keeps what was approved.
   Capturing the context (dialog/menu/section) needs a small DOM read at action time, in `agent/` (mine). It should
   be stored with the step; where (the observer state or a new step field) is a #71 question.
3. **Use an LLM only as an optional polish** for labels a person can't use as is ("Editor content" → "the file
   editor"), if at all. The data says it adds little today. Re-test with Gemini 3.x once the quota is available,
   with a screenshot, which is the one input the template can't use.
4. Prefer containers to screen positions. Keep the bbox region only as a last fallback when no container is known
   (e.g. "the **+** button in the top bar").

## Open questions
- **Gemini 3.x not measured** (quota). Planned: rerun `instruct.py gemini:gemini-3.8-flash gemini:gemini-3.5-flash`
  after the daily reset (midnight Pacific ≈ 12:30 IST) and update this note before the PR leaves draft.
- Does the post-run rewrite replace the approved plan text in the tutorial, or is it shown next to it? Replacing is
  cleaner for the learner; the plan review keeps the original. **Decision for Vishwas + Nachiketha** (the player
  shows it).
- The automatic checks miss usefulness (the template passes 22/22 while 4 of its steps are poor), so a human still
  has to read the outputs. #73 should have before/after examples in the PR (the issue already asks for that).

## Links
- https://learn.microsoft.com/en-us/style-guide/procedures-instructions/writing-step-by-step-instructions
- https://developers.google.com/style/procedures
- https://ai.google.dev/gemini-api/docs/rate-limits ("Requests per day (RPD) quotas reset at midnight Pacific time")
- `backend/app/planner/prompt.py`, `backend/app/planner/service.py`
