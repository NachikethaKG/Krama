"""Markdown and HTML report generators for benchmark reliability and performance."""

from __future__ import annotations

import html

from benchmarks.reporter.models import BenchmarkReportData


def _format_pct(ratio: float) -> str:
    """Format ratio (0.0 to 1.0) as percentage string."""
    pct = ratio * 100.0
    if pct == 100.0 or pct == 0.0:
        return f"{int(pct)}%"
    return f"{pct:.1f}%"


def _format_seconds(ms: float) -> str:
    """Format milliseconds as seconds with 's' suffix."""
    sec = ms / 1000.0
    if sec < 0.1 and sec > 0.0:
        return f"{sec:.2f}s"
    return f"{sec:.1f}s"


class MarkdownReportGenerator:
    """Generates clean GitHub-compatible Markdown reliability and performance reports."""

    def generate(self, data: BenchmarkReportData) -> str:
        lines: list[str] = []

        lines.append("# Krama Benchmark Reliability Report")
        lines.append("")
        lines.append(f"**Generated:** `{data.generated_at}`  ")
        lines.append(
            f"**Total Tasks:** {data.total_tasks} | **Total Runs:** {data.overall_total_runs}  "
        )
        lines.append(
            f"**Overall Success Rate:** {_format_pct(data.overall_success_rate)} "
            f"({data.overall_successful_runs}/{data.overall_total_runs} passed)  "
        )
        lines.append(
            f"**Overall Verifier Accuracy:** {_format_pct(data.overall_verifier_accuracy)} | "
            f"**False Alarm Rate:** {_format_pct(data.overall_false_alarm_rate)}  "
        )
        lines.append(
            f"**Overall Latency:** Avg: {_format_seconds(data.overall_avg_latency_ms)} | "
            f"P50: {_format_seconds(data.overall_median_latency_ms)} | "
            f"P90: {_format_seconds(data.overall_p90_latency_ms)} | "
            f"Total: {_format_seconds(data.overall_total_runtime_ms)}"
        )
        lines.append("")

        if not data.tasks:
            lines.append("> [!NOTE]")
            lines.append(
                "> No benchmark runs or task result logs found in the results directory."
            )
            lines.append("")
            return "\n".join(lines)

        lines.append("## Task Reliability Overview")
        lines.append("")
        lines.append(
            "| Task | Runs | Success Rate | Verifier Accuracy | False Alarms | Avg Latency | P90 Latency |"
        )
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        for task in data.tasks:
            lines.append(
                f"| {task.task_name} "
                f"| {task.total_runs} "
                f"| {_format_pct(task.success_rate)} "
                f"| {_format_pct(task.verifier_accuracy)} "
                f"| {_format_pct(task.false_alarm_rate)} "
                f"| {_format_seconds(task.avg_latency_ms)} "
                f"| {_format_seconds(task.p90_latency_ms)} |"
            )

        lines.append("")
        lines.append("## Latency & Execution Breakdown")
        lines.append("")
        lines.append(
            "| Task | Runs (Pass/Fail) | Mean (Avg) | Median (P50) | P90 Latency | Total Runtime |"
        )
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

        for task in data.tasks:
            pass_fail = f"{task.successful_runs} / {task.failed_runs}"
            lines.append(
                f"| {task.task_name} "
                f"| {pass_fail} "
                f"| {_format_seconds(task.avg_latency_ms)} "
                f"| {_format_seconds(task.median_latency_ms)} "
                f"| {_format_seconds(task.p90_latency_ms)} "
                f"| {_format_seconds(task.total_runtime_ms)} |"
            )

        lines.append("")
        lines.append("## Verifier Reliability & False Alarm Analysis")
        lines.append("")
        lines.append(
            "| Task | True Positive Detections | False Alarms | Verifier Accuracy | False Alarm Rate |"
        )
        lines.append("| :--- | :--- | :--- | :--- | :--- |")

        for task in data.tasks:
            lines.append(
                f"| {task.task_name} "
                f"| {task.true_positive_detections} "
                f"| {task.false_alarms_count} "
                f"| {_format_pct(task.verifier_accuracy)} "
                f"| {_format_pct(task.false_alarm_rate)} |"
            )

        lines.append("")
        return "\n".join(lines)


