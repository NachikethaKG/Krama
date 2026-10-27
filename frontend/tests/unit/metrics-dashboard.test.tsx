import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { MetricsSummary } from "@krama/contracts-ts";
import {
  formatMs,
  LatencySparkline,
  MetricsDashboardClient,
  MetricsKpiGrid,
  WorkflowBreakdownTable,
} from "@/components/metrics";
import { mockMetricsSummary } from "@/lib/fixtures";

describe("LatencySparkline", () => {
  it("formats millisecond durations cleanly", () => {
    expect(formatMs(0)).toBe("0s");
    expect(formatMs(500)).toBe("500ms");
    expect(formatMs(1250)).toBe("1.3s");
    expect(formatMs(41140)).toBe("41.1s");
  });

  it("renders an SVG with accessible aria-label and timing labels", () => {
    render(<LatencySparkline p50Ms={38000} p90Ms={52000} />);
    const sparkline = screen.getByRole("img");
    expect(sparkline).toBeInTheDocument();
    expect(sparkline).toHaveAttribute("aria-label");
    expect(sparkline.getAttribute("aria-label")).toContain("P50 38.0s");
    expect(sparkline.getAttribute("aria-label")).toContain("P90 52.0s");
    expect(screen.getByText("P50: 38.0s")).toBeInTheDocument();
    expect(screen.getByText("P90: 52.0s")).toBeInTheDocument();
  });
});

describe("MetricsKpiGrid", () => {
  it("renders 4 PRD §33 KPI cards with passing target badges", () => {
    render(<MetricsKpiGrid summary={mockMetricsSummary} />);

    // 1. Success Rate
    expect(screen.getByTestId("kpi-success-rate")).toBeInTheDocument();
    expect(screen.getByTestId("value-success-rate")).toHaveTextContent("93.3%");
    expect(screen.getByTestId("badge-success-rate")).toHaveTextContent("Target ≥ 80%");

    // 2. Verifier Accuracy
    expect(screen.getByTestId("kpi-verifier-accuracy")).toBeInTheDocument();
    expect(screen.getByTestId("value-verifier-accuracy")).toHaveTextContent("99.7%");
    expect(screen.getByTestId("badge-verifier-accuracy")).toHaveTextContent("Target ≥ 90%");

    // 3. Recovery Rate
    expect(screen.getByTestId("kpi-recovery-rate")).toBeInTheDocument();
    expect(screen.getByTestId("value-recovery-rate")).toHaveTextContent("Not measured");
    expect(screen.getByTestId("badge-recovery-rate")).toHaveTextContent("Target ≥ 50%");

    // 4. Latency Profile
    expect(screen.getByTestId("kpi-latency-profile")).toBeInTheDocument();
    expect(screen.getByTestId("value-latency-profile")).toHaveTextContent("41.1s");
    expect(screen.getByTestId("badge-latency-profile")).toHaveTextContent("Target < 60s");
  });

  it("handles failing thresholds gracefully", () => {
    const failingSummary: MetricsSummary = {
      generated_at: "2026-10-26T12:00:00Z",
      total_tasks: 1,
      overall_success_rate: 0.65, // Below 80%
      overall_verifier_accuracy: 0.82, // Below 90%
      overall_avg_latency_ms: 75000, // Above 60s
      tasks: [],
    };

    render(<MetricsKpiGrid summary={failingSummary} />);

    expect(screen.getByTestId("value-success-rate")).toHaveTextContent("65.0%");
    expect(screen.getByTestId("value-verifier-accuracy")).toHaveTextContent("82.0%");
    expect(screen.getByTestId("value-latency-profile")).toHaveTextContent("75.0s");
  });
});

describe("WorkflowBreakdownTable", () => {
  it("renders the 12 multi-target benchmark tasks with Gitea and GitHub platform badges", () => {
    render(<WorkflowBreakdownTable tasks={mockMetricsSummary.tasks} />);

    const table = screen.getByTestId("metrics-breakdown-table");
    expect(table).toBeInTheDocument();

    // Check Gitea tasks
    expect(screen.getByTestId("task-row-gitea-create-repo")).toBeInTheDocument();
    expect(screen.getByTestId("platform-badge-gitea-create-repo")).toHaveTextContent("Gitea");

    // Check GitHub tasks
    expect(screen.getByTestId("task-row-github-create-repo")).toBeInTheDocument();
    expect(screen.getByTestId("platform-badge-github-create-repo")).toHaveTextContent("GitHub");

    // Total rows = 12
    const rows = screen.getAllByTestId(/^task-row-/);
    expect(rows).toHaveLength(12);
  });

  it("renders empty state message when tasks array is empty", () => {
    render(<WorkflowBreakdownTable tasks={[]} />);
    expect(screen.getByTestId("metrics-empty-tasks")).toHaveTextContent(
      "No workflow tasks found matching the selected filter.",
    );
  });
});

describe("MetricsDashboardClient", () => {
  it("renders full dashboard with KPI grid, badges, and filters tasks by platform", () => {
    render(<MetricsDashboardClient initialData={mockMetricsSummary} />);

    // Header metadata
    expect(screen.getByTestId("metrics-task-count-badge")).toHaveTextContent("12 Benchmark Workflows");
    expect(screen.getByTestId("metrics-kpi-grid")).toBeInTheDocument();

    // Initial state: All 12 workflows
    expect(screen.getAllByTestId(/^task-row-/)).toHaveLength(12);

    // Filter to Gitea
    const giteaTab = screen.getByTestId("filter-tab-gitea");
    fireEvent.click(giteaTab);

    const giteaRows = screen.getAllByTestId(/^task-row-/);
    expect(giteaRows).toHaveLength(6);
    expect(screen.getByTestId("task-row-gitea-create-repo")).toBeInTheDocument();
    expect(screen.queryByTestId("task-row-github-create-repo")).not.toBeInTheDocument();

    // Filter to GitHub
    const githubTab = screen.getByTestId("filter-tab-github");
    fireEvent.click(githubTab);

    const githubRows = screen.getAllByTestId(/^task-row-/);
    expect(githubRows).toHaveLength(6);
    expect(screen.getByTestId("task-row-github-create-repo")).toBeInTheDocument();
    expect(screen.queryByTestId("task-row-gitea-create-repo")).not.toBeInTheDocument();

    // Reset to All
    const allTab = screen.getByTestId("filter-tab-all");
    fireEvent.click(allTab);
    expect(screen.getAllByTestId(/^task-row-/)).toHaveLength(12);
  });

  it("renders empty state card when initialData is null or has zero tasks", () => {
    render(<MetricsDashboardClient initialData={null} />);

    const emptyState = screen.getByTestId("metrics-empty-state");
    expect(emptyState).toBeInTheDocument();
    expect(emptyState).toHaveTextContent("No Benchmark Summary Available");
    expect(emptyState).toHaveTextContent("just bench-report");
  });
});
