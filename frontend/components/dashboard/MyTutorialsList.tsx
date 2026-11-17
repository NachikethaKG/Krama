"use client";

import React, { useEffect, useState } from "react";
import { type ApiClient, errorMessage, getApiClient } from "@/lib/api";
import { TutorialCard } from "@/components/tutorials/TutorialCard";
import { TutorialStatusBadge } from "@/components/tutorials/TutorialStatusBadge";
import { StepDiffViewer } from "@/components/versions/StepDiffViewer";
import type { TutorialSummary, WorkflowVersionRecord } from "@/types/tutorial";

export interface MyTutorialsListProps {
  tutorials?: TutorialSummary[];
  client?: ApiClient;
  onInspectDiff?: (tutorial: TutorialSummary) => void;
  className?: string;
}

export function MyTutorialsList({
  tutorials: initialTutorials,
  client,
  onInspectDiff,
  className = "",
}: MyTutorialsListProps) {
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [fetchedTutorials, setFetchedTutorials] = useState<TutorialSummary[] | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(!initialTutorials);
  const [error, setError] = useState<string | null>(null);

  const tutorialList = initialTutorials ?? fetchedTutorials;

  // Active diff preview for auto-updated tutorials
  const [diffPreviewTutorial, setDiffPreviewTutorial] = useState<TutorialSummary | null>(null);
  const [diffVersions, setDiffVersions] = useState<WorkflowVersionRecord | null>(null);
  const [isDiffLoading, setIsDiffLoading] = useState<boolean>(false);

  useEffect(() => {
    if (initialTutorials) return;

    let isMounted = true;

    apiClient
      .getTutorials({ status: "all" })
      .then((items) => {
        if (!isMounted) return;
        setFetchedTutorials(items);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(errorMessage(err, "Failed to load tutorials."));
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [apiClient, initialTutorials]);

  const handleInspectDiff = (tutorial: TutorialSummary) => {
    if (onInspectDiff) {
      onInspectDiff(tutorial);
      return;
    }

    setDiffPreviewTutorial(tutorial);
    setIsDiffLoading(true);

    apiClient
      .getWorkflowVersions(tutorial.id)
      .then((res) => {
        const autoUpdatedVer = res.items.find(
          (v) => v.source === "heal" || v.status === "current"
        );
        if (autoUpdatedVer && autoUpdatedVer.change_summary) {
          // Import parser dynamically or use normalized
          import("@/components/versions/version-utils").then(({ normalizeVersionRecord }) => {
            setDiffVersions(normalizeVersionRecord(autoUpdatedVer));
            setIsDiffLoading(false);
          });
        } else {
          setDiffVersions(null);
          setIsDiffLoading(false);
        }
      })
      .catch(() => {
        setDiffVersions(null);
        setIsDiffLoading(false);
      });
  };

  if (isLoading) {
    return (
      <div
        data-testid="my-tutorials-list"
        className={`flex flex-col items-center justify-center p-8 text-center text-sm text-zinc-500 dark:text-zinc-400 ${className}`}
      >
        <div className="size-6 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin mb-2" />
        <span>Loading your tutorials…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="my-tutorials-list"
        className={`rounded-xl border border-rose-200 bg-rose-50/60 p-6 text-sm text-rose-700 dark:border-rose-900/60 dark:bg-rose-950/20 dark:text-rose-400 ${className}`}
      >
        <p>{error}</p>
      </div>
    );
  }

  if (!tutorialList || tutorialList.length === 0) {
    return (
      <div
        data-testid="my-tutorials-list"
        className={`rounded-xl border border-dashed border-zinc-200 bg-zinc-50/50 p-8 text-center dark:border-zinc-800 dark:bg-zinc-900/30 ${className}`}
      >
        <p data-testid="empty-my-tutorials" className="text-sm text-zinc-500 dark:text-zinc-400">
          No tutorials recorded yet. Create a new task to generate your first tutorial.
        </p>
      </div>
    );
  }

  return (
    <div data-testid="my-tutorials-list" className={`flex flex-col gap-6 ${className}`}>
      {/* Grid of Tutorial Cards */}
      <div data-testid="home-recent-tutorials" className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {tutorialList.map((tutorial, i) => (
          <div key={tutorial.id} className="kr-rise" style={{ animationDelay: `${i * 70}ms` }}>
            <TutorialCard
              tutorial={tutorial}
              index={i}
              onInspectDiff={() => handleInspectDiff(tutorial)}
            />
          </div>
        ))}
      </div>

      {/* Diff Preview Modal */}
      {diffPreviewTutorial && (
        <div
          data-testid="dashboard-diff-modal"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
        >
          <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl dark:bg-zinc-950 overflow-hidden border border-zinc-200 dark:border-zinc-800">
            <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
              <div>
                <h4 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                  Step Diff: {diffPreviewTutorial.title}
                </h4>
                <div className="mt-1 flex items-center gap-2">
                  <TutorialStatusBadge status={diffPreviewTutorial.status} size="sm" />
                </div>
              </div>
              <button
                type="button"
                data-testid="close-dashboard-diff-modal"
                onClick={() => {
                  setDiffPreviewTutorial(null);
                  setDiffVersions(null);
                }}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                aria-label="Close diff preview"
              >
                <svg className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              {isDiffLoading ? (
                <div className="py-12 text-center text-sm text-zinc-500">
                  Loading step differences…
                </div>
              ) : diffVersions && diffVersions.stepDiffs.length > 0 ? (
                <StepDiffViewer
                  diffs={diffVersions.stepDiffs}
                  fromVersion="v1.0"
                  toVersion={diffVersions.version}
                  changeSummary={diffVersions.changeSummary}
                />
              ) : (
                <p className="py-8 text-center text-xs text-zinc-500">
                  No step diff available for this tutorial.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
