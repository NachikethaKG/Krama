"""Console summary table reporter for benchmark reports."""

from __future__ import annotations

import io
import sys
from pathlib import Path

from benchmarks.models import BenchmarkReport


class ConsoleReporter:
    """Renders formatted benchmark summaries and trial breakdowns to the terminal."""

    def __init__(self, stream: io.TextIOBase | None = None) -> None:
        self.stream = stream or sys.stdout

    def render(self, report: BenchmarkReport, saved_path: Path | None = None) -> None:
        """Render a clean summary table for the benchmark report."""
        out = self.stream

        sep = "=" * 80
        thin_sep = "-" * 80

        success_pct = report.success_rate * 100.0
        wall_time_str = f"{report.total_duration_seconds:.2f}s"
        avg_time_str = f"{report.average_duration_seconds:.2f}s"

        step_dist = f"min: {report.min_steps} | max: {report.max_steps} | mean: {report.average_steps:.1f}"

        out.write(f"\n{sep}\n")
        out.write(f"{'BENCHMARK SUMMARY REPORT':^80}\n")
        out.write(f"{sep}\n")
        out.write(f"Task:                    {report.task_name}\n")
        out.write(f"Total Runs:              {report.total_runs}\n")
        out.write(f"Successful Runs:         {report.successful_runs}\n")
        out.write(
            f"Success Rate:            {success_pct:.1f}% ({report.successful_runs}/{report.total_runs})\n"
        )
        out.write(
            f"Wall-Clock Duration:     {wall_time_str} (avg: {avg_time_str}/run)\n"
        )
        out.write(f"Step Distribution:       {step_dist}\n")
        out.write(f"Total Retries:           {report.total_retries}\n")
        out.write(
            f"LLM API Requests:        {report.total_llm_calls} calls "
            f"(in: {report.total_tokens_in} tokens | out: {report.total_tokens_out} tokens)\n"
        )
        out.write(f"{thin_sep}\n")
        out.write("Trial Breakdown:\n")

        for trial in report.trials:
            status = "PASSED" if trial.success else "FAILED"
            details = (
                f"{trial.steps_taken} steps, {trial.retries_count} retries, "
                f"{trial.duration_seconds:.2f}s, {trial.llm_call_count} LLM calls"
            )
            err_suffix = (
                f" -> Error: {trial.error_message}" if trial.error_message else ""
            )
            out.write(
                f"  Run #{trial.run_index:<3} [{status:^6}]  {details}{err_suffix}\n"
            )

        out.write(f"{sep}\n")
        if saved_path:
            out.write(f"Report saved to: {saved_path}\n")
        out.write("\n")
        out.flush()
