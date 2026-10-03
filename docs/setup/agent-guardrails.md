# One-time setup on each laptop

Do this once after cloning. It sets up layers 2 and 3 of the guardrails (see `docs/phases.md` §4).

## 1. Tell git (and the AI agents) who you are

```powershell
git config krama.owner vishwas        # or: nachiketha
"vishwas" | Out-File -Encoding ascii .krama-owner   # or nachiketha (git-ignored, read by agents)
```

## 2. Install the pre-commit hook

```powershell
uv tool install pre-commit
pre-commit install          # installs both the pre-commit and commit-msg hooks
```

From then on, a commit is rejected if it stages files outside your area or if its message isn't a Conventional Commit.

## 3. Hard-block Claude Code from the other person's area

Create `.claude/settings.local.json` (git-ignored).

**Vishwas:**
```json
{
  "permissions": {
    "deny": [
      "Edit(frontend/**)", "Write(frontend/**)",
      "Edit(packages/**)", "Write(packages/**)",
      "Edit(benchmarks/harness/**)", "Write(benchmarks/harness/**)",
      "Edit(backend/app/observer/**)", "Write(backend/app/observer/**)",
      "Edit(backend/app/policy/**)", "Write(backend/app/policy/**)",
      "Edit(backend/app/validation/**)", "Write(backend/app/validation/**)",
      "Edit(backend/app/export/**)", "Write(backend/app/export/**)",
      "Edit(backend/tests/observer/**)", "Write(backend/tests/observer/**)",
      "Edit(backend/tests/policy/**)", "Write(backend/tests/policy/**)",
      "Edit(backend/tests/validation/**)", "Write(backend/tests/validation/**)",
      "Edit(backend/tests/export/**)", "Write(backend/tests/export/**)",
      "Edit(backend/app/contracts_gen/**)", "Write(backend/app/contracts_gen/**)"
    ]
  }
}
```

**Nachiketha:**
```json
{
  "permissions": {
    "deny": [
      "Edit(backend/app/agent/**)", "Write(backend/app/agent/**)",
      "Edit(backend/app/planner/**)", "Write(backend/app/planner/**)",
      "Edit(backend/app/verifier/**)", "Write(backend/app/verifier/**)",
      "Edit(backend/app/runs/**)", "Write(backend/app/runs/**)",
      "Edit(backend/app/api/**)", "Write(backend/app/api/**)",
      "Edit(backend/app/db/**)", "Write(backend/app/db/**)",
      "Edit(backend/app/llm/**)", "Write(backend/app/llm/**)",
      "Edit(backend/app/storage/**)", "Write(backend/app/storage/**)",
      "Edit(backend/app/tts/**)", "Write(backend/app/tts/**)",
      "Edit(backend/tests/agent/**)", "Write(backend/tests/agent/**)",
      "Edit(backend/tests/planner/**)", "Write(backend/tests/planner/**)",
      "Edit(backend/tests/verifier/**)", "Write(backend/tests/verifier/**)",
      "Edit(backend/tests/runs/**)", "Write(backend/tests/runs/**)",
      "Edit(backend/tests/api/**)", "Write(backend/tests/api/**)",
      "Edit(backend/tests/db/**)", "Write(backend/tests/db/**)",
      "Edit(backend/tests/llm/**)", "Write(backend/tests/llm/**)",
      "Edit(backend/tests/storage/**)", "Write(backend/tests/storage/**)",
      "Edit(backend/tests/tts/**)", "Write(backend/tests/tts/**)",
      "Edit(backend/alembic/**)", "Write(backend/alembic/**)",
      "Edit(backend/app/main.py)", "Write(backend/app/main.py)",
      "Edit(backend/app/config.py)", "Write(backend/app/config.py)",
      "Edit(backend/justfile)", "Write(backend/justfile)",
      "Edit(backend/app/contracts_gen/**)", "Write(backend/app/contracts_gen/**)",
      "Edit(packages/contracts-ts/**)", "Write(packages/contracts-ts/**)"
    ]
  }
}
```

Claude Code deny rules always win over allow rules, so "all of `backend/` except my modules" can't be expressed: each of the other person's folders is listed instead. When a new backend module is added, add it here and in `OWNERSHIP.toml`.

Antigravity reads `AGENTS.md`. It has no hard deny like this, so the pre-commit hook and CODEOWNERS are its safety net.

## 4. Limit Docker's RAM (important on 16GB)

`%UserProfile%\.wslconfig`:
```ini
[wsl2]
memory=4GB
processors=4
```
Then run `wsl --shutdown` and restart Docker Desktop.

## 5. Daily habit

```powershell
git switch main; git pull
git switch -c feat/<area>/<issue#>-slug   # new task
# or, continuing a task:
git fetch; git rebase origin/main
```
