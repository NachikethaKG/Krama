import Link from "next/link";
import type { RunListItem } from "@/lib/types";
import { RunStatusBadge } from "./RunStatusBadge";

export interface RunListTableProps {
  runs: RunListItem[];
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}

export function formatDateTime(isoString?: string | null): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return isoString;
    return d.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoString;
  }
}

export function formatDuration(seconds?: number | null): string {
  if (seconds === undefined || seconds === null) return "—";
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const remainingSecs = seconds % 60;
  return `${mins}m ${remainingSecs}s`;
}

export function RunListTable({
  runs,
  isLoading = false,
  error = null,
  className = "",
}: RunListTableProps) {
  if (isLoading) {
    return (
      <div
        data-testid="runs-loading"
        className="flex flex-col items-center justify-center p-12 text-center border border-zinc-200 dark:border-zinc-800 rounded-xl bg-white dark:bg-zinc-900"
      >
        <div className="size-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Loading run history…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="runs-error"
        className="p-6 border border-rose-200 dark:border-rose-900/50 rounded-xl bg-rose-50 dark:bg-rose-950/30 text-rose-800 dark:text-rose-300"
      >
        <div className="flex items-center gap-2 font-semibold text-sm mb-1">
          <svg className="size-5 text-rose-600 dark:text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Failed to load run history
        </div>
        <p className="text-xs text-rose-700 dark:text-rose-400">{error}</p>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div
        data-testid="runs-empty-state"
        className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-zinc-300 dark:border-zinc-700 rounded-xl bg-zinc-50 dark:bg-zinc-900/50"
      >
        <div className="size-12 rounded-full bg-zinc-200 dark:bg-zinc-800 flex items-center justify-center mb-3 text-zinc-400 dark:text-zinc-500">
          <svg className="size-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">No runs found</h3>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 max-w-sm">
          No workflow runs match the current criteria. Start a new workflow from the prompt view to see results here.
        </p>
        <Link
          href="/"
          className="mt-4 px-3.5 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition-colors"
        >
          Create Workflow
        </Link>
      </div>
    );
  }

  return (
    <div
      data-testid="runs-list-table"
      className={`overflow-hidden border border-zinc-200 dark:border-zinc-800 rounded-xl bg-white dark:bg-zinc-900 shadow-sm ${className}`}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-800/60 text-xs font-semibold text-zinc-600 dark:text-zinc-400 border-b border-zinc-200 dark:border-zinc-800">
            <tr>
              <th scope="col" className="py-3.5 px-4">Run</th>
              <th scope="col" className="py-3.5 px-4">Prompt</th>
              <th scope="col" className="py-3.5 px-4">Status</th>
              <th scope="col" className="py-3.5 px-4">Started At</th>
              <th scope="col" className="py-3.5 px-4">Duration</th>
              <th scope="col" className="py-3.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {runs.map((run) => (
              <tr
                key={run.id}
                data-testid={`run-row-${run.id}`}
                className="hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40 transition-colors"
              >
                <td className="py-3.5 px-4 font-mono text-xs text-zinc-600 dark:text-zinc-400">
                  <Link
                    href={`/runs/${run.id}`}
                    data-testid="run-link"
                    className="hover:text-emerald-600 dark:hover:text-emerald-400 font-semibold"
                  >
                    <span data-testid="run-id">{run.id}</span>
                  </Link>
                </td>
                <td className="py-3.5 px-4 max-w-md">
                  <div
                    data-testid="run-prompt"
                    className="truncate text-zinc-900 dark:text-zinc-100 font-medium"
                    title={run.prompt}
                  >
                    {run.prompt}
                  </div>
                  {run.retryCount && run.retryCount > 0 ? (
                    <span
                      data-testid="run-retries"
                      className="inline-block text-[11px] text-amber-600 dark:text-amber-400 mt-0.5"
                    >
                      {run.retryCount} {run.retryCount === 1 ? "retry" : "retries"}
                    </span>
                  ) : null}
                </td>
                <td className="py-3.5 px-4 whitespace-nowrap">
                  <RunStatusBadge status={run.status} size="sm" />
                </td>
                <td
                  data-testid="run-started-at"
                  className="py-3.5 px-4 whitespace-nowrap text-xs text-zinc-600 dark:text-zinc-400"
                >
                  {formatDateTime(run.startedAt || run.createdAt)}
                </td>
                <td
                  data-testid="run-duration"
                  className="py-3.5 px-4 whitespace-nowrap text-xs text-zinc-600 dark:text-zinc-400"
                >
                  {formatDuration(run.durationSeconds)}
                </td>
                <td className="py-3.5 px-4 whitespace-nowrap text-right">
                  <Link
                    href={`/runs/${run.id}`}
                    data-testid="run-view-button"
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-700 transition-colors"
                  >
                    View Evidence
                    <svg className="size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
