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
      "Edit(backend/**)", "Write(backend/**)",
      "Edit(packages/contracts-ts/**)", "Write(packages/contracts-ts/**)"
    ]
  }
}
```

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
