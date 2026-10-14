"""Command-line entrypoint for running the verifier failure-injection benchmark.

Usage:
    python -m benchmarks.failure_injection.runner
    python -m benchmarks.failure_injection.runner --verifier rule
    python -m benchmarks.failure_injection.runner --filter-type wrong_page
    python -m benchmarks.failure_injection.runner --no-save
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from app.verifier.layered import LayeredVerifier  # type: ignore[import-untyped]
from app.verifier.verifier import RuleVerifier  # type: ignore[import-untyped]

from benchmarks.failure_injection.cases import ALL_CASES
from benchmarks.failure_injection.evaluator import FailureInjectionEvaluator
from benchmarks.failure_injection.models import FailureCase, FailureType
from benchmarks.failure_injection.reporter import FailureInjectionReporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmarks.failure_injection.runner",
        description="Run failure-injection benchmarks to evaluate verifier accuracy and false alarm rates.",
    )
    parser.add_argument(
        "--verifier",
        choices=["layered", "rule"],
        default="layered",
        help="Verifier implementation to evaluate (default: layered)",
    )
    parser.add_argument(
        "--filter-type",
        choices=[
            "wrong_page",
            "missing_element",
            "unexpected_dialog",
            "wrong_form_value",
        ],
        default=None,
        help="Optional failure mode to isolate and test",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Directory to save benchmark JSON reports (default: benchmarks/results)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip persisting report JSON to disk",
    )
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=None,
        help="Minimum required detection accuracy threshold (0.0 to 1.0) to pass",
    )
    parser.add_argument(
        "--max-false-alarm",
        type=float,
        default=None,
        help="Maximum allowed false alarm rate threshold (0.0 to 1.0) to pass",
    )
    return parser


def select_cases(filter_type: FailureType | None = None) -> list[FailureCase]:
    if filter_type:
        return [c for c in ALL_CASES if c.failure_type == filter_type]
    return list(ALL_CASES)


def run_benchmark(
    argv: Sequence[str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    verifier = LayeredVerifier() if args.verifier == "layered" else RuleVerifier()
    evaluator = FailureInjectionEvaluator(verifier=verifier)
    cases = select_cases(args.filter_type)

    if not cases:
        print(f"No cases found matching filter: {args.filter_type}", file=sys.stderr)
        return 1

    report = evaluator.run(cases)
    reporter = FailureInjectionReporter()

    saved_path = None
    if not args.no_save:
        saved_path = reporter.save_report(report, results_dir=args.results_dir)

    reporter.render(report, saved_path=saved_path)

    if args.min_accuracy is not None and report.detection_accuracy < args.min_accuracy:
        print(
            f"FAILED: Detection accuracy {report.detection_accuracy * 100.0:.1f}% "
            f"fell below required threshold {args.min_accuracy * 100.0:.1f}%.",
            file=sys.stderr,
        )
        return 1

    if (
        args.max_false_alarm is not None
        and report.false_alarm_rate > args.max_false_alarm
    ):
        print(
            f"FAILED: False alarm rate {report.false_alarm_rate * 100.0:.1f}% "
            f"exceeded maximum allowed threshold {args.max_false_alarm * 100.0:.1f}%.",
            file=sys.stderr,
        )
        return 1

    return 0


def main() -> None:
    sys.exit(run_benchmark())


if __name__ == "__main__":
    main()
