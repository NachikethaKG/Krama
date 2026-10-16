"""Console table rendering and JSON persistence for verifier failure-injection benchmark."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from benchmarks.failure_injection.models import AccuracyReport, OutcomeCounts

STATUS_LABELS = {
    "TP": "[CAUGHT]",
    "TP_PAUSED": "[PAUSED]",
    "FN": "[MISSED]",
    "TN": "[PASS]",
    "FP": "[FALSE ALARM]",
    "FP_PAUSED": "[NEEDLESS PAUSE]",
}


def _vfse(c: OutcomeCounts) -> str:
    return f"{c.verified}/{c.failed}/{c.skipped}/{c.error}"


def _pct(rate: float) -> str:
    return f"{rate * 100.0:.1f}%"


class FailureInjectionReporter:
    """Renders formatted console tables and saves JSON reports for failure injection benchmarks."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stdout

    def render(self, report: AccuracyReport, saved_path: Path | None = None) -> None:
        """Render a formatted console table summarizing accuracy and false alarms."""
        out = self.stream
        width = 96
        sep = "=" * width
        thin_sep = "-" * width
        inj, ctrl = report.injected_failures, report.clean_controls

        out.write(f"\n{sep}\n")
        out.write(f"{'VERIFIER FAILURE-INJECTION BENCHMARK REPORT':^{width}}\n")
        out.write(f"{sep}\n")
        out.write(f"Verifier Evaluated:          {report.verifier_name}\n")
        out.write(f"Timestamp:                   {report.timestamp}\n")
        out.write(f"Total Cases:                 {report.total_cases}\n")
        out.write(f"Injected Failures:           {inj}\n")
        out.write(f"Clean Control Cases:         {ctrl}\n")
        out.write(
            f"Silently Passed (must be 0): {_pct(report.silently_passed_rate)} "
            f"({report.silently_passed}/{inj} injected came back verified)\n"
        )
        out.write(
            f"Detection Accuracy (Recall): {_pct(report.detection_accuracy)} "
            f"({report.true_positives} failed + {report.paused_failures} paused / {inj})\n"
        )
        out.write(
            f"Hard Detection (failed):     {_pct(report.hard_detection_rate)} "
            f"({report.true_positives}/{inj})\n"
        )
        out.write(
            f"False Alarm Rate (FP Rate):  {_pct(report.false_alarm_rate)} "
            f"({report.false_positives}/{ctrl} controls failed or crashed)\n"
        )
        out.write(
            f"Needless Pause Rate:         {_pct(report.needless_pause_rate)} "
            f"({report.needless_pauses}/{ctrl} controls skipped)\n"
        )
        out.write(f"System / Execution Errors:   {report.errors}\n")
        out.write(
            f"Outcome != expected_result:  {report.expected_mismatches}/{report.total_cases}\n"
        )

        out.write(f"\n{thin_sep}\n")
        out.write(
            "PER-FAILURE-TYPE BREAKDOWN:\n"
            "  v/f/s/e = verified/failed/skipped/error; "
            "Silent = injected verified; Hard = injected failed\n"
        )
        out.write(
            f"{'Failure Type':<18} {'Inj':>3} {'Injected v/f/s/e':>17} {'Silent':>7} "
            f"{'Hard':>7} {'Ctl':>4} {'Control v/f/s/e':>16} {'FalseAl':>8} {'Pause':>7}\n"
        )
        out.write(f"{thin_sep}\n")
        for ft, m in report.by_type.items():
            out.write(
                f"{ft:<18} {m.injected_failures:>3} {_vfse(m.injected_outcomes):>17} "
                f"{_pct(m.silently_passed_rate):>7} {_pct(m.hard_detection_rate):>7} "
                f"{m.clean_controls:>4} {_vfse(m.control_outcomes):>16} "
                f"{_pct(m.false_alarm_rate):>8} {_pct(m.needless_pause_rate):>7}\n"
            )

        out.write(f"\n{thin_sep}\n")
        out.write("CASE EVALUATION DETAILS:\n")
        for case_res in report.cases:
            tag = STATUS_LABELS.get(
                case_res.classification, f"[{case_res.classification}]"
            )
            mismatch = (
                f" !! expected {case_res.expected_result}, got {case_res.outcome_result}"
                if case_res.matches_expected is False
                else ""
            )
            err = f" -> {case_res.error_message}" if case_res.error_message else ""
            checks = (
                f" ({', '.join(case_res.failed_checks)})"
                if case_res.failed_checks
                else ""
            )
            out.write(
                f"  {tag:<17} {case_res.case_name} [{case_res.failure_type}]"
                f"{mismatch}{checks}{err}\n"
            )

        out.write(f"{sep}\n")
        if saved_path:
            out.write(f"Report saved to: {saved_path}\n")
        out.write("\n")
        out.flush()

    def save_report(
        self,
        report: AccuracyReport,
        results_dir: Path | None = None,
        timestamp: datetime | None = None,
    ) -> Path:
        """Save benchmark metrics to `benchmarks/results/verifier-accuracy-<timestamp>.json`."""
        ts = timestamp or datetime.now(UTC)
        target_dir = results_dir or (Path(__file__).resolve().parents[1] / "results")
        target_dir.mkdir(parents=True, exist_ok=True)

        formatted_ts = ts.strftime("%Y%m%d_%H%M%S")
        filename = f"verifier-accuracy-{formatted_ts}.json"
        output_path = target_dir / filename

        output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return output_path
