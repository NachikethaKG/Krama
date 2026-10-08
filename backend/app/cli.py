"""The `krama` command line. `uv run krama --help` (from backend/).

    uv run krama run "Create a repository called demo-repo with a README" --target http://localhost:3001 \\
        --site gitea --login --yes
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from app.agent.gitea_create_repo import login_steps
from app.config import get_settings
from app.llm import create_provider
from app.observer import PageObserver
from app.planner import LLMPlanner
from app.runs import RunOptions, RunParts, RunReport, run_task
from app.runs.approval import console_approver
from app.verifier import RuleVerifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="krama", description="Krama: verified UI tutorials.")
    commands = parser.add_subparsers(dest="command", metavar="<command>")

    run = commands.add_parser(
        "run",
        help="plan, approve, execute, observe and verify one task",
        description="Run one task end to end.",
    )
    run.add_argument("task", help='what to do, e.g. "Create a repository called demo-repo"')
    run.add_argument("--target", required=True, help="base URL of the site, e.g. http://localhost:3001")
    run.add_argument("--site", choices=["gitea"], help="use the hand-written hints for this site")
    run.add_argument(
        "--login", action="store_true", help="sign in as the demo user first (needs --site gitea)"
    )
    run.add_argument("--start-path", default="/", help="URL path to open first (default: /)")
    run.add_argument("--yes", action="store_true", help="approve low/medium-risk plans without asking")
    run.add_argument("--headed", action="store_true", help="show the browser (debugging only)")
    return parser


async def run_command(args: argparse.Namespace) -> RunReport:
    settings = get_settings()
    if settings.llm_provider == "fake":
        print("Note: LLM_PROVIDER=fake, so the plan comes from recorded replies, not Gemini.")
    preconditions = []
    signed_in_as = None
    if args.login:
        preconditions = login_steps(user=settings.gitea_demo_user, password=settings.gitea_demo_password)
        signed_in_as = settings.gitea_demo_user

    options = RunOptions(
        task=args.task,
        target_url=args.target.rstrip("/"),
        site=args.site,
        start_path=args.start_path,
        preconditions=preconditions,
        signed_in_as=signed_in_as,
        headless=not args.headed,
        on_event=print,
    )
    parts = RunParts(
        planner=LLMPlanner(create_provider(settings)),
        verifier=RuleVerifier(),
        # The composition root is the one place that picks the concrete Observer behind the port.
        observer_for=lambda run_dir: PageObserver(artifacts_dir=run_dir),
        approve=console_approver(auto_approve=args.yes),
    )
    return await run_task(options, parts, artifacts_dir=settings.artifacts_dir)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.login and args.site != "gitea":
        parser.error("--login needs --site gitea")

    report = asyncio.run(run_command(args))
    path = report.write(get_settings().artifacts_dir)
    calls = len(report.llm_attempts)
    print(f"\n{report.status.upper()}: {report.message}  ({report.duration_ms} ms, {calls} LLM request(s))")
    print(f"Run log: {path}")
    if report.recording is not None:
        print(f"Recording: {report.recording.path} ({report.recording.event_count} events)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
