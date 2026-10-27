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

describe("MetricsDashboard Components", () => {
  describe("MetricsKpiGrid", () => {
    it("renders all 4 PRD §33 KPI numbers and threshold labels display", () => {
      render(<MetricsKpiGrid summary={mockMetricsSummary} />);

      // 1. Task Success Rate KPI card & target indicator
      expect(screen.getByTestId("kpi-success-rate")).toBeInTheDocument();
      expect(screen.getByTestId("value-success-rate")).toHaveTextContent("93.3%");
      expect(screen.getByTestId("badge-success-rate")).toHaveTextContent("Target ≥ 80%");

      // 2. Verifier Accuracy KPI card & target indicator
      expect(screen.getByTestId("kpi-verifier-accuracy")).toBeInTheDocument();
      expect(screen.getByTestId("value-verifier-accuracy")).toHaveTextContent("99.7%");
      expect(screen.getByTestId("badge-verifier-accuracy")).toHaveTextContent("Target ≥ 90%");

      // 3. Recovery Rate KPI card & target indicator
      expect(screen.getByTestId("kpi-recovery-rate")).toBeInTheDocument();
      expect(screen.getByTestId("value-recovery-rate")).toHaveTextContent("100.0%");
      expect(screen.getByTestId("badge-recovery-rate")).toHaveTextContent("Target ≥ 50%");

      // 4. Latency Profile KPI card & target indicator
      expect(screen.getByTestId("kpi-latency-profile")).toBeInTheDocument();
      expect(screen.getByTestId("value-latency-profile")).toHaveTextContent("41.1s");
      expect(screen.getByTestId("badge-latency-profile")).toHaveTextContent("Target < 60s");
    });

    it("displays alert indicators when metrics fall below target thresholds", () => {
      const failingSummary: MetricsSummary = {
        generated_at: "2026-10-26T12:00:00Z",
        total_tasks: 1,
        overall_success_rate: 0.72, // Below 80%
        overall_verifier_accuracy: 0.85, // Below 90%
        overall_avg_latency_ms: 72000, // Above 60s
        tasks: [],
      };

      render(<MetricsKpiGrid summary={failingSummary} />);

      expect(screen.getByTestId("value-success-rate")).toHaveTextContent("72.0%");
      expect(screen.getByTestId("value-verifier-accuracy")).toHaveTextContent("85.0%");
      expect(screen.getByTestId("value-latency-profile")).toHaveTextContent("72.0s");
    });
  });

  describe("WorkflowBreakdownTable", () => {
    it("renders rows for both Gitea and GitHub workflows with platform badges", () => {
      render(<WorkflowBreakdownTable tasks={mockMetricsSummary.tasks} />);

      const table = screen.getByTestId("metrics-breakdown-table");
      expect(table).toBeInTheDocument();

      // Assert Gitea workflow rows and badge
      expect(screen.getByTestId("task-row-gitea-create-repo")).toBeInTheDocument();
      expect(screen.getByTestId("platform-badge-gitea-create-repo")).toHaveTextContent("Gitea");
      expect(screen.getByTestId("task-row-gitea-add-file")).toBeInTheDocument();

      // Assert GitHub workflow rows and badge
      expect(screen.getByTestId("task-row-github-create-repo")).toBeInTheDocument();
      expect(screen.getByTestId("platform-badge-github-create-repo")).toHaveTextContent("GitHub");
      expect(screen.getByTestId("task-row-github-add-file")).toBeInTheDocument();

      // Total 12 tasks represented
      const allRows = screen.getAllByTestId(/^task-row-/);
      expect(allRows).toHaveLength(12);
    });

    it("renders friendly zero-state message when task list is empty", () => {
      render(<WorkflowBreakdownTable tasks={[]} />);
      expect(screen.getByTestId("metrics-empty-tasks")).toHaveTextContent(
        "No workflow tasks found matching the selected filter.",
      );
    });
  });

  describe("LatencySparkline", () => {
    it("renders SVG with timing markers and accessible aria-label", () => {
      render(<LatencySparkline p50Ms={38500} p90Ms={52500} />);

      const sparkline = screen.getByRole("img");
      expect(sparkline).toBeInTheDocument();
      expect(sparkline.getAttribute("aria-label")).toContain("P50 38.5s");
      expect(sparkline.getAttribute("aria-label")).toContain("P90 52.5s");
      expect(screen.getByText("P50: 38.5s")).toBeInTheDocument();
      expect(screen.getByText("P90: 52.5s")).toBeInTheDocument();
    });

    it("formats millisecond durations correctly", () => {
      expect(formatMs(0)).toBe("0s");
      expect(formatMs(450)).toBe("450ms");
      expect(formatMs(1500)).toBe("1.5s");
      expect(formatMs(41142)).toBe("41.1s");
    });
  });

  describe("MetricsDashboardClient", () => {
    it("filters task table rows by target platform tabs", () => {
      render(<MetricsDashboardClient initialData={mockMetricsSummary} />);

      // Starts with All 12 workflows
      expect(screen.getAllByTestId(/^task-row-/)).toHaveLength(12);

      // Switch to Gitea tab
      const giteaTab = screen.getByTestId("filter-tab-gitea");
      fireEvent.click(giteaTab);
      const giteaRows = screen.getAllByTestId(/^task-row-/);
      expect(giteaRows).toHaveLength(6);
      expect(screen.getByTestId("task-row-gitea-create-repo")).toBeInTheDocument();
      expect(screen.queryByTestId("task-row-github-create-repo")).not.toBeInTheDocument();

      // Switch to GitHub tab
      const githubTab = screen.getByTestId("filter-tab-github");
      fireEvent.click(githubTab);
      const githubRows = screen.getAllByTestId(/^task-row-/);
      expect(githubRows).toHaveLength(6);
      expect(screen.getByTestId("task-row-github-create-repo")).toBeInTheDocument();
      expect(screen.queryByTestId("task-row-gitea-create-repo")).not.toBeInTheDocument();

      // Switch back to All tab
      const allTab = screen.getByTestId("filter-tab-all");
      fireEvent.click(allTab);
      expect(screen.getAllByTestId(/^task-row-/)).toHaveLength(12);
    });

    it("renders empty state card when initialData is null", () => {
      render(<MetricsDashboardClient initialData={null} />);

      const emptyCard = screen.getByTestId("metrics-empty-state");
      expect(emptyCard).toBeInTheDocument();
      expect(emptyCard).toHaveTextContent("No Benchmark Summary Available");
      expect(emptyCard).toHaveTextContent("just bench-report");
    });
  });
});
