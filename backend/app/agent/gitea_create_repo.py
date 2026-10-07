"""Hand-written "create a repository" run on the local Gitea: the known-good baseline before any LLM (#29).

Follows docs/research/phase-f-together-gitea-create-repo-walkthrough.md. Logging in is a precondition, not a
task step. Usage, from backend/ with `just up` + `just seed` running:

    uv run python -m app.agent.gitea_create_repo                  # one run, repo name generated
    uv run python -m app.agent.gitea_create_repo --runs 10        # baseline: 10 runs, unique names
"""

import argparse
import asyncio
import os
import sys
import uuid

from app.agent.executor import ActionExecutor
from app.agent.runlog import RunLog, ScriptedStep, run_script
from app.agent.session import PlaywrightSession, SessionConfig
from app.config import REPO_ROOT, get_settings
from app.contracts_gen.common_schema import Action, Target


def create_repo_steps(repo: str, *, user: str, password: str) -> list[ScriptedStep]:
    login: list[ScriptedStep] = [
        ScriptedStep(action=Action(type="navigate", value="/user/login"), section="precondition"),
        ScriptedStep(
            action=Action(type="fill", value=user),
            target=Target(role="textbox", name="Username or Email Address"),
            section="precondition",
        ),
        ScriptedStep(
            action=Action(type="fill", value=password),
            target=Target(role="textbox", name="Password"),
            section="precondition",
            sensitive=True,
        ),
        ScriptedStep(
            action=Action(type="click"), target=Target(role="button", name="Sign In"), section="precondition"
        ),
        ScriptedStep(
            action=Action(type="wait"), target=Target(role="main", name="Dashboard"), section="precondition"
        ),
    ]
    task: list[ScriptedStep] = [
        ScriptedStep(action=Action(type="click"), target=Target(role="menu", name="Create…")),
        ScriptedStep(action=Action(type="click"), target=Target(role="menuitem", name="New Repository")),
        ScriptedStep(
            action=Action(type="fill", value=repo), target=Target(role="textbox", name="Repository Name")
        ),
        ScriptedStep(
            action=Action(type="click"), target=Target(role="checkbox", name="Initialize Repository")
        ),
        ScriptedStep(action=Action(type="click"), target=Target(role="button", name="Create Repository")),
        # The repo page's README heading: the run only counts once the new repo is really shown.
        ScriptedStep(action=Action(type="wait"), target=Target(role="heading", name=f"{repo}")),
    ]
    return login + task


async def run_once(base_url: str, repo: str, *, user: str, password: str, headless: bool = True) -> RunLog:
    async with PlaywrightSession(SessionConfig(base_url=base_url, headless=headless)) as session:
        steps = create_repo_steps(repo, user=user, password=password)
        log = await run_script(
            ActionExecutor(session.page), steps, task=f"create repository {repo}", base_url=base_url
        )
    expected_path = f"/{user}/{repo}"
    if log.ok and log.entries[-1].result.url_after != expected_path:
        # Every action succeeded but we're not on the new repo's page: count it as a failed run.
        log.ok = False
    return log


async def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default=os.environ.get("GITEA_URL", "http://localhost:3001"))
    parser.add_argument("--repo", help="repository name (default: baseline-<random>)")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--headed", action="store_true", help="show the browser (debugging only)")
    args = parser.parse_args(argv)

    user = os.environ.get("GITEA_DEMO_USER", "demo")
    password = os.environ.get("GITEA_DEMO_PASSWORD", "demo-local-only")
    artifacts = get_settings().artifacts_dir
    if not artifacts.is_absolute():
        # `.env` uses a path relative to the repo root (./data/artifacts), not to the current folder.
        artifacts = REPO_ROOT / artifacts
    passed = 0
    for i in range(1, args.runs + 1):
        repo = args.repo if args.repo and args.runs == 1 else f"baseline-{uuid.uuid4().hex[:8]}"
        log = await run_once(args.base_url, repo, user=user, password=password, headless=not args.headed)
        path = log.write(artifacts)
        passed += log.ok
        failed = log.failed_entry
        detail = (
            ""
            if log.ok
            else f"  failed at #{failed.seq} {failed.action.type}: {failed.result.error}"
            if failed
            else ""
        )
        print(
            f"run {i}/{args.runs}  {'OK  ' if log.ok else 'FAIL'}  {repo}  {log.duration_ms} ms",
            f" {path}{detail}",
        )
    print(f"{passed}/{args.runs} runs succeeded")
    return 0 if passed == args.runs else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
