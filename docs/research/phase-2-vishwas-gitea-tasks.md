# More Gitea tasks: issue, branch, file, settings

- **Phase:** 2
- **Researched by:** Vishwas (experiments run by Claude Code on Vishwas's laptop, decisions by Vishwas)
- **Question(s):** **More Gitea tasks:** create an issue, create a branch, add a file, change repo settings. Which are stable, which need extra setup?

## Findings
Experiments ran on 2026-10-16 against local Gitea 1.22.6 (`demo` user), Playwright 1.63.0, viewport 1280×800, through
Krama's real `ActionExecutor` (role/name → label → text → selector chain). Planner tests used live Gemini through
`LLMPlanner` with today's prompt (the chain fell through to `gemini-2.5-flash` both times). Scripts, ARIA snapshots,
screenshots and raw results: [`assets/phase-2-vishwas-gitea-tasks/`](assets/phase-2-vishwas-gitea-tasks/).

**Setup every task needs** [verified locally]
- A repository **with at least one commit**. An empty repo has a different home page (no "Add File" menu, no `main`
  branch to branch from). Created per trial with `POST /api/v1/user/repos {"name", "auto_init": true}`
  (≈0.3 s), deleted with `DELETE /api/v1/repos/{owner}/{repo}`.
- Nothing else: no extra users, no tokens, no SSH. All four work as `demo` over the web UI.

**The flows, as ARIA sees them** (from `*.aria.yaml`)

| Task | Pages and targets | Success check (API) |
|---|---|---|
| Create issue | `/{o}/{r}/issues/new`: textbox "Title", textbox "Leave a comment", button "Create Issue" → `/{o}/{r}/issues/1` | `GET /repos/{o}/{r}/issues?state=all&type=issues` has the title |
| Create branch | `/{o}/{r}/branches`: button `Create new branch from "main"` opens a modal with textbox "Branch Name \*" and button "Confirm" | `GET /repos/{o}/{r}/branches/{name}` → 200 |
| Add file | `/{o}/{r}`: "Add File" menu → "New File" (or go straight to `/{o}/{r}/_new/main/`): textbox "Name your file…", textbox "Editor content" (Monaco), button "Commit Changes" | `GET /repos/{o}/{r}/contents/{path}` content matches |
| Repo settings | `/{o}/{r}/settings`: textbox "Description", then **one of three** buttons "Update Settings" | `GET /repos/{o}/{r}` → `description` |

**Executor stability (hand-written steps, no planner)** [verified locally: `run_tasks.py`, `results-5-trials.txt`]

| Task | Trials | Notes |
|---|---|---|
| Create issue | 5/5 | ~1 s |
| Create branch | 5/5 | ~1.4–4 s |
| Add file | 5/5 | `fill` works on Monaco's "Editor content" textbox, multi-line content included |
| Repo settings, role+name | **0/1** | `ambiguous_target`: three visible "Update Settings" buttons (Basic, Advanced, Signing) |
| Repo settings, CSS selector `form:has(textarea#description) button.primary` | 5/5 | |
| Repo settings, role+name + Gemini vision fallback | 3/3 | 5–7 s extra per run for the vision call |

**The planner can't plan these from the dashboard alone** [verified locally: `plan_tasks.py`, `plans-live-1.json`]
- Planning starts on `/` (that's what `PlanningService` does), so the planner sees only the dashboard snapshot, and
  `SITE_HINTS["gitea"]` describes only repo creation. Result with live Gemini: **0/4**.
  - 3/4 plans began by clicking link "demo/krama-research-tasks" on the dashboard, which matches twice → `ambiguous_target`.
  - The add-file plan guessed textbox "File name" (the real name is "Name your file…") → `target_not_found`.
- With **site hints for the four flows** (pages, exact names, the result URL, "navigate to repo pages directly", the
  settings selector) the same planner went **4/4**: every plan executed and passed the API check
  [verified locally: `plans-live-hints-1.json`]. The hints used are in `plan_tasks.py` (`HINTS`).
- So which tasks are stable is mostly a question of **hints**, not of Gitea. Without hints the run would rely on
  replanning after the first failure. That costs an extra Gemini call and a human re-approval (`replan_review`).

**A locator-chain hazard found on the way** [verified locally: `branch_modal.py`]
- With my first, wrong guess `button "Create branch"`, the **text** fallback matched a `<div>` with the text
  "Create branch from branch: main" (substring match), clicked it and reported `ok`. Nothing happened on the page.
  The verifier would catch it (no effect), but the executor accepting a non-interactive element through the text
  strategy is worth tightening. One option: accept a text match only if it is (inside) a link, button,
  `[role=menuitem]` or a form control. This is in `agent/` (mine); a candidate for #73/#72 or a Phase 3 hardening issue.
- Related: role names match **case-insensitively as substrings** (Playwright `exact=False`), so a planned
  "Add file" found "Add File". That helps with small wording drift and is also why a wrong name can hit a longer one.

**Reset between benchmark runs** (what exists today) [verified locally]
- `benchmarks/gitea.py::reset_gitea_api` deletes all repos of the user. But it lists them with the default page size
  (**30**), so with more repos it leaves the rest behind. The demo user has ≥ 50 repos right now (`?limit=50` returns
  50, the default returns 30). It also doesn't create the starting repo these tasks need.
- `benchmarks/tasks/gitea-create-repo.yaml` uses `http://localhost:3000` and user `krama-user`. Our Gitea is on `:3001`
  with user `demo`.
- The benchmark runner grades a trial by the **agent's own** `verified` status (`benchmarks/agent_runner.py:30`).
  The task YAML's `setup` and `success_check` are loaded by `load_task_from_yaml` but used nowhere, although
  `benchmarks/tasks/README.md` says "the agent never grades itself". For the Phase 2 exit criterion "5 Gitea
  workflows pass the benchmark at ≥ 80%", that has to change.

## Recommendation
For #78:
1. Add the four tasks as YAML in `benchmarks/tasks/` (shared), each with:
   `setup` = delete + create `demo/<repo>` with `auto_init` (API), `success_check` = the API checks in the table.
   Use `:3001` and `demo`, and fix `gitea-create-repo.yaml` the same way.
2. Add site hints for the four flows to `planner/prompt.py` (mine), based on the `HINTS` block tested here.
   Without them the planner fails all four; with them it passed 4/4.
3. Reset per task, not a full Gitea wipe: delete + re-create only the task's repo through the API (≈0.3 s). A full
   reset (Docker volume wipe + `just seed`) isn't needed for these tasks.
4. The benchmark harness changes (use YAML `setup`/`success_check`, page through the repo list in
   `reset_gitea_api`) are in `benchmarks/` = **Nachiketha's area**. They could go into his #82 (benchmark report),
   or into a cross-boundary PR from me if he agrees. **Decision for Vishwas + Nachiketha.**
5. Settings task: put the selector in the hint (it worked 5/5) rather than relying on vision (slow, uses quota).

Stability ranking: create issue ≈ create branch ≈ add file (stable, no surprises) > repo settings (stable only with
the selector or vision, because of the three identical buttons).

## Open questions
- Does the planner keep 4/4 over many trials? Only one live trial per task was run (free-tier quota). The benchmark
  in #78 will measure it.
- Should hints become per-flow documents (one per task) instead of one growing `SITE_HINTS["gitea"]` string? With 5
  flows it is still small (~20 lines); revisit at Phase 3 (GitHub).

## Links
- https://docs.gitea.com/api/1.22/ (repos, branches, contents, issues endpoints)
- https://playwright.dev/python/docs/api/class-page#page-get-by-role (`exact` defaults to case-insensitive substring)
- `backend/app/planner/prompt.py` (`SITE_HINTS`), `backend/app/planner/service.py` (planning starts on `/`)
