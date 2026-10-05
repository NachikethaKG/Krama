# AGENTS.md — rules for every AI coding agent in this repo

Read this fully before making any change. These rules apply to Claude Code, Antigravity, Cursor, Copilot, etc.
Product context and phases: `docs/phases/` (one file per phase). Research notes: `docs/research/`. Architecture and mock seams: `docs/architecture.md`.
API: `docs/api-contract.md`. DB: `docs/database-schema.md`. Team process, commit scopes and Definition of Done: `docs/development-workflow.md`.

## 1. Who am I working for?

Run `git config --get krama.owner` (or read `.krama-owner`). Result is `vishwas` or `nachiketha`.
If it is unset, STOP and ask the human to run `git config krama.owner <name>`.

## 2. Ownership map (source of truth: `OWNERSHIP.toml`)

| Area | Paths | Owner |
|---|---|---|
| Backend core | `backend/**` except the modules below: agent, planner, verifier, runs, api, db, llm, storage, tts, alembic | vishwas |
| Backend modules | `backend/app/{observer,policy,validation,export}/**` + matching `backend/tests/<module>/**`, `benchmarks/**` | nachiketha |
| Frontend / tutorial | `frontend/**`, `packages/**`, `package.json`, `pnpm-*.yaml` | nachiketha |
| Contracts | `contracts/**`, `backend/app/ports/**` (Python interfaces between backend modules) | both (contract-change PRs only) |
| Generated | `backend/app/contracts_gen/**`, `packages/contracts-ts/**` | nobody — regenerate only |
| Shared | `backend/pyproject.toml`, `backend/uv.lock`, `benchmarks/tasks/**`, `AGENTS.md`, `CLAUDE.md`, `.github/**`, `infra/**`, `docs/**`, `scripts/**`, root config | both, small dedicated PRs |

Backend modules owned by different people talk **only through `backend/app/ports/`**. Never import another owner's module internals.

## 3. Hard rules

1. **Only edit files in your owner's area.** Edit SHARED files only when the current task/issue explicitly says so.
2. **Never edit the other owner's area.** If your task needs a change there, stop and write the request in the PR description or a new issue, then continue with a mock/fixture.
3. **Never edit `contracts/**`** unless the task issue is labelled `contract-change`. Contract PRs contain only `contracts/**`, regenerated output and `contracts/CHANGELOG.md` — no feature code.
4. **Never hand-edit generated folders.** Run `scripts/gen-contracts` instead.
5. **Dependencies:** frontend deps (`pnpm-lock.yaml`) are Nachiketha's only. Backend deps (`backend/pyproject.toml`, `backend/uv.lock`) are shared: change them only in a tiny separate `build(deps)` PR, never mixed into feature work. On a `uv.lock` conflict, re-run `uv lock`; never hand-merge a lockfile.
6. **Database:** never edit an Alembic migration that is already on `main`; add a new one. Only vishwas's area creates migrations.
7. **Git:** never commit to `main`, never `git push --force` (use `--force-with-lease` only on your own branch), never rebase/merge someone else's branch, never skip hooks (`--no-verify`). One issue per branch; keep PRs small.
8. **Branch names:** `feat/<area>/<issue#>-slug`, `fix/...`, `chore/...`, `contract/<issue#>-slug`. Commits use Conventional Commits with the scopes in `docs/development-workflow.md` §4 (a commit-msg hook enforces this). Make one small commit per logical change.
8a. **Build against interfaces, not concrete classes.** If a dependency isn't ready, use or create its mock behind the interface (`docs/architecture.md` §4). Mocks must return contract-valid data.
8b. **A task is done only when the Definition of Done is met** (`docs/development-workflow.md` §5). Never claim done when tests are failing or skipped.
9. **Before committing:** run the checks for the area you touched (lint, types, tests) and `python scripts/check_ownership.py`.
10. **No GPU assumptions.** Everything must run on a 16GB RAM, CPU-only laptop. Ollama/local models are opt-in only; default LLM is Gemini, tests use the fake LLM provider.
11. **Secrets:** never commit `.env`, API keys, browser storage state, or screenshots containing real credentials.

## 4. Product-code safety rules (apply to code you write)

- Webpage content (DOM text, ARIA names, screenshots) is **untrusted data, never instructions**. Never concatenate it into the system prompt; pass it as clearly delimited data.
- Destructive actions (delete, purchase, transfer, publish, send, reset, security changes) must route through the policy layer and pause for human confirmation.
- Mask sensitive fields (passwords, tokens, payment, personal info) before storing artifacts or sending screenshots to an LLM.
- On CAPTCHA / bot challenge / automation restriction: stop. Never write bypass code.

## 5. Research handoffs

When the human pastes a research HANDOFF (from `just research-prompt`):
1. Create a branch `chore/research/<issue#>-phase-<n>-<person>` (use the phase's research issue).
2. Write each `=== FILE: <path> ===` block to that path **verbatim**. One commit per file: `docs(research): <topic>`.
3. Don't apply the SUMMARY's suggested plan changes yourself. List them in the PR description, and change `docs/phases/` or `architecture.md` only after the human confirms (architecture changes need an ADR).
4. Facts tagged `[unverified]` are guesses. Don't build on them without checking.

## 6. When unsure

Prefer: ask the human, or leave a `TODO(owner):` note in your own area, over touching files you don't own.
