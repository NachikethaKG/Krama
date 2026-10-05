# Development workflow

How the two of us (and our AI agents) work together without blocking each other or causing merge conflicts.
Agent-specific rules: [`AGENTS.md`](../AGENTS.md). Ownership: [`OWNERSHIP.toml`](../OWNERSHIP.toml).

## 1. Who owns what

Ownership is by module, so **both of us work on the backend** without sharing files ([ADR 0001](adr/0001-ownership-by-module.md)).

| Owned alone | Owner |
|---|---|
| Backend core: `agent/`, `planner/`, `verifier/`, `runs/`, `api/`, `db/` + migrations, `llm/`, `storage/`, `tts/` | Vishwas |
| Backend modules: `observer/` (capture + recording), `policy/` (safety), `validation/` (drift), `export/` (video jobs), plus `benchmarks/` | Nachiketha |
| `frontend/`, `packages/`: UI, tutorial compiler, player, video exporter | Nachiketha |

**Defined jointly** (changes need both to agree; PRs need both reviewers):

| Shared thing | Where it lives |
|---|---|
| Architecture | [`architecture.md`](architecture.md) + ADRs |
| API contract | [`api-contract.md`](api-contract.md), `contracts/` |
| Backend module interfaces | `backend/app/ports/` (Python `Protocol`s between modules owned by different people) |
| Backend dependencies | `backend/pyproject.toml`, `backend/uv.lock`: tiny separate `build(deps)` PRs only |
| Database schema (*what* the tables are) | [`database-schema.md`](database-schema.md) |
| Docker / dev environment | `infra/`, `justfile`, `.env.example` |
| Git workflow, review rules, Definition of Done | this file |
| Testing strategy | §9 below |
| Agent rules | `AGENTS.md` |

## 2. The flow for every piece of work

```
Issue  →  Branch  →  small commits  →  PR  →  CI  →  1 review  →  rebase merge  →  issue closed
```

1. **Issue first.** No branch without an issue.
2. **Branch** from up-to-date `main`: `feat/<area>/<issue#>-<slug>`, e.g. `feat/verifier/34-aria-assertions`.
3. **Commit small and often** (see §4) and push your branch regularly.
4. **Open the PR early** as a draft if you want feedback. Mark it ready when the Definition of Done is met.
5. **Rebase and merge** once CI is green and it's approved (keeps every small commit on `main` with a linear history; never squash). Delete the branch. Because each commit lands on `main` individually, every commit must pass hooks and make sense on its own.

Daily: `git switch main && git pull`, then `git rebase origin/main` on your branch *before* you start your AI agent session.

## 3. Issues represent real work

