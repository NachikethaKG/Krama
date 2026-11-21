"use client";

import { useTranslations } from "next-intl";

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
  const t = useTranslations("metrics.table");
  if (tasks.length === 0) {
    return (
      <div
        data-testid="metrics-empty-tasks"
        className="kr-glass rounded-3xl border-dashed p-8 text-center"
      >
        <p className="text-sm font-medium text-ink-400">
          {t("empty")}
        </p>
      </div>
    );
  }

  return (
    <div className="kr-glass overflow-hidden rounded-3xl">
      <div className="overflow-x-auto">
        <table
          data-testid="metrics-breakdown-table"
          className="w-full text-left text-xs border-collapse"
        >
          <thead>
            <tr className="border-b border-white/10 bg-gradient-to-r from-run/15 via-approve/10 to-ask/15">
              <th scope="col" className="py-3.5 pl-4 pr-3 font-bold uppercase tracking-wider text-[10px] text-ink-300 sm:pl-6">
                {t("task")}
              </th>
              <th scope="col" className="px-3 py-3.5 font-bold uppercase tracking-wider text-[10px] text-ink-300">
                {t("platform")}
              </th>
              <th scope="col" className="px-3 py-3.5 font-bold uppercase tracking-wider text-[10px] text-ink-300 text-center">
                {t("trials")}
              </th>
              <th scope="col" className="px-3 py-3.5 font-bold uppercase tracking-wider text-[10px] text-ink-300 text-right">
                {t("successRate")}
              </th>
              <th scope="col" className="px-3 py-3.5 font-bold uppercase tracking-wider text-[10px] text-ink-300 text-right">
                {t("verifierAccuracy")}
              </th>
              <th scope="col" className="py-3.5 pl-3 pr-4 font-bold uppercase tracking-wider text-[10px] text-ink-300 sm:pr-6">
                {t("latency")}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
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
                  className="hover:bg-white/[0.04] transition-colors"
                >
                  {/* Task name & title */}
                  <td className="py-4 pl-4 pr-3 sm:pl-6 font-medium text-white">
                    <div className="font-semibold text-sm text-white">
                      {formatTaskTitle(task.task_name)}
                    </div>
                    <div className="mt-0.5 font-mono text-xs text-ink-400">
                      {task.task_name}
                    </div>
                  </td>

                  {/* Platform badge */}
                  <td className="px-3 py-4 whitespace-nowrap">
                    {platform === "github" ? (
                      <span
                        data-testid={`platform-badge-${task.task_name}`}
                        className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold bg-approve/15 text-approve border border-approve/40"
                      >
                        <svg className="size-3 fill-current" viewBox="0 0 16 16" aria-hidden="true">
                          <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                        </svg>
                        GitHub
                      </span>
                    ) : (
                      <span
                        data-testid={`platform-badge-${task.task_name}`}
                        className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold bg-plan/15 text-plan border border-plan/40"
                      >
                        <span className="size-1.5 rounded-full bg-plan" />
                        Gitea
                      </span>
                    )}
                  </td>

                  {/* Trials count */}
                  <td className="px-3 py-4 text-center whitespace-nowrap">
                    <span className="font-semibold text-white font-mono">
                      {task.total_runs}
                    </span>
                    <span className="ml-1 text-ink-400 font-mono text-[11px]">
                      ({task.successful_runs} /{" "}
                      <span className={failedCount > 0 ? "text-danger font-bold" : ""}>
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
                          ? "text-verify"
                          : "text-plan"
                      }`}
                    >
                      {successRatePct}%
                    </span>
                  </td>

                  {/* Verifier Accuracy */}
                  <td className="px-3 py-4 text-right whitespace-nowrap font-mono text-ink-300">
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
