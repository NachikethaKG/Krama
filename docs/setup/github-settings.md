# GitHub repo settings (repo admin only: Nachiketha)

These can't go in code, so the repo owner applies them once in the GitHub UI.

## 1. Merge buttons: Settings → General → Pull Requests

- ☐ Allow merge commits: **off**
- ☐ Allow squash merging: **off** (it would turn our small commits into one)
- ☑ Allow rebase merging: **on**
- ☑ Automatically delete head branches: **on**
- ☑ Always suggest updating pull request branches: **on**

## 2. Protect `main`: Settings → Rules → Rulesets → New branch ruleset

- Name: `main`, Enforcement: **Active**, Target: **Default branch**
- ☑ Restrict deletions
- ☑ Require linear history
- ☑ Require a pull request before merging
  - Required approvals: **1**
  - ☑ Require review from Code Owners
  - ☑ Dismiss stale pull request approvals when new commits are pushed
  - ☑ Require conversation resolution before merging
- ☑ Require status checks to pass (add them after CI has run once on a PR so they show up in the list):
  - `Hygiene hooks`
  - `Backend (ruff, mypy, pytest)`
  - `Frontend (lint, typecheck, test, build)`
  - ☑ Require branches to be up to date before merging
- ☑ Block force pushes
- Bypass list: **empty** (the rules apply to the owner too)

## 3. Collaborator access: Settings → Collaborators

Vishwas (`Vishwas721`) needs the **Maintain** role so he can manage labels, milestones and the Project board.
Rulesets still apply to Maintain users.

## 4. Project board

Projects → New project → Board, named **Krama**. Columns: Backlog · Ready · In progress · In review · Done.
Link it to the repo (Project → Settings → Manage access / link repository).
