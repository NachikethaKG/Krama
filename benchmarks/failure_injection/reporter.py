"""Console table rendering and JSON persistence for verifier failure-injection benchmark."""

from __future__ import annotations

import io
import sys
from datetime import UTC, datetime
from pathlib import Path

from benchmarks.failure_injection.models import AccuracyReport


class FailureInjectionReporter:
    """Renders formatted console tables and saves JSON reports for failure injection benchmarks."""

    def __init__(self, stream: io.TextIOBase | None = None) -> None:
        self.stream = stream or sys.stdout

    def render(self, report: AccuracyReport, saved_path: Path | None = None) -> None:
        """Render a formatted console table summarizing accuracy and false alarms."""
        out = self.stream

        sep = "=" * 80
        thin_sep = "-" * 80

        acc_pct = report.detection_accuracy * 100.0
        far_pct = report.false_alarm_rate * 100.0

        out.write(f"\n{sep}\n")
        out.write(f"{'VERIFIER FAILURE-INJECTION BENCHMARK REPORT':^80}\n")
        out.write(f"{sep}\n")
        out.write(f"Verifier Evaluated:          {report.verifier_name}\n")
        out.write(f"Timestamp:                   {report.timestamp}\n")
        out.write(f"Total Cases:                 {report.total_cases}\n")
        out.write(f"Injected Failures:           {report.injected_failures}\n")
        out.write(f"Clean Control Cases:         {report.clean_controls}\n")
        out.write(
            f"Detection Accuracy (Recall): {acc_pct:.1f}% "
            f"({report.true_positives}/{report.injected_failures} caught)\n"
        )
        out.write(
            f"False Alarm Rate (FP Rate):  {far_pct:.1f}% "
            f"({report.false_positives}/{report.clean_controls} false alarms)\n"
        )
        if report.errors > 0:
            out.write(f"System / Execution Errors:   {report.errors}\n")

        out.write(f"\n{thin_sep}\n")
        out.write("PER-FAILURE-TYPE BREAKDOWN:\n")
        out.write(
            f"{'Failure Type':<20} {'Total':<6} {'Injected (TP/FN)':<18} "
            f"{'Control (TN/FP)':<17} {'Recall':<8} {'False Alarm'}\n"
        )
        out.write(f"{thin_sep}\n")

        for ft, metrics in report.by_type.items():
            inj_str = f"{metrics.injected_failures} ({metrics.true_positives}/{metrics.false_negatives})"
            ctrl_str = f"{metrics.clean_controls} ({metrics.true_negatives}/{metrics.false_positives})"
            rec_str = f"{metrics.recall * 100.0:.1f}%"
            far_str = f"{metrics.false_alarm_rate * 100.0:.1f}%"
            out.write(
                f"{ft:<20} {metrics.total_cases:<6} {inj_str:<18} "
                f"{ctrl_str:<17} {rec_str:<8} {far_str}\n"
            )

        out.write(f"\n{thin_sep}\n")
        out.write("CASE EVALUATION DETAILS:\n")

        status_labels = {
            "TP": "[CAUGHT]",
            "FN": "[MISSED]",
            "TN": "[PASS]",
            "FP": "[FALSE ALARM]",
            "ERROR": "[ERROR]",
        }

        for case_res in report.cases:
            tag = status_labels.get(
                case_res.classification, f"[{case_res.classification}]"
            )
            err = f" -> {case_res.error_message}" if case_res.error_message else ""
            checks = (
                f" ({', '.join(case_res.failed_checks)})"
                if case_res.failed_checks
                else ""
            )
            out.write(
                f"  {tag:<14} {case_res.case_name} [{case_res.failure_type}]{checks}{err}\n"
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
