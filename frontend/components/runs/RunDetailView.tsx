"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
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
  const t = useTranslations("runs");
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
          <div className="mb-4 size-12 animate-spin rounded-full border-4 border-white/10 border-t-verify shadow-[0_0_30px_-4px_var(--verify)]" />
          <h2 className="text-base font-semibold text-ink-300">
            {t("detailView.loading")}
          </h2>
          <p className="text-xs text-ink-400 mt-1">
            {t("detailView.loadingHint")}
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
          className="kr-danger kr-tone-card rounded-3xl p-8 text-center"
        >
          <div className="mx-auto mb-3 flex size-14 items-center justify-center rounded-2xl bg-danger text-oncolor shadow-[0_0_30px_-4px_var(--danger)]">
            <svg className="size-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="kr-display text-2xl font-extrabold text-white">
            {t("detailView.notFound")}
          </h2>
          <p className="text-xs sm:text-sm text-ink-400 mt-1 max-w-md mx-auto">
            {error || t("detailView.notFoundBody", { runId })}
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link
              href="/runs"
              data-testid="back-to-runs-button"
              className="kr-btn kr-btn-ghost px-4 py-2 text-xs"
            >
              {t("detailView.backToRuns")}
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
          className="kr-btn kr-btn-primary self-start px-4 py-1.5 text-xs"
        >
          {t("detailView.openLive")} →
        </Link>
      )}

      {details.error && (
        <div
          role="alert"
          data-testid="run-error"
          className="kr-danger kr-tone-card rounded-2xl p-4 text-sm text-danger"
        >
          <span className="font-mono text-xs font-semibold uppercase">{details.error.code}</span> {details.error.message}
        </div>
      )}

      <section className="space-y-4">
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div>
            <h2 className="kr-display text-2xl font-extrabold text-white sm:text-3xl">
              {t.rich("detailView.title", {
                em: (chunks) => <span className="kr-gradient-text">{chunks}</span>,
              })}
            </h2>
            <p className="text-xs text-ink-400">
              {t("detailView.subtitle")}
            </p>
          </div>
          <span className="kr-chip kr-verify">
            {t("detailView.stepCount", { count: details.steps.length })}
          </span>
        </div>

        {details.steps.length === 0 ? (
          <div
            data-testid="steps-empty-state"
            className="rounded-3xl border border-dashed border-white/15 bg-ink-900/40 p-8 text-center text-xs text-ink-400"
          >
            {t("detailView.noSteps")}
          </div>
        ) : (
          <div data-testid="step-evidence-list" className="relative space-y-4">
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
