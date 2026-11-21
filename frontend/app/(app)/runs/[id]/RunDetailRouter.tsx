"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
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
  const t = useTranslations("shell.runDetail");
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
          <div className="mb-4 size-12 animate-spin rounded-full border-4 border-white/10 border-t-run shadow-[0_0_30px_-4px_var(--run)]" />
          <h2 className="font-mono text-sm font-semibold text-run">
            {t("loading")}
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
          className="kr-danger kr-tone-card rounded-3xl p-8 text-center"
        >
          <div className="mx-auto mb-3 flex size-14 items-center justify-center rounded-2xl bg-danger text-oncolor shadow-[0_0_30px_-4px_var(--danger)]">
            <svg className="size-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="kr-display text-2xl font-extrabold text-white">
            {t("notFound")}
          </h2>
          <p className="text-xs sm:text-sm text-ink-400 mt-1 max-w-md mx-auto">
            {error || t("notFoundBody", { runId })}
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link
              href="/runs"
              data-testid="back-to-runs-button"
              className="kr-btn kr-btn-primary px-4 py-2 text-xs"
            >
              {t("backToRuns")}
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (activeTab === "evidence" && details) {
    return (
      <div>
        {/* A finished run has nothing live to show (#318) */}
        {["queued", "running", "paused"].includes(details.run.status) && (
          <div className="mx-auto flex max-w-5xl items-center justify-end px-4 pt-4 sm:px-6">
            <button
              type="button"
              data-testid="toggle-live-observer-btn"
              onClick={() => setActiveTab("live")}
              className="kr-btn kr-btn-tone kr-run px-4 py-1.5 text-xs"
            >
              {t("watchLive")}
            </button>
          </div>
        )}
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
            className="kr-btn kr-btn-ghost kr-verify px-4 py-1.5 text-xs"
          >
            {t("showChecks")}
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
