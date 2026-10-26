"use client";

import { useState } from "react";
import Link from "next/link";
import type { MetricsSummary } from "@krama/contracts-ts";
import { MetricsKpiGrid } from "./MetricsKpiGrid";
import { getTaskPlatform, WorkflowBreakdownTable } from "./WorkflowBreakdownTable";

export interface MetricsDashboardClientProps {
  initialData?: MetricsSummary | null;
}

export type PlatformFilter = "all" | "gitea" | "github";

function formatGeneratedDate(dateStr?: string): string {
  if (!dateStr) return "Not available";
  try {
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function MetricsDashboardClient({ initialData }: MetricsDashboardClientProps) {
  const [platformFilter, setPlatformFilter] = useState<PlatformFilter>("all");

  const tasks = initialData?.tasks ?? [];

  const giteaTasksCount = tasks.filter((t) => getTaskPlatform(t) === "gitea").length;
  const githubTasksCount = tasks.filter((t) => getTaskPlatform(t) === "github").length;

  const filteredTasks =
    platformFilter === "all"
      ? tasks
      : tasks.filter((t) => getTaskPlatform(t) === platformFilter);

  const formattedDate = formatGeneratedDate(initialData?.generated_at);

  if (!initialData || tasks.length === 0) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-12 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl space-y-8">
          {/* Breadcrumb nav */}
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <Link
              href="/dashboard"
              className="font-medium text-zinc-700 hover:text-indigo-600 dark:text-zinc-300 dark:hover:text-indigo-400 transition-colors"
            >
              ← User Dashboard
            </Link>
            <span className="text-zinc-300 dark:text-zinc-700">/</span>
            <span className="font-semibold text-zinc-900 dark:text-zinc-100">Technical Metrics</span>
          </div>

          <div
            data-testid="metrics-empty-state"
            className="rounded-2xl border border-dashed border-zinc-300 bg-white p-12 text-center dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-500 mb-4">
              <svg className="size-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
              </svg>
            </div>
            <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
              No Benchmark Summary Available
            </h2>
            <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 max-w-md mx-auto">
              Run the multi-target benchmark collector across Gitea and GitHub to generate real metrics data.
            </p>
            <div className="mt-6 flex flex-col items-center gap-3">
              <code className="rounded-lg bg-zinc-100 px-4 py-2 font-mono text-xs font-semibold text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
                just bench-report
              </code>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Generates <code className="font-mono">benchmarks/results/summary.json</code> adhering to PRD §33.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-8">
        {/* Navigation Breadcrumbs */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <Link
              href="/"
              className="font-medium text-zinc-700 hover:text-indigo-600 dark:text-zinc-300 dark:hover:text-indigo-400 transition-colors"
            >
              ← Krama Home
            </Link>
            <span className="text-zinc-300 dark:text-zinc-700">/</span>
            <Link
              href="/dashboard"
              className="font-medium text-zinc-700 hover:text-indigo-600 dark:text-zinc-300 dark:hover:text-indigo-400 transition-colors"
            >
              User Dashboard
            </Link>
            <span className="text-zinc-300 dark:text-zinc-700">/</span>
            <span className="font-semibold text-zinc-900 dark:text-zinc-100">Technical Metrics</span>
          </div>

          <div className="flex items-center gap-2 text-xs text-zinc-500 font-mono">
            <span>Generated:</span>
            <span data-testid="metrics-generated-at" className="font-semibold text-zinc-800 dark:text-zinc-200">
              {formattedDate}
            </span>
          </div>
        </div>

        {/* Header Section */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-zinc-200 dark:border-zinc-800 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 sm:text-3xl">
                PRD §33 Technical Metrics
              </h1>
              <span
                data-testid="metrics-task-count-badge"
                className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300"
              >
                {initialData.total_tasks} Benchmark Workflows
              </span>
            </div>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              Multi-target reliability matrix evaluating Task Success Rate, Verifier Accuracy, Recovery Rate, and Latency Profile across Gitea &amp; GitHub.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/runs/new"
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-indigo-500 transition-colors"
            >
              <span>+ Launch Real Run</span>
            </Link>
          </div>
        </div>

        {/* Top-Level KPI Summary Cards */}
        <section aria-labelledby="kpi-summary-heading">
          <h2 id="kpi-summary-heading" className="sr-only">
            Key Performance Indicators
          </h2>
          <MetricsKpiGrid summary={initialData} />
        </section>

        {/* Workflow Breakdown Section */}
        <section aria-labelledby="workflows-breakdown-heading" className="space-y-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2
                id="workflows-breakdown-heading"
                className="text-lg font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-2"
              >
                <span>Task Matrix Breakdown</span>
                <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                  {filteredTasks.length}
                </span>
              </h2>
              <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                Granular trial counts, verification accuracy, and execution latency profiles per workflow
              </p>
            </div>

            {/* Platform Filter Tabs */}
            <div
              data-testid="platform-filter-tabs"
              className="inline-flex rounded-lg border border-zinc-200 bg-zinc-100/80 p-0.5 dark:border-zinc-800 dark:bg-zinc-900"
              role="tablist"
              aria-label="Filter workflows by target platform"
            >
              <button
                type="button"
                role="tab"
                aria-selected={platformFilter === "all"}
                data-testid="filter-tab-all"
                onClick={() => setPlatformFilter("all")}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                  platformFilter === "all"
                    ? "bg-white text-zinc-900 shadow-xs dark:bg-zinc-800 dark:text-zinc-100"
                    : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
                }`}
              >
                All Workflows ({tasks.length})
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={platformFilter === "gitea"}
                data-testid="filter-tab-gitea"
                onClick={() => setPlatformFilter("gitea")}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                  platformFilter === "gitea"
                    ? "bg-white text-zinc-900 shadow-xs dark:bg-zinc-800 dark:text-zinc-100"
                    : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
                }`}
              >
                Gitea ({giteaTasksCount})
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={platformFilter === "github"}
                data-testid="filter-tab-github"
                onClick={() => setPlatformFilter("github")}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                  platformFilter === "github"
                    ? "bg-white text-zinc-900 shadow-xs dark:bg-zinc-800 dark:text-zinc-100"
                    : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
                }`}
              >
                GitHub ({githubTasksCount})
              </button>
            </div>
          </div>

          <WorkflowBreakdownTable tasks={filteredTasks} />
        </section>
      </div>
    </div>
  );
}
