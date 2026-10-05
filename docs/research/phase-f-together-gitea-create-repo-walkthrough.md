# Gitea "create a repository": step-by-step walkthrough

- **Phase:** F (Sprint F2)
- **Researched by:** Together (recorded by Claude Code on Vishwas's laptop, decisions by Vishwas; Nachiketha to review)
- **Question(s):** Do "create a repository" in local Gitea (user `demo`) and write down every step: what you click, the URL after, the heading you see. This becomes the first fixture and its `expected_state`s.

## Findings
- Local Gitea **1.22.6** at `http://localhost:3001` (Docker, `just up`), freshly reset with `just reset-gitea` [verified locally]
- Recorded with Playwright for Python 1.63 driving headless Chromium at 1280×800. Raw data: [`assets/phase-f-gitea-create-repo/walkthrough.json`](assets/phase-f-gitea-create-repo/walkthrough.json); screenshots in the same folder; recorder: `record_walkthrough.py` [verified locally]

**Precondition:** signed in as `demo`. Start page `/`, title `demo - Dashboard - Gitea: Git with a cup of tea`.

| # | Action | Target (ARIA role + name) | URL after | Expected state (how to verify) | Screenshot |
|---|---|---|---|---|---|
| 1 | click | `menu "Create…"` (the **+** in the top bar) | `/` (unchanged) | `menuitem "New Repository"` visible | [step-1](assets/phase-f-gitea-create-repo/step-1.png) |
| 2 | click | `menuitem "New Repository"` | `/repo/create` | URL `^/repo/create$`; heading `New Repository`; title starts `New Repository` | [step-2](assets/phase-f-gitea-create-repo/step-2.png) |
| 3 | fill `demo-repo` | `textbox "Repository Name *"` | `/repo/create` | textbox value = `demo-repo` | [step-3](assets/phase-f-gitea-create-repo/step-3.png) |
| 4 | click | `checkbox "Initialize Repository (Adds .gitignore, License and README)"` | `/repo/create` | checkbox checked | [step-4](assets/phase-f-gitea-create-repo/step-4.png) |
| 5 | click | `button "Create Repository"` | `/demo/demo-repo` | URL `^/demo/demo-repo$`; title starts `demo/demo-repo`; README heading `demo-repo` visible | [step-5](assets/phase-f-gitea-create-repo/step-5.png) |

All five steps succeeded on the first run [verified locally].

**Negative case (same name again)** [verified locally]: the URL stays `/repo/create`, and the title and heading are unchanged (`New Repository`). The **only** difference is a banner: *"The repository name is already used."* ([screenshot](assets/phase-f-gitea-create-repo/negative-duplicate.png)).

**Things the agent and verifier must handle** [verified locally]:
- **Never wait for `networkidle`** on Gitea: it timed out after 30 s on the dashboard, because Gitea keeps a background connection open. Wait for a URL (`wait_for_url`) or an element instead.
- **Required-field labels end in ` *`** (`"Repository Name *"`, `"Password *"`). Role/label matching must not be exact. Playwright's default substring match worked.
- The **+** menu is `role="menu"` with `aria-expanded`, and its entries are `role="menuitem"`. The dashboard's *Repositories* panel has a second **+** that leads to the same `/repo/create`; accept either path.
- The form has many optional fields (description, template, labels, .gitignore, license, README template, default branch `main`, object format `sha1`). Leaving them alone gives a valid repo.
- The `bbox` values in the JSON are viewport coordinates at 1280×800 (`walkthrough.json` → `target.bbox`).

## Recommendation
Decisions (Vishwas):
- **Login is a precondition**, not a workflow step: `preconditions: {"logged_in_as": "demo"}`, which `database-schema.md` already has. Tutorials teach the task; saved sessions arrive in Phase 3.
- **Include the "Initialize Repository" step**: it matches the PRD's "configure initialization", and the README on the result page is a clear success signal. 5 steps total.
- **Opening the + menu is its own step**, so the tutorial can highlight the small **+** first and each step has its own verifiable state.

For the fixture task (#20) and the schemas (#14, #15):
- `expected_state` needs at least: `url_matches` (regex on the **path**), `visible` (list of `{role, name}`), plus a way to say "this field has value X" and "this checkbox is checked" (steps 3 and 4).
- The **verifier (#36) must check that the URL changed to the expected page.** A "page loaded without errors" check would pass the duplicate-name failure.

## Open questions
- Nachiketha: does this match what you see doing it by hand in the browser?
- How should `expected_state` express form values (`{"field": {role, name, value}}` vs `{"checked": [...]}`)? Decide in the schema PR (#15).
- Should the fixture's repo name be fixed (`demo-repo`) or come from the task's parameters? The planner will extract it from the prompt, so the fixture should show it as a parameter.

## Links
- [`assets/phase-f-gitea-create-repo/`](assets/phase-f-gitea-create-repo/): raw JSON, screenshots, recorder script
- https://playwright.dev/python/docs/aria-snapshots
