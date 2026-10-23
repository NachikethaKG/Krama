"use client";

import Link from "next/link";
import type { RunListItem } from "@/lib/types";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";

export interface RecentRunsSectionProps {
  runs: RunListItem[];
}

function formatDuration(seconds?: number | null): string {
  if (!seconds || seconds <= 0) return "< 1s";
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const remSec = seconds % 60;
  return `${mins}m ${remSec}s`;
}

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

export function RecentRunsSection({ runs }: RecentRunsSectionProps) {
  return (
    <section aria-labelledby="recent-runs-heading">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2
            id="recent-runs-heading"
            className="text-lg font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-2"
          >
            <span>Recent Executions</span>
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
              {runs.length}
            </span>
          </h2>
          <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
            Recent headless execution runs and verification evidence
          </p>
        </div>

        <Link
          href="/runs"
          className="text-xs font-semibold text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
        >
          View all runs history →
        </Link>
      </div>

      {runs.length === 0 ? (
        <div
          data-testid="empty-recent-runs"
          className="rounded-xl border border-dashed border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950"
        >
          <div className="mx-auto flex size-10 items-center justify-center rounded-full bg-zinc-100 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-500 mb-3">
            <svg
              className="size-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z"
              />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            No execution runs found
          </h3>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400 max-w-sm mx-auto">
            Submit a task against Gitea or GitHub to initiate automated planning and execution.
          </p>
          <Link
            href="/runs/new"
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
          >
            + Start New Execution
          </Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-xs dark:border-zinc-800 dark:bg-zinc-950">
          <div className="overflow-x-auto">
            <table
              data-testid="recent-runs-table"
              className="min-w-full divide-y divide-zinc-200 text-left text-xs dark:divide-zinc-800"
            >
              <thead className="bg-zinc-50/75 dark:bg-zinc-900/50 text-zinc-500 dark:text-zinc-400 font-semibold">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Run ID
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Task Prompt
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Status
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Started
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Duration
                  </th>
                  <th scope="col" className="px-4 py-3 text-right">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60 text-zinc-700 dark:text-zinc-300">
                {runs.map((run) => (
                  <tr
                    key={run.id}
                    data-testid="recent-run-row"
                    className="hover:bg-zinc-50/50 dark:hover:bg-zinc-900/30 transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-[11px] font-medium text-zinc-900 dark:text-zinc-100">
                      <Link
                        href={`/runs/${run.id}`}
                        className="hover:text-indigo-600 dark:hover:text-indigo-400 underline decoration-zinc-300 underline-offset-2"
                      >
                        {run.id.slice(0, 8)}…
                      </Link>
                    </td>

                    <td className="px-4 py-3 max-w-xs truncate text-zinc-900 dark:text-zinc-100">
                      {run.prompt ?? "Automated Workflow Task"}
                    </td>

                    <td className="px-4 py-3">
                      <RunStatusBadge status={run.status} size="sm" />
                    </td>

                    <td className="px-4 py-3 text-zinc-500 dark:text-zinc-400">
                      {formatDate(run.startedAt ?? run.createdAt)}
                    </td>

                    <td className="px-4 py-3 text-zinc-500 dark:text-zinc-400 font-mono">
                      {formatDuration(run.durationSeconds)}
                    </td>

                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/runs/${run.id}`}
                        className="font-semibold text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 hover:underline"
                      >
                        View Evidence →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
