# Krama

Verified UI Tutorial Engine: turns a natural-language software question into a **verified, interactive tutorial** grounded in the real application's UI.

Prompt → Plan → Human approval → Isolated browser execution → Per-step verification → Verified Workflow → Interactive tutorial (MP4 later).

## Quick start (Windows, both laptops)

Prerequisites: Git, Docker Desktop (WSL2), [uv](https://docs.astral.sh/uv/), Node 22. Then `corepack enable pnpm`, `uv tool install rust-just` and `uv tool install pre-commit`.

```powershell
git clone https://github.com/NachikethaKG/Krama.git; cd Krama
just setup    # checks tools, creates .env, installs git hooks + all dependencies
just up       # Postgres :5433, Redis :6379, Gitea :3001
just seed     # Gitea users: krama-admin, demo (local-only passwords in .env)
```
**Run the whole app** (after the setup above): `.\start-krama.bat` from the repo root starts Docker Desktop if
needed, Postgres/Redis/Gitea, migrations, the API (:8000) and the web app in real mode (:3000) in their own
windows, and opens http://localhost:3000/login (sign in as `demo@krama.dev` with `KRAMA_DEMO_PASSWORD` from `.env`).
`.\stop-krama.bat` stops it all (`-KeepDocker` leaves the containers running).

`just dev` starts the API (:8000) and web app (:3000, mock mode unless `NEXT_PUBLIC_API_MODE=http`). `just check` runs what CI runs. `just` lists every command. `just reset-gitea` wipes the test site back to a clean state.

## Docs

- Phases, sprints and per-person research lists: [`docs/phases/`](docs/phases/README.md) · research notes: [`docs/research/`](docs/research/README.md)
- Architecture: [`docs/architecture.md`](docs/architecture.md) · API: [`docs/api-contract.md`](docs/api-contract.md) · DB: [`docs/database-schema.md`](docs/database-schema.md)
- How we work (issues, commits, review, Definition of Done): [`docs/development-workflow.md`](docs/development-workflow.md)
- Rules for AI agents and ownership: [`AGENTS.md`](AGENTS.md), [`OWNERSHIP.toml`](OWNERSHIP.toml)
- First-time laptop setup: [`docs/setup/agent-guardrails.md`](docs/setup/agent-guardrails.md)

| Area | Owner |
|---|---|
| `backend/` (agent, verification, API, DB) | Vishwas |
| `frontend/`, `packages/` (UI, tutorial compiler, player) | Nachiketha |
| `contracts/` | both |
