"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiClient, type ApiClient } from "@/lib/api";
import type { RunDetails } from "@/lib/types";
import { RunDetailHeader } from "./RunDetailHeader";
import { StepEvidenceCard } from "./StepEvidenceCard";

export interface RunDetailViewProps {
  runId: string;
  client?: ApiClient;
  initialDetails?: RunDetails;
  className?: string;
}

export function RunDetailView({
  runId,
  client,
  initialDetails,
  className = "",
}: RunDetailViewProps) {
  const [details, setDetails] = useState<RunDetails | null>(initialDetails ?? null);
  const [isLoading, setIsLoading] = useState(!initialDetails);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialDetails) return;

    let isMounted = true;

    const apiClient = client ?? getApiClient();
    apiClient
      .getRunDetails(runId)
      .then((data) => {
        if (isMounted) {
          setDetails(data);
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
  }, [runId, client, initialDetails]);

  if (isLoading) {
    return (
      <main className={`mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20 ${className}`}>
        <div
          data-testid="run-details-loading"
          className="flex flex-col items-center justify-center p-10 text-center"
        >
          <div className="size-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4" />
          <h2 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">
            Loading Run Verification Evidence…
          </h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Fetching step screenshots and multi-layer verification scores from artifact store
          </p>
        </div>
      </main>
    );
  }

  if (error || !details) {
    return (
      <main className={`mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-4 py-16 ${className}`}>
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
            {error || `The requested run "${runId}" does not exist or its execution artifacts were deleted.`}
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

  return (
    <main className={`mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-10 ${className}`}>
      <RunDetailHeader runDetails={details} />

      {(details.run.status === "queued" || details.run.status === "running" || details.run.status === "paused") && (
        <Link
          href={`/runs/${details.run.id}/live`}
          data-testid="run-live-link"
          className="self-start rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500"
        >
          Open the live view &rarr;
        </Link>
      )}

      {details.error && (
        <div
          role="alert"
          data-testid="run-error"
          className="rounded-xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-900 dark:border-rose-900/80 dark:bg-rose-950/40 dark:text-rose-200"
        >
          <span className="font-mono text-xs font-semibold uppercase">{details.error.code}</span> {details.error.message}
        </div>
      )}

      <section className="space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 pb-3">
          <div>
            <h2 className="text-base sm:text-lg font-bold text-zinc-900 dark:text-zinc-100">
              What Krama did and checked
            </h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Each step, how it was checked, and a screenshot of the page right after it.
            </p>
          </div>
          <span className="text-xs font-medium px-2.5 py-1 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
            {details.steps.length} {details.steps.length === 1 ? "Step" : "Steps"}
          </span>
        </div>

        {details.steps.length === 0 ? (
          <div
            data-testid="steps-empty-state"
            className="p-8 border border-dashed border-zinc-300 dark:border-zinc-700 rounded-xl bg-zinc-50 dark:bg-zinc-900/40 text-center text-xs text-zinc-500"
          >
            No steps executed for this workflow run yet.
          </div>
        ) : (
          <div data-testid="step-evidence-list" className="space-y-4">
            {details.steps.map((step, idx) => (
              <StepEvidenceCard
                key={step.id || `step-${step.seq || idx + 1}`}
                step={step}
                index={idx}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
