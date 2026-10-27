"""Command-line interface for generating benchmark reliability and performance reports.

Usage:
    python -m benchmarks.report --input-dir benchmarks/results --output-dir benchmarks/results
    python -m benchmarks.report
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from benchmarks.reporter.collector import BenchmarkMetricsCollector
from benchmarks.reporter.generators import HtmlReportGenerator, MarkdownReportGenerator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmarks.report",
        description="Aggregate benchmark results and generate HTML/Markdown reliability reports.",
    )
    parser.add_argument(
        "--input-dir",
        "-i",
        type=Path,
        default=Path("benchmarks/results"),
        help="Directory containing benchmark result JSON files (default: benchmarks/results)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("benchmarks/results"),
        help="Directory to save generated report.html and report.md (default: benchmarks/results)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Optional path to save machine-readable aggregated JSON report",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console output",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    collector = BenchmarkMetricsCollector(results_dir=input_dir)
    data = collector.collect()

    md_generator = MarkdownReportGenerator()
    html_generator = HtmlReportGenerator()

    md_content = md_generator.generate(data)
    html_content = html_generator.generate(data)

    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "report.md"
    html_path = output_dir / "report.html"
    summary_path = output_dir / "summary.json"
    report_json_path = output_dir / "report.json"

    md_path.write_text(md_content, encoding="utf-8")
    html_path.write_text(html_content, encoding="utf-8")
    summary_path.write_text(json.dumps(data.to_contract_dict(), indent=2), encoding="utf-8")
    report_json_path.write_text(data.model_dump_json(indent=2), encoding="utf-8")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(data.model_dump_json(indent=2), encoding="utf-8")

    if not args.quiet:
        print(f"\nSuccessfully generated benchmark reports in {output_dir}:")
        print(f"  - Markdown: {md_path}")
        print(f"  - HTML:     {html_path}")
        print("\nSummary:")
        print(f"  Tasks:                 {data.total_tasks}")
        print(f"  Total Runs:            {data.overall_total_runs}")
        print(
            f"  Overall Success Rate:  {data.overall_success_rate * 100:.1f}% "
            f"({data.overall_successful_runs}/{data.overall_total_runs} passed)"
        )
        print(
            f"  Verifier Accuracy:     {data.overall_verifier_accuracy * 100:.1f}% "
            f"(false alarms: {data.overall_false_alarm_rate * 100:.1f}%)"
        )
        print(
            f"  Mean / P90 Latency:    {data.overall_avg_latency_s:.2f}s / {data.overall_p90_latency_s:.2f}s\n"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
