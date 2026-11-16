"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getApiClient } from "@/lib/api";
import type { RunListItem } from "@/lib/types";
import { BarChart3, RefreshCw } from "lucide-react";
import { RunListTable, RunPagination } from "@/components/runs";
import { PageHero } from "@/components/ui";

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
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-10 sm:px-6">
      <PageHero
        stage="run"
        eyebrow="Run history"
        title="Runs"
        subtitle="Every time Krama did a task for you, with what it checked at each step."
        actions={
          <>
            <button
              type="button"
              data-testid="refresh-runs-button"
              onClick={handleRefresh}
              disabled={isLoading}
              className="kr-btn kr-btn-ghost kr-run px-4 py-2 text-xs"
            >
              <RefreshCw aria-hidden="true" className={`size-3.5 ${isLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
            <Link
              href="/dashboard/metrics"
              data-testid="nav-technical-metrics"
              className="kr-btn kr-btn-ghost kr-plan px-4 py-2 text-xs"
            >
              <BarChart3 aria-hidden="true" className="size-3.5 text-plan" />
              Benchmark metrics
            </Link>
          </>
        }
      />

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
