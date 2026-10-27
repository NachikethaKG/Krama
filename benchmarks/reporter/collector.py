"""Metrics collector and aggregator for benchmark run logs and results."""

from __future__ import annotations

import json
import logging
import math
import statistics
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmarks.reporter.models import BenchmarkReportData, TaskMetrics

logger = logging.getLogger(__name__)


def compute_p90(latencies: Sequence[float]) -> float:
    """Compute the 90th percentile (P90) latency using linear interpolation."""
    if not latencies:
        return 0.0
    if len(latencies) == 1:
        return float(latencies[0])
    sorted_vals = sorted(latencies)
    k = (len(sorted_vals) - 1) * 0.9
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f))


def compute_median(latencies: Sequence[float]) -> float:
    """Compute median (P50) latency, returning 0.0 if empty."""
    if not latencies:
        return 0.0
    return float(statistics.median(latencies))


class BenchmarkMetricsCollector:
    """Scans and aggregates benchmark run result JSONs into structured report data."""

    def __init__(self, results_dir: Path | str = "benchmarks/results") -> None:
        self.results_dir = Path(results_dir)

    def scan_json_files(self) -> list[Path]:
        """Find all relevant benchmark JSON results, ignoring report artifacts."""
        if not self.results_dir.exists() or not self.results_dir.is_dir():
            return []
        files = []
        for p in sorted(self.results_dir.glob("*.json")):
            # Skip generated reports or temporary output files
            if p.name in ("report.json", "summary.json"):
                continue
            files.append(p)
        return files

    def collect(self) -> BenchmarkReportData:
        """Scan results directory and produce aggregated BenchmarkReportData."""
        now_iso = datetime.now(UTC).isoformat()
        if not self.results_dir.exists():
            logger.warning("Results directory does not exist: %s", self.results_dir)
            return BenchmarkReportData(
                generated_at=now_iso,
                total_tasks=0,
                overall_success_rate=0.0,
                overall_verifier_accuracy=0.0,
                tasks=[],
            )

        json_files = self.scan_json_files()
        if not json_files:
            logger.warning("No benchmark JSON files found in: %s", self.results_dir)
            return BenchmarkReportData(
                generated_at=now_iso,
                total_tasks=0,
                overall_success_rate=0.0,
                overall_verifier_accuracy=0.0,
                tasks=[],
            )

        task_groups: dict[str, list[dict[str, Any]]] = {}
        standalone_accuracy: dict[str, Any] = {}
        all_trials_latencies: list[float] = []

        for file_path in json_files:
            try:
                raw_text = file_path.read_text(encoding="utf-8")
                data = json.loads(raw_text)
            except (
                json.JSONDecodeError,
                OSError,
                UnicodeDecodeError,
                ValueError,
            ) as exc:
                logger.warning(
                    "Skipping malformed or unreadable JSON file %s: %s", file_path, exc
                )
                continue

            if not isinstance(data, dict):
                logger.warning("Skipping non-dict JSON file %s", file_path)
                continue

            # Check if this is a standalone failure-injection / verifier accuracy report
            if "verifier_name" in data and (
                "detection_accuracy" in data or "false_alarm_rate" in data
            ):
                standalone_accuracy = data
                continue

            # Check if file has multiple tasks under "tasks"
            if "tasks" in data and isinstance(data["tasks"], list):
                for subtask in data["tasks"]:
                    if isinstance(subtask, dict) and "task_name" in subtask:
                        task_name = str(subtask["task_name"])
                        task_groups.setdefault(task_name, []).append(subtask)
                continue

            # Check standard single task benchmark file
            raw_task = data.get("task_name") or data.get("task")
            if raw_task:
                task_groups.setdefault(str(raw_task), []).append(data)
            else:
                logger.debug(
                    "JSON file %s did not contain task_name; skipping.", file_path
                )

        if not task_groups:
            logger.warning(
                "No valid task data extracted from JSON files in: %s", self.results_dir
            )
            return BenchmarkReportData(
                generated_at=now_iso,
                total_tasks=0,
                overall_success_rate=0.0,
                overall_verifier_accuracy=0.0,
                tasks=[],
            )

        tasks_metrics: list[TaskMetrics] = []

        for task_name, records in sorted(task_groups.items()):
            task_metrics = self._aggregate_task(task_name, records, standalone_accuracy)
            tasks_metrics.append(task_metrics)
            # Collect latencies for overall P90 / median calculation
            for rec in records:
                for t in rec.get("trials", []):
                    if isinstance(t, dict):
                        dur = self._extract_duration_ms(t)
                        if dur is not None:
                            all_trials_latencies.append(dur)

        total_runs_all = sum(t.total_runs for t in tasks_metrics)
        successful_runs_all = sum(t.successful_runs for t in tasks_metrics)
        failed_runs_all = sum(t.failed_runs for t in tasks_metrics)
        overall_success_rate = (
            (successful_runs_all / total_runs_all) if total_runs_all > 0 else 0.0
        )

        # Compute overall weighted verifier accuracy and false alarm rate
        if total_runs_all > 0:
            overall_verifier_acc = (
                sum(t.verifier_accuracy * t.total_runs for t in tasks_metrics)
                / total_runs_all
            )
            overall_false_alarm = (
                sum(t.false_alarm_rate * t.total_runs for t in tasks_metrics)
                / total_runs_all
            )
        else:
            overall_verifier_acc = (
                sum(t.verifier_accuracy for t in tasks_metrics) / len(tasks_metrics)
                if tasks_metrics
                else 0.0
            )
            overall_false_alarm = (
                sum(t.false_alarm_rate for t in tasks_metrics) / len(tasks_metrics)
                if tasks_metrics
                else 0.0
            )

        total_runtime_all_ms = sum(t.total_runtime_ms for t in tasks_metrics)
        overall_avg_lat = (
            (total_runtime_all_ms / total_runs_all) if total_runs_all > 0 else 0.0
        )
        overall_median_lat = (
            compute_median(all_trials_latencies)
            if all_trials_latencies
            else overall_avg_lat
        )
        overall_p90_lat = (
            compute_p90(all_trials_latencies)
            if all_trials_latencies
            else overall_avg_lat
        )

        total_replan_attempts = sum(t.replan_attempts for t in tasks_metrics)
        total_replan_successes = sum(t.replan_successes for t in tasks_metrics)
        overall_recovery_rate = (
            round((total_replan_successes / total_replan_attempts) * 100.0, 2)
            if total_replan_attempts > 0
            else 0.0
        )
        overall_planning_lat = (
            round(
                sum(t.avg_planning_latency_ms * t.total_runs for t in tasks_metrics)
                / total_runs_all,
                2,
            )
            if total_runs_all > 0
            else 0.0
        )

        return BenchmarkReportData(
            generated_at=now_iso,
            total_tasks=len(tasks_metrics),
            overall_success_rate=round(overall_success_rate, 4),
            overall_verifier_accuracy=round(overall_verifier_acc, 4),
            tasks=tasks_metrics,
            overall_total_runs=total_runs_all,
            overall_successful_runs=successful_runs_all,
            overall_failed_runs=failed_runs_all,
            overall_false_alarm_rate=round(overall_false_alarm, 4),
            overall_recovery_rate=overall_recovery_rate,
            overall_replan_attempts=total_replan_attempts,
            overall_replan_successes=total_replan_successes,
            overall_avg_planning_latency_ms=overall_planning_lat,
            overall_avg_latency_ms=round(overall_avg_lat, 2),
            overall_median_latency_ms=round(overall_median_lat, 2),
            overall_p50_latency_ms=round(overall_median_lat, 2),
            overall_p90_latency_ms=round(overall_p90_lat, 2),
            overall_total_runtime_ms=round(total_runtime_all_ms, 2),
        )

    def _aggregate_task(
        self,
        task_name: str,
        records: list[dict[str, Any]],
        standalone_accuracy: dict[str, Any],
    ) -> TaskMetrics:
        """Aggregate multiple run records/batches for a single task."""
        total_runs = 0
        successful_runs = 0
        latencies_ms: list[float] = []
        planning_latencies_ms: list[float] = []
        replan_attempts = 0
        replan_successes = 0
        explicit_verifier_acc: float | None = None
        explicit_false_alarm: float | None = None
        tp_detections = 0
        false_alarms = 0
        graded_trials = 0
        graded_agreements = 0
        graded_successes = 0

        # Platform detection
        platform = "github" if "github" in task_name.lower() else "gitea"

        for rec in records:
            if rec.get("platform"):
                platform = str(rec["platform"]).lower()

            if "replan_attempts" in rec:
                replan_attempts += int(rec["replan_attempts"])
            if "replan_successes" in rec:
                replan_successes += int(rec["replan_successes"])
            if "avg_planning_latency_ms" in rec:
                planning_latencies_ms.append(float(rec["avg_planning_latency_ms"]))

            # Check explicit rates if provided directly on the record
            if "verifier_accuracy" in rec:
                val = float(rec["verifier_accuracy"])
                explicit_verifier_acc = (val / 100.0) if val > 1.0 else val
            elif "accuracy" in rec:
                val = float(rec["accuracy"])
                explicit_verifier_acc = (val / 100.0) if val > 1.0 else val

            if "false_alarm_rate" in rec:
                val = float(rec["false_alarm_rate"])
                explicit_false_alarm = (val / 100.0) if val > 1.0 else val

            if "true_positive_detections" in rec:
                tp_detections += int(rec["true_positive_detections"])
            if "false_alarms_count" in rec:
                false_alarms += int(rec["false_alarms_count"])

            trials = rec.get("trials", [])
            if trials and isinstance(trials, list):
                total_runs += len(trials)
                for t in trials:
                    if not isinstance(t, dict):
                        continue
                    if t.get("success") is True:
                        successful_runs += 1
                    # The verifier is right when what the agent reported matches the task's independent
                    # success_check (`success`). Trials without `agent_verified` were never graded.
                    if t.get("agent_verified") is not None:
                        graded_trials += 1
                        agreed = bool(t["agent_verified"]) == bool(t.get("success"))
                        graded_agreements += agreed
                        if t.get("success") is True:
                            graded_successes += 1
                            false_alarms += not t["agent_verified"]
                        elif not t["agent_verified"]:
                            tp_detections += 1

                    # Only replans the trial recorded; a retry is not a replan.
                    r_attempts = int(t.get("replan_attempts") or t.get("replans_count") or t.get("replans") or 0)
                    replan_attempts += r_attempts
                    if "replan_successes" in t:
                        replan_successes += int(t["replan_successes"])
                    elif r_attempts > 0 and t.get("success") is True:
                        replan_successes += r_attempts

                    dur_ms = self._extract_duration_ms(t)
                    if dur_ms is not None:
                        latencies_ms.append(dur_ms)

                    plan_ms = self._extract_planning_ms(t)
                    if plan_ms is not None:
                        planning_latencies_ms.append(plan_ms)
            else:
                # Fallback to top-level run counts if trials list not provided
                runs = int(rec.get("total_runs", 1))
                succ = int(
                    rec.get("successful_runs", runs if rec.get("success", False) else 0)
                )
                total_runs += runs
                successful_runs += succ

                top_dur = self._extract_duration_ms(rec)
                if top_dur is not None:
                    latencies_ms.append(top_dur)
                elif "avg_latency_ms" in rec:
                    latencies_ms.append(float(rec["avg_latency_ms"]))
                elif "average_duration_seconds" in rec:
                    latencies_ms.append(float(rec["average_duration_seconds"]) * 1000.0)

                top_plan = self._extract_planning_ms(rec)
                if top_plan is not None:
                    planning_latencies_ms.append(top_plan)

        # Success rate
        success_rate = (successful_runs / total_runs) if total_runs > 0 else 0.0

        # Latency calculations
        if latencies_ms:
            avg_lat = sum(latencies_ms) / len(latencies_ms)
            med_lat = compute_median(latencies_ms)
            p90_lat = compute_p90(latencies_ms)
            total_time_ms = sum(latencies_ms)
        else:
            first_rec = records[0]
            avg_lat = float(
                first_rec.get(
                    "avg_latency_ms",
                    float(first_rec.get("average_duration_seconds", 0.0)) * 1000.0,
                )
            )
            p90_lat = float(first_rec.get("p90_latency_ms", avg_lat))
            med_lat = float(first_rec.get("median_latency_ms", avg_lat))
            total_time_ms = avg_lat * total_runs

        # Planning latency calculation
        # Not measured means 0: never an estimate (#104 found invented values here).
        avg_planning_lat = (
            sum(planning_latencies_ms) / len(planning_latencies_ms) if planning_latencies_ms else 0.0
        )
        recovery_rate = round((replan_successes / replan_attempts) * 100.0, 2) if replan_attempts else 0.0

        # Verifier accuracy & false alarms: measured on graded trials first, else a measured value given in
        # the files; if nothing measured them, 0 (and a warning), never a guess.
        if graded_trials:
            verif_acc = graded_agreements / graded_trials
        elif explicit_verifier_acc is not None:
            verif_acc = explicit_verifier_acc
        elif standalone_accuracy:
            acc = float(standalone_accuracy.get("detection_accuracy", 0.0))
            verif_acc = (acc / 100.0) if acc > 1.0 else acc
        else:
            logger.warning("%s: no graded trials, verifier accuracy not measured", task_name)
            verif_acc = 0.0

        if graded_trials:
            fa_rate = false_alarms / graded_successes if graded_successes else 0.0
        elif explicit_false_alarm is not None:
            fa_rate = explicit_false_alarm
        elif standalone_accuracy:
            fa = float(standalone_accuracy.get("false_alarm_rate", 0.0))
            fa_rate = (fa / 100.0) if fa > 1.0 else fa
        else:
            fa_rate = 0.0

        return TaskMetrics(
            task_name=task_name,
            platform=platform,
            total_runs=total_runs,
            successful_runs=successful_runs,
            failed_runs=max(0, total_runs - successful_runs),
            success_rate=round(success_rate, 4),
            verifier_accuracy=round(verif_acc, 4),
            false_alarm_rate=round(fa_rate, 4),
            replan_attempts=replan_attempts,
            replan_successes=replan_successes,
            recovery_rate=recovery_rate,
            avg_planning_latency_ms=round(avg_planning_lat, 2),
            avg_latency_ms=round(avg_lat, 2),
            median_latency_ms=round(med_lat, 2),
            p50_latency_ms=round(med_lat, 2),
            p90_latency_ms=round(p90_lat, 2),
            total_runtime_ms=round(total_time_ms, 2),
            true_positive_detections=tp_detections,
            false_alarms_count=false_alarms,
        )

    def _extract_duration_ms(self, item: dict[str, Any]) -> float | None:
        """Extract duration in milliseconds from a trial or task dictionary."""
        if "duration_seconds" in item and item["duration_seconds"] is not None:
            return float(item["duration_seconds"]) * 1000.0
        if "duration_ms" in item and item["duration_ms"] is not None:
            return float(item["duration_ms"])
        if "latency_ms" in item and item["latency_ms"] is not None:
            return float(item["latency_ms"])
        if "duration" in item and item["duration"] is not None:
            val = float(item["duration"])
            return val if val > 100.0 else val * 1000.0
        return None

    def _extract_planning_ms(self, item: dict[str, Any]) -> float | None:
        """Extract planning latency in milliseconds from a trial or task dictionary."""
        if (
            "planning_duration_ms" in item
            and item["planning_duration_ms"] is not None
        ):
            return float(item["planning_duration_ms"])
        if (
            "planning_duration_seconds" in item
            and item["planning_duration_seconds"] is not None
        ):
            return float(item["planning_duration_seconds"]) * 1000.0
        if (
            "planning_latency_ms" in item
            and item["planning_latency_ms"] is not None
        ):
            return float(item["planning_latency_ms"])
        if "planning_seconds" in item and item["planning_seconds"] is not None:
            return float(item["planning_seconds"]) * 1000.0
        return None


def collect_benchmark_metrics(
    results_dir: Path | str = "benchmarks/results",
) -> BenchmarkReportData:
    """Helper entrypoint to scan a directory and return aggregated BenchmarkReportData."""
    collector = BenchmarkMetricsCollector(results_dir=results_dir)
    return collector.collect()