class HtmlReportGenerator:
    """Generates a standalone, responsive, modern HTML reliability dashboard."""

    def generate(self, data: BenchmarkReportData) -> str:
        tasks_rows = ""
        for t in data.tasks:
            rate_pct = t.success_rate * 100.0
            if rate_pct >= 90.0:
                badge_class = "badge-success"
            elif rate_pct >= 80.0:
                badge_class = "badge-warning"
            else:
                badge_class = "badge-danger"

            v_acc_pct = t.verifier_accuracy * 100.0
            v_badge_class = (
                "badge-success"
                if v_acc_pct >= 95.0
                else ("badge-warning" if v_acc_pct >= 85.0 else "badge-danger")
            )

            fa_pct = t.false_alarm_rate * 100.0
            fa_badge_class = (
                "badge-success"
                if fa_pct <= 2.0
                else ("badge-warning" if fa_pct <= 5.0 else "badge-danger")
            )

            safe_name = html.escape(t.task_name)
            tasks_rows += f"""
            <tr>
              <td class="task-col font-mono font-semibold">{safe_name}</td>
              <td class="text-center">{t.total_runs}</td>
              <td class="text-center">
                <span class="text-emerald-400">{t.successful_runs}</span> /
                <span class="text-rose-400">{t.failed_runs}</span>
              </td>
              <td class="text-center"><span class="badge {badge_class}">{_format_pct(t.success_rate)}</span></td>
              <td class="text-center"><span class="badge {v_badge_class}">{_format_pct(t.verifier_accuracy)}</span></td>
              <td class="text-center"><span class="badge {fa_badge_class}">{_format_pct(t.false_alarm_rate)}</span></td>
              <td class="text-right font-mono">{_format_seconds(t.avg_latency_ms)}</td>
              <td class="text-right font-mono">{_format_seconds(t.median_latency_ms)}</td>
              <td class="text-right font-mono">{_format_seconds(t.p90_latency_ms)}</td>
              <td class="text-right font-mono text-slate-400">{_format_seconds(t.total_runtime_ms)}</td>
            </tr>
            """

        empty_banner = ""
        if not data.tasks:
            empty_banner = """
            <div class="empty-state">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" class="empty-icon">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
              <h3 class="text-lg font-bold text-slate-300">No Benchmark Runs Recorded</h3>
              <p class="text-slate-400 text-sm mt-1">Execute benchmark tasks via <code>just bench &lt;task&gt;</code> to populate run metrics.</p>
            </div>
            """

        overall_rate_pct = data.overall_success_rate * 100.0
        overall_badge = (
            "badge-success"
            if overall_rate_pct >= 90.0
            else ("badge-warning" if overall_rate_pct >= 80.0 else "badge-danger")
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Krama Benchmark Reliability Report</title>
  <style>
    :root {{
      --bg-color: #0b0f19;
      --card-bg: #151d30;
      --card-border: #1e293b;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --success-bg: rgba(16, 185, 129, 0.15);
      --success-text: #34d399;
      --warning-bg: rgba(245, 158, 11, 0.15);
      --warning-text: #fbbf24;
      --danger-bg: rgba(239, 68, 68, 0.15);
      --danger-text: #f87171;
    }}

    @media (prefers-color-scheme: light) {{
      :root {{
        --bg-color: #f8fafc;
        --card-bg: #ffffff;
        --card-border: #e2e8f0;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --accent: #0284c7;
        --success-bg: #dcfce7;
        --success-text: #15803d;
        --warning-bg: #fef3c7;
        --warning-text: #b45309;
        --danger-bg: #fee2e2;
        --danger-text: #b91c1c;
      }}
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg-color);
      color: var(--text-main);
      line-height: 1.5;
      padding: 2rem 1.5rem;
    }}

    .container {{
      max-width: 1280px;
      margin: 0 auto;
    }}

    header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 2rem;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 1.5rem;
      flex-wrap: wrap;
      gap: 1rem;
    }}

    .title-group h1 {{
      font-size: 1.875rem;
      font-weight: 700;
      letter-spacing: -0.025em;
      color: var(--text-main);
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}

    .title-group p {{
      color: var(--text-muted);
      font-size: 0.875rem;
      margin-top: 0.25rem;
    }}

    .timestamp-badge {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 0.4rem 0.8rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}

    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2rem;
    }}

    .card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 0.75rem;
      padding: 1.25rem;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    .card-label {{
      font-size: 0.75rem;
      text-transform: uppercase;
      font-weight: 600;
      letter-spacing: 0.05em;
      color: var(--text-muted);
    }}

    .card-value {{
      font-size: 2rem;
      font-weight: 800;
      margin: 0.35rem 0;
      color: var(--text-main);
    }}

    .card-subtext {{
      font-size: 0.8125rem;
      color: var(--text-muted);
    }}

    .badge {{
      display: inline-block;
      padding: 0.2rem 0.55rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      line-height: 1;
    }}

    .badge-success {{ background: var(--success-bg); color: var(--success-text); }}
    .badge-warning {{ background: var(--warning-bg); color: var(--warning-text); }}
    .badge-danger {{ background: var(--danger-bg); color: var(--danger-text); }}

    .table-container {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 0.75rem;
      overflow-x: auto;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 0.875rem;
    }}

    thead {{
      background: rgba(0, 0, 0, 0.08);
      border-bottom: 1px solid var(--card-border);
    }}

    th {{
      padding: 0.875rem 1rem;
      font-weight: 600;
      color: var(--text-muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    td {{
      padding: 0.875rem 1rem;
      border-bottom: 1px solid var(--card-border);
      color: var(--text-main);
    }}

    tbody tr:last-child td {{
      border-bottom: none;
    }}

    tbody tr:hover {{
      background-color: rgba(255, 255, 255, 0.02);
    }}

    .text-center {{ text-align: center; }}
    .text-right {{ text-align: right; }}
    .font-mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    .font-semibold {{ font-weight: 600; }}
    .text-emerald-400 {{ color: var(--success-text); }}
    .text-rose-400 {{ color: var(--danger-text); }}
    .text-slate-400 {{ color: var(--text-muted); }}

    .empty-state {{
      padding: 4rem 2rem;
      text-align: center;
    }}

    .empty-icon {{
      width: 3rem;
      height: 3rem;
      margin: 0 auto 1rem;
      color: var(--text-muted);
    }}

    footer {{
      margin-top: 3rem;
      text-align: center;
      font-size: 0.8125rem;
      color: var(--text-muted);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>
          <span>⚡</span> Krama Benchmark Reliability Report
        </h1>
        <p>Reliability, verification accuracy, and latency breakdown across benchmark tasks.</p>
      </div>
      <div class="timestamp-badge">
        Generated: {data.generated_at}
      </div>
    </header>

    <div class="cards-grid">
      <div class="card">
        <div class="card-label">Overall Success Rate</div>
        <div class="card-value">{_format_pct(data.overall_success_rate)}</div>
        <div class="card-subtext">
          <span class="badge {overall_badge}">{data.overall_successful_runs} / {data.overall_total_runs} Passed</span>
          ({data.overall_failed_runs} failed)
        </div>
      </div>

      <div class="card">
        <div class="card-label">Verifier Accuracy</div>
        <div class="card-value">{_format_pct(data.overall_verifier_accuracy)}</div>
        <div class="card-subtext">
          False alarm rate: <strong>{_format_pct(data.overall_false_alarm_rate)}</strong>
        </div>
      </div>

      <div class="card">
        <div class="card-label">Latency Breakdown</div>
        <div class="card-value">{_format_seconds(data.overall_avg_latency_ms)}</div>
        <div class="card-subtext">
          P50: <strong>{_format_seconds(data.overall_median_latency_ms)}</strong> |
          P90: <strong>{_format_seconds(data.overall_p90_latency_ms)}</strong>
        </div>
      </div>

      <div class="card">
        <div class="card-label">Volume & Runtime</div>
        <div class="card-value">{data.total_tasks} <span style="font-size:1.1rem;font-weight:500;">tasks</span></div>
        <div class="card-subtext">
          {data.overall_total_runs} total runs · {_format_seconds(data.overall_total_runtime_ms)} wall-clock
        </div>
      </div>
    </div>

    <div class="table-container">
      {empty_banner}
      {"<table><thead><tr><th>Task</th><th class='text-center'>Runs</th><th class='text-center'>Passed / Failed</th><th class='text-center'>Success Rate</th><th class='text-center'>Verifier Accuracy</th><th class='text-center'>False Alarms</th><th class='text-right'>Avg Latency</th><th class='text-right'>P50 (Median)</th><th class='text-right'>P90 Latency</th><th class='text-right'>Total Time</th></tr></thead><tbody>" + tasks_rows + "</tbody></table>" if data.tasks else ""}
    </div>

    <footer>
      <p>Krama Automated Benchmark Reporter · Phase 2 Player Reliability & Performance Gate</p>
    </footer>
  </div>
</body>
</html>
"""


def generate_markdown_report(data: BenchmarkReportData) -> str:
    """Helper to generate a Markdown report string."""
    return MarkdownReportGenerator().generate(data)


def generate_html_report(data: BenchmarkReportData) -> str:
    """Helper to generate an HTML report string."""
    return HtmlReportGenerator().generate(data)
