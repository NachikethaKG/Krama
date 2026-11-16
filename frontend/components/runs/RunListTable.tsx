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
        className="kr-glass flex flex-col items-center justify-center rounded-3xl p-12 text-center"
      >
        <div className="mb-3 size-10 animate-spin rounded-full border-4 border-white/10 border-t-run shadow-[0_0_24px_-4px_var(--run)]" />
        <p className="text-sm text-ink-400">Loading runs…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="runs-error"
        className="kr-danger kr-tone-card rounded-3xl p-6 text-danger"
      >
        <div className="flex items-center gap-2 font-semibold text-sm mb-1">
          <svg className="size-5 text-danger" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Couldn&apos;t load your runs
        </div>
        <p className="text-xs text-danger">{error}</p>
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div
        data-testid="runs-empty-state"
        className="kr-run kr-tone-card flex flex-col items-center justify-center rounded-3xl border-dashed p-12 text-center"
      >
        <div className="kr-float mb-3 flex size-14 items-center justify-center rounded-2xl bg-run text-ink-950 shadow-[0_0_30px_-4px_var(--run)]">
          <svg className="size-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        </div>
        <h3 className="kr-display text-xl font-bold text-white">No runs yet</h3>
        <p className="text-xs text-ink-400 mt-1 max-w-sm">
          Each time Krama does a task for you, it shows up here.
        </p>
        <Link
          href="/"
          className="kr-btn kr-btn-primary mt-5 px-5 py-2 text-xs"
        >
          New tutorial
        </Link>
      </div>
    );
  }

  return (
    <div
      data-testid="runs-list-table"
      className={`kr-glass overflow-hidden rounded-3xl ${className}`}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-white/10 bg-white/[0.03] text-[11px] font-bold uppercase tracking-[0.18em] text-ink-400">
            <tr>
              <th scope="col" className="py-3.5 px-4">Task</th>
              <th scope="col" className="py-3.5 px-4">Result</th>
              <th scope="col" className="py-3.5 px-4">Started</th>
              <th scope="col" className="py-3.5 px-4">Took</th>
              <th scope="col" className="py-3.5 px-4 text-right">
                <span className="sr-only">Open</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10">
            {runs.map((run) => (
              <tr
                key={run.id}
                data-testid={`run-row-${run.id}`}
                className="group relative transition-all duration-300 hover:bg-gradient-to-r hover:from-run/10 hover:via-approve/5 hover:to-transparent"
              >
                <td className="py-3.5 px-4 max-w-md">
                  <Link
                    href={`/runs/${run.id}`}
                    data-testid="run-link"
                    className="block truncate font-semibold text-white transition-colors group-hover:text-run"
                    title={run.prompt ?? undefined}
                  >
                    <span data-testid="run-prompt">{run.prompt ?? "(task text unavailable)"}</span>
                    <span data-testid="run-id" className="sr-only">
                      {run.id}
                    </span>
                  </Link>
                  {run.retryCount && run.retryCount > 0 ? (
                    <span
                      data-testid="run-retries"
                      className="inline-block text-[11px] text-plan mt-0.5"
                    >
                      {run.retryCount === 1 ? "Retried once" : `Retried ${run.retryCount} times`}
                    </span>
                  ) : null}
                </td>
                <td className="py-3.5 px-4 whitespace-nowrap">
                  <RunStatusBadge status={run.status} size="sm" />
                </td>
                <td
                  data-testid="run-started-at"
                  className="py-3.5 px-4 whitespace-nowrap text-xs text-ink-400"
                >
                  {formatDateTime(run.startedAt || run.createdAt)}
                </td>
                <td
                  data-testid="run-duration"
                  className="py-3.5 px-4 whitespace-nowrap text-xs text-ink-400"
                >
                  {formatDuration(run.durationSeconds)}
                </td>
                <td className="py-3.5 px-4 whitespace-nowrap text-right">
                  <Link
                    href={`/runs/${run.id}`}
                    data-testid="run-view-button"
                    className="kr-btn kr-btn-ghost kr-run px-3 py-1 text-xs"
                  >
                    Details
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