- **One issue = one PR = a few working sessions at most.** If it's bigger, split it.
- The title starts with a verb and names the outcome: ✅ `Add ARIA-based state assertions to verifier`, ❌ `Verifier`.
- Each issue lists **allowed paths** (the AI agent's scope) and **Done when** (template: `.github/ISSUE_TEMPLATE/task.yml`).
- Sprint = **Milestone** (e.g. `Phase 0 / Sprint 0.2`). Phase = **Project board** (Backlog → Ready → In progress → In review → Done).
- Labels: `area:backend`, `area:frontend`, `area:compiler`, `shared`, `contract-change`, `cross-boundary`, `bug`, `phase:N`, `good-first-cross`.

Example: the sprint item "layered verifier" becomes:
`#40 Add URL/DOM assertions to verifier` · `#41 Add ARIA snapshot assertions` · `#42 Add network-signal verification` · `#43 Add LLM vision fallback with confidence` · `#44 Add verifier accuracy tests on recorded failures`

## 4. Commits

[Conventional Commits](https://www.conventionalcommits.org/), enforced by a commit-msg hook:

```
<type>(<scope>): <imperative summary, lower case, no period>
```

**Types:** `feat` `fix` `refactor` `test` `docs` `chore` `perf` `ci` `build`
**Scopes:** backend: `agent` `planner` `verifier` `policy` `observer` `llm` `api` `db` `runs` · frontend: `ui` `plan-review` `live-view` `player` `compiler` `overlay` `tts` `export` · shared: `contracts` `infra` `ci` `docs` `scripts` `bench`

Examples: `feat(verifier): add aria snapshot assertions` · `test(planner): cover ambiguous repo-name prompt` · `fix(player): keep cursor in sync after seek` · `feat(contracts): add run.paused event`

Commit one logical change at a time. A commit should still make sense on its own when you read it in `git log`.

## 5. Definition of Done

A task is done only when **all** of these hold:

- [ ] Implementation complete for the issue's "Done when"
- [ ] Tests added: happy path **and** at least one failure/edge case
- [ ] Lint + type check pass (backend: `ruff`, `mypy` · frontend: `eslint`, `tsc`)
- [ ] Works with mocks **and** with the real dependency if that dependency exists yet
- [ ] Runs on **Nachiketha's laptop** (if it touches runtime behaviour, infra or deps)
- [ ] Contract fixtures still validate; docs updated if behaviour or API changed
- [ ] No secrets, unmasked credentials or real personal data in code, fixtures or screenshots
- [ ] CI green, 1 review approved, rebase-merged to `main`, issue closed

## 6. Code review

**One reviewer is enough**: the other person. Contract PRs (`contracts/**`) need **both**, which means the author plus the other person, because the author is also a consumer.

The reviewer checks:
1. **Does it work?** Pull the branch and run it if it changes behaviour.
2. **Is the architecture right?** It uses the interfaces and seams in `architecture.md`; no shortcut around policy or verifier.
3. **Are there tests?** Including a failure case.
4. **Is the naming clear?**
5. **Does it break the other module?** Contract drift, changed fixtures, shared files.
6. **Are new dependencies necessary?** And do they run without a GPU?
7. **Is error handling present?** Especially browser timeouts, LLM errors, rate limits.
8. **Is any of it safety-relevant?** Masking, untrusted page text, destructive actions.
9. **Does it need docs?**

Comment prefixes keep it light: `blocker:` (must fix) · `question:` · `nit:` (optional). Approve with nits; don't block on style that the linter could catch.
**AI-written code gets the same review as human code.** "The agent wrote it" is not a reason to skip any check.

## 7. Contract changes

1. Open an issue from the `Contract change` template.
2. Open a PR on branch `contract/<issue#>-<slug>` touching **only** `contracts/**`, the regenerated `contracts_gen/` / `contracts-ts/`, fixtures, `contracts/CHANGELOG.md` and the matching doc (`api-contract.md` / `database-schema.md`).
3. Both approve, then merge.
4. Each person adapts their own side in separate PRs. Mocks and fixtures are already updated, so nobody is blocked.

Additive change (new optional field, new event): minor version bump. Breaking change: major version bump plus an ADR.

## 8. Shared files

`infra/`, `.github/`, `justfile`, `AGENTS.md`, `OWNERSHIP.toml`, root configs:
- change them in **small dedicated `chore/` PRs**, never mixed into feature work;
- tell the other person before starting, so only one person edits shared files at a time;
- the root `justfile` only imports `backend/justfile` and `frontend/justfile`. **Add your commands to your own sub-justfile**, never to the root.

## 9. Testing strategy

| Level | What | Tooling | Network / LLM |
|---|---|---|---|
| Unit | planner, verifier rules, policy, masking, compiler | pytest, vitest | none (`FakeProvider`) |
| Contract | fixtures validate against schemas; generated types up to date; responses match `openapi.json` | CI drift job | none |
| Integration | agent against Gitea in Docker | pytest + Playwright | `FakeProvider` |
| Frontend e2e | UI against `MockApiClient` | Playwright | none |
| Live e2e | benchmark tasks with real Gemini | `just e2e-live` | Gemini (manual, not in CI) |

CI runs everything except live e2e on every PR.

## 10. CI pipeline

```
push → PR → GitHub Actions
             ├─ ownership report
             ├─ backend:  ruff · mypy · pytest            (runs once backend/ exists)
             ├─ frontend: eslint · tsc · vitest · build  (runs once frontend/ exists)
             └─ contracts drift: just gen-contracts, then fail on any change (models, openapi.json, TS types)
          → 1 review → rebase merge
```

## 11. Environment setup (both laptops)

Prerequisites: Git, Docker Desktop (WSL2), [uv](https://docs.astral.sh/uv/), Node 22 (via nvm), then `corepack enable pnpm`, `uv tool install rust-just` and `uv tool install pre-commit`.

```powershell
git clone https://github.com/NachikethaKG/Krama.git; cd Krama
just setup     # copies .env.example → .env, installs git hooks, sets up both halves
just up        # Postgres, Redis, Gitea in Docker
just seed      # creates the Gitea demo users
just dev       # backend :8000 + frontend :3000
```

Versions are pinned (`.python-version`, `.nvmrc`, Docker image tags, lockfiles), so nobody has to ask "which Python / Postgres / Redis are you on?".
Secrets live only in `.env` (git-ignored). New variables go into `.env.example` in the same PR, with a comment.
