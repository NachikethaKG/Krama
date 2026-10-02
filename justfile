# Root task runner. SHARED file: only infra and cross-cutting recipes live here.
# Backend commands go in backend/justfile (Vishwas), frontend ones in frontend/justfile (Nachiketha).
# They are optional modules, so this works before those folders exist:  just backend <recipe>, just frontend <recipe>
# Install just once:  uv tool install rust-just

set dotenv-load
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

mod? backend 'backend/justfile'
mod? frontend 'frontend/justfile'

compose := "docker compose --env-file .env -f infra/docker-compose.yml"

# List recipes
default:
    @just --list --list-submodules

# One-time setup after cloning
setup:
    uv run --no-project --python 3.12 scripts/dev_setup.py

# Backend (:8000) and frontend (:3000) dev servers together
dev:
    uv run --no-project --python 3.12 scripts/dev.py

# Lint, typecheck, test and build both halves (what CI runs)
check:
    just backend check
    just frontend check

# Start Postgres, Redis and Gitea, and wait until they are healthy
up:
    {{compose}} up -d --wait

# Stop services (data is kept)
down:
    {{compose}} down

# Service status
ps:
    {{compose}} ps

# Follow logs, e.g. `just logs gitea`
logs service="":
    {{compose}} logs -f {{service}}

# Create the Gitea admin and demo users (safe to re-run)
seed:
    uv run --no-project --python 3.12 scripts/seed_gitea.py

# Wipe Gitea back to a clean state (deletes all its repos), then re-seed
reset-gitea:
    {{compose}} rm -sf gitea
    docker volume rm -f krama_gitea-data
    {{compose}} up -d --wait gitea
    just seed

# Ownership check on staged files
check-ownership:
    uv run --no-project --python 3.12 scripts/check_ownership.py

# Run every git hook on all files
hooks:
    pre-commit run --all-files
