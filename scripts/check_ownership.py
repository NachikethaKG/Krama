"""Reject changes to files outside the committer's ownership area.

Usage:
  python scripts/check_ownership.py              # pre-commit: checks staged files
  python scripts/check_ownership.py --base REF   # CI: checks files changed since REF (report only)

Who you are comes from `git config krama.owner` (vishwas | nachiketha).
Bypass for an agreed cross-boundary change: set KRAMA_CROSS_EDIT=1 and label the PR `cross-boundary`.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def load_rules() -> list[tuple[list[str], str]]:
    data = tomllib.loads((ROOT / "OWNERSHIP.toml").read_text(encoding="utf-8"))
    return [(r["paths"], r["area"]) for r in data["rule"]]


def area_of(path: str, rules: list[tuple[list[str], str]]) -> str:
    for patterns, area in rules:
        if any(fnmatch.fnmatch(path, p) for p in patterns):
            return area
    return "shared"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="CI mode: diff against this ref and only report areas touched")
    args = parser.parse_args()

    rules = load_rules()

    if args.base:
        files = git("diff", "--name-only", f"{args.base}...HEAD").split()
        areas: dict[str, list[str]] = {}
        for f in files:
            areas.setdefault(area_of(f, rules), []).append(f)
        for area, fs in sorted(areas.items()):
            print(f"[{area}] {len(fs)} file(s)")
            for f in fs:
                print(f"    {f}")
        if "vishwas" in areas and "nachiketha" in areas:
            print("::warning::PR touches BOTH backend and frontend areas -> label it `cross-boundary`.")
        if "contract" in areas:
            print("::notice::PR changes contracts/ -> needs `contract-change` label and approval from both.")
        return 0

    owner = git("config", "--get", "krama.owner").strip() if _has_owner() else ""
    if owner not in ("vishwas", "nachiketha"):
        print("check-ownership: set your identity first:  git config krama.owner vishwas|nachiketha")
        return 1

    other = "nachiketha" if owner == "vishwas" else "vishwas"
    staged = git("diff", "--cached", "--name-only", "--diff-filter=ACMRD").split()
    cross = os.environ.get("KRAMA_CROSS_EDIT") == "1"

    errors: list[str] = []
    for f in staged:
        area = area_of(f, rules)
        if area == other and not cross:
            errors.append(f"  {f}  (owned by {other})")
        elif area == "generated" and os.environ.get("KRAMA_GEN") != "1":
            errors.append(f"  {f}  (generated - run scripts/gen-contracts, which sets KRAMA_GEN=1)")

    if errors:
        print("check-ownership: these staged files are outside your area:")
        print("\n".join(errors))
        print("Unstage them, or for an agreed cross-boundary change re-run with KRAMA_CROSS_EDIT=1"
              " and label the PR `cross-boundary`.")
        return 1
    return 0


def _has_owner() -> bool:
    return subprocess.run(["git", "config", "--get", "krama.owner"], cwd=ROOT, capture_output=True).returncode == 0


if __name__ == "__main__":
    sys.exit(main())
