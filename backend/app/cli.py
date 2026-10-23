"""The `krama` command line. `uv run krama --help` (from backend/).

    uv run krama run "Create a repository called demo-repo with a README" --target http://localhost:3001 \\
        --site gitea --login --yes
    uv run krama session key              # a new KRAMA_STORAGE_KEY for .env
    uv run krama session capture github   # log in once by hand; stored encrypted (#87)
    uv run krama session check github     # still signed in?
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence

from app.agent.gitea_create_repo import login_steps
from app.agent.stored_session import (
    SITES,
    SessionVault,
    SessionVaultError,
    capture,
    new_key,
    probe,
    sign_in_problem,
)
from app.config import get_settings
from app.llm import create_provider
from app.observer import PageObserver
from app.planner import LLMPlanner
from app.runs import RunOptions, RunParts, RunReport, run_task
from app.runs.approval import console_approver
from app.verifier import LayeredVerifier
from app.verifier.vision import GeminiVisionJudge


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

    session = commands.add_parser(
        "session",
        help="signed-in browser sessions for real sites (log in once, stored encrypted)",
        description="Manage the stored, encrypted browser sessions Krama uses on real sites (#87).",
    )
    session.add_argument("action", choices=["key", "capture", "check", "forget"])
    session.add_argument("site", nargs="?", choices=sorted(SITES), help="e.g. github")
    session.add_argument("--timeout", type=float, default=600.0, help="seconds to wait for the sign-in")
    return parser


def session_command(args: argparse.Namespace) -> int:
    """`krama session ...`. Never prints a cookie or the key's stored contents, only what to do next."""
    if args.action == "key":
        print(f"KRAMA_STORAGE_KEY={new_key()}")
        print("Put this line in the repo-root .env (never commit it). A new key can't read old sessions.")
        return 0
    if args.site is None:
        print("Name the site, e.g. `krama session capture github`.")
        return 2
    settings = get_settings()
    login, base_url = SITES[args.site], settings.github_url
    try:
        vault = SessionVault(settings.sessions_dir, settings.krama_storage_key.get_secret_value())
        if args.action == "forget":
            print("Stored session deleted." if vault.delete(login.site) else "No stored session.")
            return 0
        if args.action == "capture":
            print(f"A browser opens at {base_url}{login.login_path}. Sign in there (password and 2FA).")
            print("Krama waits for the signed-in page and never reads what you type.")
            expires = asyncio.run(capture(login, base_url, vault, timeout_s=args.timeout))
            print(
                f"Signed in. The session is stored encrypted and expires {expires:%Y-%m-%d}."
                if expires
                else "Stored."
            )
            return 0
        state = vault.load(login.site)
    except SessionVaultError as e:
        print(f"{e}.")
        return 1
    except TimeoutError:
        print("Nobody signed in before the timeout; nothing was stored.")
        return 1
    problem = sign_in_problem(state, login)
    if problem is None and state is not None and not asyncio.run(probe(login, base_url, state)):
        problem = f"{base_url} no longer accepts the stored session. Log in again."
    print(problem or f"The stored {login.site} session is signed in.")
    return 1 if problem else 0


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
    llm = create_provider(settings)
    vision = GeminiVisionJudge(llm) if settings.llm_provider == "gemini" else None
    parts = RunParts(
        planner=LLMPlanner(llm),
        verifier=LayeredVerifier(vision),
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
    if args.command == "session":
        return session_command(args)
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
