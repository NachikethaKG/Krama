"use client";

import type { TaskMetrics } from "@krama/contracts-ts";
import { LatencySparkline } from "./LatencySparkline";

export interface WorkflowBreakdownTableProps {
  tasks: TaskMetrics[];
}

export function getTaskPlatform(task: TaskMetrics): "gitea" | "github" {
  const extended = task as unknown as { platform?: string };
  if (extended.platform === "github" || extended.platform === "gitea") {
    return extended.platform;
  }
  return task.task_name.toLowerCase().includes("github") ? "github" : "gitea";
}

function formatTaskTitle(taskName: string): string {
  // e.g. "gitea-create-repo" -> "Create Repository"
  return taskName
    .replace(/^(gitea|github)-/, "")
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function WorkflowBreakdownTable({ tasks }: WorkflowBreakdownTableProps) {
  if (tasks.length === 0) {
    return (
      <div
        data-testid="metrics-empty-tasks"
        className="rounded-xl border border-dashed border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950"
      >
        <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
          No workflow tasks found matching the selected filter.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-xs dark:border-zinc-800 dark:bg-zinc-950">
      <div className="overflow-x-auto">
        <table
          data-testid="metrics-breakdown-table"
          className="w-full text-left text-xs border-collapse"
        >
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50/80 dark:border-zinc-800 dark:bg-zinc-900/50">
              <th scope="col" className="py-3.5 pl-4 pr-3 font-semibold text-zinc-900 dark:text-zinc-100 sm:pl-6">
                Workflow Task
              </th>
              <th scope="col" className="px-3 py-3.5 font-semibold text-zinc-900 dark:text-zinc-100">
                Platform
              </th>
              <th scope="col" className="px-3 py-3.5 font-semibold text-zinc-900 dark:text-zinc-100 text-center">
                Trials (Pass/Fail)
              </th>
              <th scope="col" className="px-3 py-3.5 font-semibold text-zinc-900 dark:text-zinc-100 text-right">
                Success Rate
              </th>
              <th scope="col" className="px-3 py-3.5 font-semibold text-zinc-900 dark:text-zinc-100 text-right">
                Verifier Accuracy
              </th>
              <th scope="col" className="py-3.5 pl-3 pr-4 font-semibold text-zinc-900 dark:text-zinc-100 sm:pr-6">
                Latency Profile (P50 / P90)
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {tasks.map((task) => {
              const platform = getTaskPlatform(task);
              const successRatePct = (task.success_rate * 100).toFixed(1);
              const verifierAccuracyPct = (task.verifier_accuracy * 100).toFixed(1);
              const isSuccessPassed = task.success_rate >= 0.8;
              const p50 = task.median_latency_ms ?? task.avg_latency_ms;
              const p90 = task.p90_latency_ms;
              const failedCount = task.failed_runs ?? (task.total_runs - task.successful_runs);

              return (
                <tr
                  key={task.task_name}
                  data-testid={`task-row-${task.task_name}`}
                  className="hover:bg-zinc-50/60 dark:hover:bg-zinc-900/40 transition-colors"
                >
                  {/* Task name & title */}
                  <td className="py-4 pl-4 pr-3 sm:pl-6 font-medium text-zinc-900 dark:text-zinc-100">
                    <div className="font-semibold text-sm text-zinc-900 dark:text-zinc-100">
                      {formatTaskTitle(task.task_name)}
                    </div>
                    <div className="mt-0.5 font-mono text-xs text-zinc-500 dark:text-zinc-400">
                      {task.task_name}
                    </div>
                  </td>

                  {/* Platform badge */}
                  <td className="px-3 py-4 whitespace-nowrap">
                    {platform === "github" ? (
                      <span
                        data-testid={`platform-badge-${task.task_name}`}
                        className="inline-flex items-center gap-1 rounded-md bg-purple-50 px-2 py-0.5 text-xs font-semibold text-purple-700 dark:bg-purple-950/50 dark:text-purple-300 border border-purple-200 dark:border-purple-800"
                      >
                        <svg className="size-3 fill-current" viewBox="0 0 16 16" aria-hidden="true">
                          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                        </svg>
                        GitHub
                      </span>
                    ) : (
                      <span
                        data-testid={`platform-badge-${task.task_name}`}
                        className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
                      >
                        <span className="size-1.5 rounded-full bg-amber-500" />
                        Gitea
                      </span>
                    )}
                  </td>

                  {/* Trials count */}
                  <td className="px-3 py-4 text-center whitespace-nowrap">
                    <span className="font-semibold text-zinc-900 dark:text-zinc-100 font-mono">
                      {task.total_runs}
                    </span>
                    <span className="ml-1 text-zinc-500 dark:text-zinc-400 font-mono text-[11px]">
                      ({task.successful_runs} /{" "}
                      <span className={failedCount > 0 ? "text-rose-600 font-bold" : ""}>
                        {failedCount}
                      </span>
                      )
                    </span>
                  </td>

                  {/* Success Rate */}
                  <td className="px-3 py-4 text-right whitespace-nowrap">
                    <span
                      data-testid={`success-rate-${task.task_name}`}
                      className={`inline-flex items-center gap-1 font-mono font-semibold ${
                        isSuccessPassed
                          ? "text-emerald-700 dark:text-emerald-400"
                          : "text-amber-700 dark:text-amber-400"
                      }`}
                    >
                      {successRatePct}%
                    </span>
                  </td>

                  {/* Verifier Accuracy */}
                  <td className="px-3 py-4 text-right whitespace-nowrap font-mono text-zinc-700 dark:text-zinc-300">
                    <span data-testid={`accuracy-${task.task_name}`}>
                      {verifierAccuracyPct}%
                    </span>
                  </td>

                  {/* Latency profile with sparkline */}
                  <td className="py-4 pl-3 pr-4 sm:pr-6 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      <LatencySparkline p50Ms={p50} p90Ms={p90} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
