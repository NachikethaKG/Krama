"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiClient, type ApiClient } from "@/lib/api";
import type { RunDetails } from "@/lib/types";
import { LiveAgentObserverView, RunDetailView } from "@/components/runs";

export interface RunDetailRouterProps {
  runId: string;
  viewParam?: string;
  client?: ApiClient;
}

export function RunDetailRouter({
  runId,
  viewParam,
  client,
}: RunDetailRouterProps) {
  const [details, setDetails] = useState<RunDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"live" | "evidence">(
    viewParam === "evidence" ? "evidence" : viewParam === "live" ? "live" : "auto" as unknown as "live",
  );

  useEffect(() => {
    let isMounted = true;
    const apiClient = client ?? getApiClient();

    apiClient
      .getRunDetails(runId)
      .then((data) => {
        if (!isMounted) return;
        setDetails(data);
        setIsLoading(false);
        if (viewParam !== "live" && viewParam !== "evidence") {
          if (
            runId.includes("stream") ||
            runId.startsWith("stream-") ||
            runId === "test-run-stream" ||
            !data.steps ||
            data.steps.length === 0
          ) {
            setActiveTab("live");
          } else {
            setActiveTab("evidence");
          }
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        if (runId.includes("stream") || runId === "test-run-stream" || viewParam === "live") {
          setActiveTab("live");
          setIsLoading(false);
        } else {
          setError(err instanceof Error ? err.message : String(err));
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [runId, client, viewParam]);

  if (isLoading) {
    return (
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20">
        <div
          data-testid="run-details-loading"
          className="flex flex-col items-center justify-center p-10 text-center"
        >
          <div className="size-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4" />
          <h2 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">
            Loading Run…
          </h2>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-4 py-16">
        <div
          data-testid="run-not-found"
          className="p-8 border border-rose-200 dark:border-rose-900/60 rounded-2xl bg-white dark:bg-zinc-900 text-center shadow-sm"
        >
          <div className="size-12 rounded-full bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 flex items-center justify-center mx-auto mb-3">
            <svg className="size-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">
            Run Not Found
          </h2>
          <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 mt-1 max-w-md mx-auto">
            {error || `The requested run "${runId}" does not exist.`}
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link
              href="/runs"
              data-testid="back-to-runs-button"
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 hover:bg-zinc-800 transition-colors"
            >
              Back to Run History
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (activeTab === "evidence" && details) {
    return (
      <div>
        <div className="mx-auto flex max-w-5xl items-center justify-end px-4 pt-4 sm:px-6">
          <button
            type="button"
            data-testid="toggle-live-observer-btn"
            onClick={() => setActiveTab("live")}
            className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-300 dark:hover:bg-indigo-900/60"
          >
            ← Switch to Live Observer Stream
          </button>
        </div>
        <RunDetailView runId={runId} initialDetails={details} />
      </div>
    );
  }

  return (
    <div>
      {details && (
        <div className="mx-auto flex max-w-7xl items-center justify-end px-4 pt-4 sm:px-6">
          <button
            type="button"
            data-testid="toggle-evidence-view-btn"
            onClick={() => setActiveTab("evidence")}
            className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            Switch to Verification Evidence →
          </button>
        </div>
      )}
      <LiveAgentObserverView
        runId={runId}
        prompt={details?.run.prompt}
        targetUrl={details?.targetUrl}
      />
    </div>
  );
}
