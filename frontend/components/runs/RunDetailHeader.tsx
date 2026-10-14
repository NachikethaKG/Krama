import Link from "next/link";
import type { RunDetails } from "@/lib/types";
import { RunStatusBadge } from "./RunStatusBadge";
import { formatDateTime, formatDuration } from "./RunListTable";

export interface RunDetailHeaderProps {
  runDetails: RunDetails;
  className?: string;
}

export function RunDetailHeader({ runDetails, className = "" }: RunDetailHeaderProps) {
  const { run, summary, targetUrl } = runDetails;

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Navigation Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
        <Link
          href="/runs"
          data-testid="back-to-runs-link"
          className="inline-flex items-center gap-1 hover:text-zinc-900 dark:hover:text-zinc-100 font-medium transition-colors"
        >
          <svg className="size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Run History
        </Link>
        <span>/</span>
        <span data-testid="run-detail-id" className="font-mono text-zinc-700 dark:text-zinc-300">
          {run.id}
        </span>
      </div>

      {/* Main Title & Status */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm">
        <div className="space-y-1 max-w-3xl">
          <div className="flex items-center gap-2.5">
            <h1
              data-testid="run-detail-prompt"
              className="text-lg sm:text-xl font-bold text-zinc-900 dark:text-zinc-100"
            >
              {run.prompt}
            </h1>
            <RunStatusBadge status={run.status} size="md" />
          </div>
          {targetUrl && (
            <p
              data-testid="stat-target-url"
              className="text-xs text-zinc-500 dark:text-zinc-400 font-mono truncate"
            >
              Target: <span className="text-zinc-700 dark:text-zinc-300">{targetUrl}</span>
            </p>
          )}
        </div>

        <div className="text-xs text-zinc-500 dark:text-zinc-400 shrink-0">
          <div>Started: <span className="font-medium text-zinc-700 dark:text-zinc-300">{formatDateTime(run.startedAt || run.createdAt)}</span></div>
          {run.finishedAt && (
            <div>Finished: <span className="font-medium text-zinc-700 dark:text-zinc-300">{formatDateTime(run.finishedAt)}</span></div>
          )}
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
          <span className="text-xs text-zinc-500 dark:text-zinc-400 block mb-0.5">Total Steps</span>
          <span
            data-testid="stat-total-steps"
            className="text-xl font-bold text-zinc-900 dark:text-zinc-100"
          >
            {summary.totalSteps}
          </span>
        </div>

        <div className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
          <span className="text-xs text-zinc-500 dark:text-zinc-400 block mb-0.5">Verified Steps</span>
          <span
            data-testid="stat-verified-steps"
            className="text-xl font-bold text-emerald-600 dark:text-emerald-400"
          >
            {summary.verifiedSteps}
          </span>
        </div>

        <div className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
          <span className="text-xs text-zinc-500 dark:text-zinc-400 block mb-0.5">Failed Steps</span>
          <span
            data-testid="stat-failed-steps"
            className={`text-xl font-bold ${
              summary.failedSteps > 0
                ? "text-rose-600 dark:text-rose-400"
                : "text-zinc-600 dark:text-zinc-400"
            }`}
          >
            {summary.failedSteps}
          </span>
        </div>

        <div className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
          <span className="text-xs text-zinc-500 dark:text-zinc-400 block mb-0.5">Duration</span>
          <span
            data-testid="stat-duration"
            className="text-xl font-bold text-zinc-900 dark:text-zinc-100 font-mono"
          >
            {formatDuration(summary.durationSeconds ?? run.durationSeconds)}
          </span>
        </div>
      </div>
    </div>
  );
}
