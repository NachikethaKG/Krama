"""Benchmark reporting module for console, markdown, and HTML reliability reports."""

from __future__ import annotations

from benchmarks.reporter.collector import (
    BenchmarkMetricsCollector,
    collect_benchmark_metrics,
    compute_median,
    compute_p90,
)
from benchmarks.reporter.console import ConsoleReporter
from benchmarks.reporter.generators import (
    HtmlReportGenerator,
    MarkdownReportGenerator,
    generate_html_report,
    generate_markdown_report,
)
from benchmarks.reporter.models import BenchmarkReportData, TaskMetrics

__all__ = [
    "BenchmarkMetricsCollector",
    "BenchmarkReportData",
    "ConsoleReporter",
    "HtmlReportGenerator",
    "MarkdownReportGenerator",
    "TaskMetrics",
    "collect_benchmark_metrics",
    "compute_median",
    "compute_p90",
    "generate_html_report",
    "generate_markdown_report",
]
