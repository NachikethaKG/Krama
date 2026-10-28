"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getApiClient } from "@/lib/api";
import type { RunListItem } from "@/lib/types";
import { RunListTable, RunPagination } from "@/components/runs";

const PAGE_SIZE = 20;

export default function RunsPage() {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  // cursors[i] is the cursor that loads page i + 1 (page 1 has none). GET /runs only gives `next_cursor`.
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cursor = cursors[cursors.length - 1];

  useEffect(() => {
    let isMounted = true;
    getApiClient()
      .getRuns({ limit: PAGE_SIZE, cursor })
      .then((res) => {
        if (!isMounted) return;
        setRuns(res.items);
        setNextCursor(res.nextCursor);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : String(err));
        setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [cursor, reloadKey]);

  const startLoading = () => {
    setIsLoading(true);
    setError(null);
  };

  const handleRefresh = useCallback(() => {
    startLoading();
    setReloadKey((k) => k + 1);
  }, []);

  const handleOlder = () => {
    if (!nextCursor) return;
    startLoading();
    setCursors((prev) => [...prev, nextCursor]);
  };

  const handleNewer = () => {
    if (cursors.length <= 1) return;
    startLoading();
    setCursors((prev) => prev.slice(0, -1));
  };

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">Runs</h1>
          <p className="mt-1 text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
            Every time Krama did a task for you, with what it checked at each step.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            data-testid="refresh-runs-button"
            onClick={handleRefresh}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-750 disabled:opacity-50 transition-colors"
          >
            <svg
              className={`size-3.5 ${isLoading ? "animate-spin" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
          <Link
            href="/dashboard/metrics"
            data-testid="nav-technical-metrics"
            className="px-3 py-1.5 text-xs font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
          >
            Benchmark metrics
          </Link>
        </div>
      </div>

      <RunListTable
        runs={runs}
        isLoading={isLoading}
        error={error}
      />

      {!isLoading && !error && runs.length > 0 && (
        <RunPagination
          page={cursors.length}
          pageSize={PAGE_SIZE}
          itemCount={runs.length}
          hasPrevious={cursors.length > 1}
          hasNext={nextCursor !== null}
          onPrevious={handleNewer}
          onNext={handleOlder}
          disabled={isLoading}
        />
      )}
    </main>
  );
}
