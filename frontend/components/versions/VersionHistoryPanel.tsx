"use client";

import React, { useEffect, useMemo, useState } from "react";
import type { WorkflowVersion } from "@krama/contracts-ts";
import { type ApiClient, errorMessage, getApiClient } from "@/lib/api";
import type { WorkflowVersionRecord } from "@/types/tutorial";
import { StepDiffViewer } from "./StepDiffViewer";
import { normalizeVersionRecord } from "./version-utils";

export interface VersionHistoryPanelProps {
  workflowId?: string;
  versions?: (WorkflowVersion | WorkflowVersionRecord)[];
  activeVersionId?: string;
  onSelectVersion?: (versionId: string) => void;
  onInspectDiff?: (version: WorkflowVersionRecord) => void;
  className?: string;
  apiClient?: ApiClient;
  readOnly?: boolean;
}

export function VersionHistoryPanel({
  workflowId,
  versions: initialVersions,
  activeVersionId,
  onSelectVersion,
  onInspectDiff,
  className = "",
  apiClient,
  readOnly = false,
}: VersionHistoryPanelProps) {
  const [client] = useState<ApiClient>(() => apiClient ?? getApiClient());
  const [fetchedVersions, setFetchedVersions] = useState<WorkflowVersionRecord[] | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(!initialVersions && !!workflowId);
  const [error, setError] = useState<string | null>(null);

  const versionList = useMemo(() => {
    if (initialVersions) {
      return initialVersions.map(normalizeVersionRecord);
    }
    return fetchedVersions;
  }, [initialVersions, fetchedVersions]);

  // Wording-only versions collapsed by default (D11)
  const [showWordingChanges, setShowWordingChanges] = useState<boolean>(false);

  // Selected version for inline step diff preview
  const [inspectingVersion, setInspectingVersion] = useState<WorkflowVersionRecord | null>(null);

  useEffect(() => {
    if (initialVersions || !workflowId) {
      return;
    }

    let isMounted = true;

    // Call API: GET /api/v1/workflows/{id}/versions
    client
      .getWorkflowVersions(workflowId)
      .then((res) => {
        if (!isMounted) return;
        const normalized = res.items.map(normalizeVersionRecord);
        setFetchedVersions(normalized);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(errorMessage(err, "Failed to load version history."));
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [workflowId, initialVersions, client]);

  // D8 & D11: Segregate active/viewer-playable versions, pending review, and wording-only
  const { structuralVersions, wordingVersions, pendingReviewVersions, isBaselineOnly } =
    useMemo(() => {
      if (!versionList || versionList.length === 0) {
        return {
          structuralVersions: [],
          wordingVersions: [],
          pendingReviewVersions: [],
          isBaselineOnly: true,
        };
      }

      // Filter out heal_pending / pending_review from active playback selection (D8)
      const pending: WorkflowVersionRecord[] = [];
      const playable: WorkflowVersionRecord[] = [];

      for (const v of versionList) {
        if (v.status === "heal_pending" || v.status === "pending_review") {
          pending.push(v);
        } else {
          playable.push(v);
        }
      }

      const wording = playable.filter((v) => v.isWordingOnly);
      const structural = playable.filter((v) => !v.isWordingOnly);

      const baselineOnly =
        playable.length === 1 &&
        (playable[0].stepDiffs.length === 0 || playable[0].version === "v1.0");

      return {
        structuralVersions: structural,
        wordingVersions: wording,
        pendingReviewVersions: pending,
        isBaselineOnly: baselineOnly,
      };
    }, [versionList]);

  const handleInspectDiff = (version: WorkflowVersionRecord) => {
    setInspectingVersion(version);
    if (onInspectDiff) {
      onInspectDiff(version);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div
        data-testid="version-history-panel"
        className={`flex flex-col items-center justify-center rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950 ${className}`}
      >
        <div
          data-testid="version-history-loading"
          className="flex flex-col items-center gap-3 text-sm text-zinc-500 dark:text-zinc-400"
        >
          <div className="size-6 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin" />
          <span>Loading version history…</span>
        </div>
      </div>
    );
  }

  // Graceful error state (does not crash player)
  if (error) {
    return (
      <div
        data-testid="version-history-panel"
        className={`rounded-xl border border-rose-200 bg-rose-50/50 p-6 text-sm dark:border-rose-900/60 dark:bg-rose-950/20 ${className}`}
      >
        <div data-testid="version-history-error" className="flex flex-col gap-2">
          <div className="flex items-center gap-2 text-rose-700 dark:text-rose-400 font-semibold">
            <svg
              className="size-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <span>Unable to load version history</span>
          </div>
          <p className="text-xs text-rose-600 dark:text-rose-300">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="version-history-panel"
      className={`flex flex-col gap-5 rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950 ${className}`}
    >
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-zinc-100 pb-3 dark:border-zinc-900">
        <div className="flex items-center gap-2">
          <svg
            className="size-4 text-zinc-500 dark:text-zinc-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
            Version History
          </h3>
        </div>
        {versionList && (
          <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
            {versionList.length} {versionList.length === 1 ? "version" : "versions"}
          </span>
        )}
      </div>

      {/* Baseline only: clean state without broken diff controls */}
      {isBaselineOnly && (
        <div
          data-testid="version-history-baseline"
          className="rounded-lg border border-dashed border-zinc-200 bg-zinc-50/70 p-4 text-xs text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-400"
        >
          <p className="font-semibold text-zinc-900 dark:text-zinc-200">
            Baseline version (v1.0)
          </p>
          <p className="mt-1 text-zinc-500 dark:text-zinc-400">
            This is the initial recorded version. No prior revisions or healed step deltas exist.
          </p>
        </div>
      )}

      {/* Active & Healed Versions List */}
      <div className="flex flex-col gap-3" data-testid="version-records-list">
        {structuralVersions.map((ver) => {
          const isActive = ver.id === activeVersionId;
          const isAutoUpdated = ver.status === "auto-updated";

          return (
            <div
              key={ver.id}
              data-testid="version-item"
              data-version={ver.version}
              className={`flex flex-col gap-2 rounded-lg border p-3.5 transition-all ${
                isActive
                  ? "border-indigo-400 bg-indigo-50/20 shadow-xs dark:border-indigo-600 dark:bg-indigo-950/20"
                  : "border-zinc-200 bg-white hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-900/50"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-bold text-zinc-900 dark:text-zinc-100">
                    {ver.version}
                  </span>
                  {isAutoUpdated ? (
                    <span
                      data-testid="version-auto-updated-badge"
                      className="inline-flex items-center gap-1 rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-800 dark:bg-sky-900/60 dark:text-sky-200"
                    >
                      <span className="size-1.5 rounded-full bg-sky-500" />
                      Auto-Updated
                    </span>
                  ) : isActive ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-200">
                      Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                      Archived
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {onSelectVersion && !isActive && !readOnly && (
                    <button
                      type="button"
                      data-testid="select-version-btn"
                      onClick={() => onSelectVersion(ver.id)}
                      className="rounded px-2 py-1 text-xs font-semibold text-indigo-600 hover:bg-indigo-50 dark:text-indigo-400 dark:hover:bg-indigo-950/50 transition-colors"
                    >
                      Switch to {ver.version}
                    </button>
                  )}
                  {ver.stepDiffs.length > 0 && (
                    <button
                      type="button"
                      data-testid="view-diff-btn"
                      onClick={() => handleInspectDiff(ver)}
                      className="inline-flex items-center gap-1 rounded border border-zinc-200 bg-zinc-50 px-2.5 py-1 text-xs font-semibold text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700 transition-colors"
                    >
                      Inspect Step Diff
                    </button>
                  )}
                </div>
              </div>

              {/* Stored change summary */}
              <p
                data-testid="version-change-summary"
                className="text-xs text-zinc-600 dark:text-zinc-300 leading-relaxed"
              >
                {ver.changeSummary}
              </p>
            </div>
          );
        })}
      </div>

      {/* Wording-only changes (D11: Collapsed by default behind a disclosure toggle) */}
      {wordingVersions.length > 0 && (
        <div
          data-testid="wording-changes-section"
          className="border-t border-zinc-100 pt-3 dark:border-zinc-900"
        >
          <button
            type="button"
            data-testid="toggle-wording-changes"
            onClick={() => setShowWordingChanges((prev) => !prev)}
            aria-expanded={showWordingChanges}
            className="flex w-full items-center justify-between rounded-lg bg-zinc-50 px-3 py-2 text-xs font-semibold text-zinc-700 hover:bg-zinc-100 dark:bg-zinc-900/60 dark:text-zinc-300 dark:hover:bg-zinc-900 transition-colors"
          >
            <div className="flex items-center gap-1.5">
              <span>Wording-only changes ({wordingVersions.length})</span>
              <span className="text-[10px] text-zinc-400 font-normal">
                (captions & descriptions)
              </span>
            </div>
            <span className="text-zinc-400 text-xs">
              {showWordingChanges ? "▲ Hide" : "▼ Show"}
            </span>
          </button>

          {showWordingChanges && (
            <div
              data-testid="wording-versions-list"
              className="mt-3 flex flex-col gap-2 pl-2 border-l-2 border-zinc-200 dark:border-zinc-800"
            >
              {wordingVersions.map((wVer) => (
                <div
                  key={wVer.id}
                  data-testid="wording-version-item"
                  data-version={wVer.version}
                  className="flex flex-col gap-1 rounded border border-zinc-100 bg-white p-3 text-xs dark:border-zinc-900 dark:bg-zinc-950"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono font-bold text-zinc-800 dark:text-zinc-200">
                      {wVer.version}
                    </span>
                    {wVer.stepDiffs.length > 0 && (
                      <button
                        type="button"
                        data-testid="view-wording-diff-btn"
                        onClick={() => handleInspectDiff(wVer)}
                        className="text-[11px] font-semibold text-indigo-600 hover:underline dark:text-indigo-400"
                      >
                        View diff
                      </button>
                    )}
                  </div>
                  <p className="text-zinc-500 dark:text-zinc-400">
                    {wVer.changeSummary}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* D8: Versions in heal_pending / pending_review (Never shown as current active version to viewers) */}
      {pendingReviewVersions.length > 0 && (
        <div
          data-testid="pending-review-section"
          className="border-t border-amber-200/60 pt-3 dark:border-amber-900/50"
        >
          <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3.5 text-xs text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/30 dark:text-amber-200">
            <div className="flex items-center gap-2 font-semibold">
              <span className="size-2 rounded-full bg-amber-500 animate-pulse" />
              <span>Pending Review ({pendingReviewVersions.length})</span>
            </div>
            <p className="mt-1 text-[11px] text-amber-800 dark:text-amber-300/90">
              Healed versions awaiting creator confirmation in the Review Queue. They are locked from viewer playback until accepted.
            </p>
            <div className="mt-3 flex flex-col gap-2">
              {pendingReviewVersions.map((pVer) => (
                <div
                  key={pVer.id}
                  data-testid="pending-version-item"
                  className="flex items-center justify-between rounded border border-amber-300/80 bg-white/80 px-3 py-2 text-xs dark:border-amber-800/80 dark:bg-zinc-900"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold">{pVer.version}</span>
                    <span
                      data-testid="pending-review-badge"
                      className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-800 dark:bg-amber-900/60 dark:text-amber-200"
                    >
                      Locked (Pending Review)
                    </span>
                  </div>
                  {pVer.stepDiffs.length > 0 && (
                    <button
                      type="button"
                      data-testid="inspect-pending-diff-btn"
                      onClick={() => handleInspectDiff(pVer)}
                      className="text-xs font-semibold text-amber-900 underline hover:no-underline dark:text-amber-200"
                    >
                      Review diff
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Inline step diff modal / drawer preview when user clicked Inspect Step Diff */}
      {inspectingVersion && (
        <div
          data-testid="inspect-diff-modal"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs"
        >
          <div className="flex max-h-[85vh] w-full max-w-2xl flex-col rounded-2xl bg-white shadow-2xl dark:bg-zinc-950 overflow-hidden border border-zinc-200 dark:border-zinc-800">
            <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
              <h4 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
                Step-by-Step Diff ({inspectingVersion.version})
              </h4>
              <button
                type="button"
                data-testid="close-diff-modal-btn"
                onClick={() => setInspectingVersion(null)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
                aria-label="Close diff preview"
              >
                <svg className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <StepDiffViewer
                diffs={inspectingVersion.stepDiffs}
                fromVersion="v1.0"
                toVersion={inspectingVersion.version}
                changeSummary={inspectingVersion.changeSummary}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
