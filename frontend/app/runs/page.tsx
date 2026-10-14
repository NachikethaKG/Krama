"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getApiClient } from "@/lib/api";
import type { RunListItem } from "@/lib/types";
import { RunListTable, RunPagination } from "@/components/runs";

export default function RunsPage() {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(5);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const client = getApiClient();
    client
      .getRuns(page, pageSize)
      .then((res) => {
        if (isMounted) {
          setRuns(res.items);
          setTotal(res.total);
          setTotalPages(res.totalPages);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : String(err));
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [page, pageSize]);

  const handleRefresh = useCallback(() => {
    setIsLoading(true);
    setError(null);
    const client = getApiClient();
    client
      .getRuns(page, pageSize)
      .then((res) => {
        setRuns(res.items);
        setTotal(res.total);
        setTotalPages(res.totalPages);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : String(err));
        setIsLoading(false);
      });
  }, [page, pageSize]);

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400 mb-1">
            <Link href="/" className="hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors">
              Home
            </Link>
            <span>/</span>
            <span className="text-zinc-800 dark:text-zinc-200 font-medium">Runs</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Run History
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-zinc-600 dark:text-zinc-400">
            Inspect past workflow runs and review verification evidence layers for each executed step.
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
            href="/"
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white transition-colors"
          >
            New Workflow
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
          page={page}
          totalPages={totalPages}
          total={total}
          pageSize={pageSize}
          onPageChange={(newPage) => setPage(newPage)}
          disabled={isLoading}
        />
      )}
    </main>
  );
}
