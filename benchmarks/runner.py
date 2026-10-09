"""Command-line entrypoint for running benchmark suites.

Usage:
    python -m benchmarks.runner --task "Create a repository called demo-repo with a README" --runs 5
    python -m benchmarks.runner "Create a repository called demo-repo with a README" 3
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from benchmarks.agent_runner import AgentRunner
from benchmarks.gitea import reset_gitea
from benchmarks.orchestrator import BenchmarkOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmarks.runner",
        description="Run repeatable benchmark trials for Krama web agents.",
    )
    parser.add_argument(
        "pos_task", nargs="?", default=None, help="Task description or identifier"
    )
    parser.add_argument(
        "pos_runs", nargs="?", default=None, help="Number of benchmark trials"
    )
    parser.add_argument(
        "--task", dest="flag_task", help="Task description or identifier"
    )
    parser.add_argument(
        "--runs", dest="flag_runs", type=int, help="Number of benchmark trials"
    )
    parser.add_argument(
        "--target",
        default="http://localhost:3001",
        help="Target site URL (default: http://localhost:3001)",
    )
    parser.add_argument(
        "--site",
        default="gitea",
        choices=["gitea"],
        help="Site-specific hint configuration (default: gitea)",
    )
    parser.add_argument(
        "--no-login",
        action="store_true",
        help="Do not pre-login as demo user",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Skip Gitea environment reset before runs",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Maximum duration per trial in seconds (default: 300.0)",
    )
    parser.add_argument(
        "--reset-timeout",
        type=float,
        default=10.0,
        help="Maximum duration for Gitea reset in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Directory to save benchmark JSON reports",
    )
    return parser


def parse_args(
    argv: Sequence[str] | None = None,
) -> tuple[str, int, argparse.Namespace]:
    parser = build_parser()
    args = parser.parse_args(argv)

    task = args.flag_task or args.pos_task
    if not task:
        parser.error("A task must be specified (via --task or positional argument)")

    runs = 1
    if args.flag_runs is not None:
        runs = args.flag_runs
    elif args.pos_runs is not None:
        val = args.pos_runs.removeprefix("--runs=").removeprefix("--runs")
        try:
            runs = int(val)
        except ValueError:
            parser.error(f"Invalid runs count: {args.pos_runs}")

    if runs < 1:
        parser.error(f"--runs must be >= 1, got {runs}")

    return task, runs, args


def main(argv: Sequence[str] | None = None) -> int:
    task, runs, args = parse_args(argv)

    runner = AgentRunner(
        target_url=args.target,
        site=args.site,
        login=not args.no_login,
        auto_approve=True,
        timeout=args.timeout,
    )

    def do_reset() -> None:
        reset_gitea(base_url=args.target, timeout=args.reset_timeout)

    orchestrator = BenchmarkOrchestrator(
        task=task,
        runs=runs,
        runner=runner,
        reset_fn=do_reset,
        results_dir=args.results_dir,
        skip_reset=args.no_reset,
    )

    report, _path = orchestrator.run()
    # Exit with 0 if all runs succeeded, 1 if any trial failed
    return 0 if report.successful_runs == report.total_runs else 1


if __name__ == "__main__":
    sys.exit(main())
