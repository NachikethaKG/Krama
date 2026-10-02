"""Create the local Gitea admin and demo users (`just seed`). Safe to re-run.

These are throwaway local accounts from .env; they never leave this machine.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "--env-file", ".env", "-f", "infra/docker-compose.yml"]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.exists():
        sys.exit(".env not found - run `just setup` first")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def gitea(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*COMPOSE, "exec", "-T", "-u", "git", "gitea", "gitea", *args],
        cwd=ROOT, capture_output=True, text=True,
    )


def ensure_user(username: str, password: str, admin: bool) -> None:
    listed = gitea("admin", "user", "list")
    if listed.returncode != 0:
        sys.exit(f"cannot reach gitea (is `just up` running?):\n{listed.stderr}")
    if any(line.split()[1:2] == [username] for line in listed.stdout.splitlines()[1:]):
        print(f"  exists   {username}")
        return
    args = ["admin", "user", "create", "--username", username, "--password", password,
            "--email", f"{username}@krama.local", "--must-change-password=false"]
    if admin:
        args.append("--admin")
    created = gitea(*args)
    if created.returncode != 0:
        sys.exit(f"failed to create {username}:\n{created.stdout}{created.stderr}")
    print(f"  created  {username}")


def main() -> None:
    env = load_env()
    ensure_user(env["GITEA_ADMIN_USER"], env["GITEA_ADMIN_PASSWORD"], admin=True)
    ensure_user(env["GITEA_DEMO_USER"], env["GITEA_DEMO_PASSWORD"], admin=False)
    print(f"Gitea ready at {env.get('GITEA_URL', 'http://localhost:3001')}")


if __name__ == "__main__":
    main()
