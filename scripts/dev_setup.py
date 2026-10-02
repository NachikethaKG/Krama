"""One-time setup after cloning (`just setup`). Safe to re-run.

- checks required tools are installed
- creates .env from .env.example if missing
- installs git hooks (pre-commit + commit-msg)
- reminds you to set your owner identity
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TOOLS = {
    "git": "https://git-scm.com/",
    "docker": "Docker Desktop (WSL2): https://www.docker.com/products/docker-desktop/",
    "uv": "https://docs.astral.sh/uv/",
    "node": "Node 22 via nvm-windows: https://github.com/coreybutler/nvm-windows",
    "pre-commit": "uv tool install pre-commit",
    "just": "uv tool install rust-just",
}


def main() -> int:
    missing = [name for name in TOOLS if shutil.which(name) is None]
    for name in TOOLS:
        print(f"  {'ok ' if name not in missing else 'MISSING'}  {name}")
    if missing:
        print("\nInstall the missing tools, then re-run `just setup`:")
        for name in missing:
            print(f"  {name}: {TOOLS[name]}")
        return 1

    env, example = ROOT / ".env", ROOT / ".env.example"
    if env.exists():
        print(".env already exists - left untouched")
    else:
        shutil.copyfile(example, env)
        print("created .env from .env.example - add your GEMINI_API_KEY")

    subprocess.run(["pre-commit", "install"], cwd=ROOT, check=True)

    owner = subprocess.run(["git", "config", "--get", "krama.owner"], cwd=ROOT, capture_output=True, text=True)
    if owner.stdout.strip() not in ("vishwas", "nachiketha"):
        print("\nSet who you are (used by the ownership hook and AI agents):")
        print("  git config krama.owner vishwas      # or nachiketha")
        print('  "vishwas" | Out-File -Encoding ascii .krama-owner')
    else:
        print(f"owner: {owner.stdout.strip()}")

    print("\nNext: `just up` then `just seed`. Per-laptop agent setup: docs/setup/agent-guardrails.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
