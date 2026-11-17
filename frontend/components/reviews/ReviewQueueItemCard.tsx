"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  Clock,
  ExternalLink,
  GitBranch,
  KeyRound,
  RefreshCw,
  RotateCcw,
  Sparkles,
  X,
} from "lucide-react";
import { StepDiffViewer } from "@/components/versions/StepDiffViewer";
import type { ReviewQueueItem } from "@/types/review";

export interface ReviewQueueItemCardProps {
  item: ReviewQueueItem;
  onAccept?: (id: string) => Promise<void> | void;
  onReject?: (id: string) => Promise<void> | void;
  onRegenerate?: (workflowId: string) => Promise<void> | void;
  onRetryAiFix?: (workflowId: string) => Promise<void> | void;
  onRetryCheck?: (workflowId: string) => Promise<void> | void;
  isProcessing?: boolean;
  quotaError?: string | null;
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

export function ReviewQueueItemCard({
  item,
  onAccept,
  onReject,
  onRegenerate,
  onRetryAiFix,
  onRetryCheck,
  isProcessing = false,
  quotaError = null,
}: ReviewQueueItemCardProps) {
  const [isDiffExpanded, setIsDiffExpanded] = useState(item.category === "heal_pending");

  const renderCategoryBadge = () => {
    switch (item.category) {
      case "heal_pending":
        return (
          <span
            data-testid="category-badge"
            className="inline-flex items-center gap-1.5 rounded-full border border-purple-400/40 bg-purple-500/15 px-3 py-1 text-xs font-bold text-purple-300"
          >
            <Sparkles className="size-3.5 text-purple-400" aria-hidden="true" />
            <span>Heal Pending</span>
          </span>
        );
      case "outdated":
        return (
          <span
            data-testid="category-badge"
            className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/40 bg-amber-500/15 px-3 py-1 text-xs font-bold text-amber-300"
          >
            <AlertTriangle className="size-3.5 text-amber-400" aria-hidden="true" />
            <span>Outdated</span>
          </span>
        );
      case "unstable":
        return (
          <span
            data-testid="category-badge"
            className="inline-flex items-center gap-1.5 rounded-full border border-orange-400/40 bg-orange-500/15 px-3 py-1 text-xs font-bold text-orange-300"
          >
            <RotateCcw className="size-3.5 text-orange-400" aria-hidden="true" />
            <span>Unstable</span>
          </span>
        );
      case "cant_check":
      default:
        return (
          <span
            data-testid="category-badge"
            data-testid-cant-check="true"
            className="inline-flex items-center gap-1.5 rounded-full border border-rose-400/40 bg-rose-500/15 px-3 py-1 text-xs font-bold text-rose-300"
          >
            <AlertTriangle className="size-3.5 text-rose-400" aria-hidden="true" />
            <span data-testid="category-cant_check">Can&apos;t check: {item.reason}</span>
          </span>
        );
    }
  };

  const isSessionExpired =
    item.category === "cant_check" &&
    (item.reason.toLowerCase().includes("session") || item.targetPlatform === "github");

  return (
    <article
      data-testid="review-queue-card"
      data-item-id={item.id}
      data-category={item.category}
      className="kr-tone-card relative flex flex-col justify-between overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-5 shadow-lg transition-all hover:border-white/20"
    >
      {/* Top Header */}
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/10 pb-4">
        <div className="flex flex-1 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span
              data-testid="target-platform-badge"
              className="inline-flex items-center gap-1 rounded-md border border-white/15 bg-white/5 px-2 py-0.5 text-[11px] font-semibold uppercase text-ink-300"
            >
              <GitBranch className="size-3" aria-hidden="true" />
              {item.targetPlatform}
            </span>
            {renderCategoryBadge()}
          </div>
          <h3 data-testid="workflow-title" className="kr-display text-lg font-bold text-white">
            <Link
              href={`/tutorials/${item.workflowId}`}
              className="hover:text-purple-300 transition-colors inline-flex items-center gap-1.5"
            >
              <span>{item.workflowTitle}</span>
              <ArrowUpRight className="size-4 opacity-50" aria-hidden="true" />
            </Link>
          </h3>
        </div>

        <div
          data-testid="item-timestamp"
          className="flex items-center gap-1 text-xs text-ink-400"
        >
          <Clock className="size-3.5" aria-hidden="true" />
          <span>{formatDate(item.createdAt)}</span>
        </div>
      </div>

      {/* Middle Body / Description */}
      <div className="my-4 flex flex-col gap-3">
        <div className="rounded-xl border border-white/5 bg-white/[0.02] p-3 text-sm text-ink-200">
          <span className="font-semibold text-white">Trigger reason: </span>
          <span data-testid="review-reason">{item.reason}</span>
          {item.failedStepIndex !== undefined && (
            <span className="ml-2 font-mono text-xs text-ink-400">
              (Step {item.failedStepIndex})
            </span>
          )}
        </div>

        {/* Step Diff Disclosure for heal_pending */}
        {item.category === "heal_pending" && (
          <div className="flex flex-col gap-2">
            <button
              type="button"
              data-testid="inspect-diff-btn"
              onClick={() => setIsDiffExpanded((prev) => !prev)}
              className="flex w-fit items-center gap-1.5 text-xs font-bold text-purple-300 hover:text-white transition-colors"
            >
              <span>{isDiffExpanded ? "Hide Step-by-Step Diff" : "Inspect Step-by-Step Diff"}</span>
              <span className="text-[10px]">{isDiffExpanded ? "▲" : "▼"}</span>
            </button>

            {isDiffExpanded && (
              <div
                data-testid="review-step-diff-wrapper"
                className="mt-1 rounded-xl border border-purple-500/20 bg-purple-950/10 p-3"
              >
                <StepDiffViewer
                  diffs={item.stepDiffs ?? []}
                  fromVersion="v1.0"
                  toVersion={item.pendingVersion ?? "v1.1"}
                  changeSummary={item.reason}
                />
              </div>
            )}
          </div>
        )}

        {/* Quota Exhausted Notice */}
        {quotaError && (
          <div
            data-testid="quota-exhausted-notice"
            role="alert"
            className="flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300"
          >
            <AlertTriangle className="size-4 shrink-0 text-amber-400" aria-hidden="true" />
            <span>{quotaError}</span>
          </div>
        )}
      </div>

      {/* Card Actions Bottom */}
      <div
        data-testid="card-actions"
        className="flex flex-wrap items-center justify-end gap-2.5 border-t border-white/10 pt-4"
      >
        {item.category === "heal_pending" && (
          <>
            <button
              type="button"
              data-testid="action-reject"
              disabled={isProcessing}
              onClick={() => onReject?.(item.id)}
              className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/40 bg-rose-500/10 px-4 py-2 text-xs font-bold text-rose-300 hover:bg-rose-500/20 disabled:opacity-50 transition-colors"
            >
              <X className="size-3.5" aria-hidden="true" />
              <span>Reject</span>
            </button>

            <button
              type="button"
              data-testid="action-accept"
              disabled={isProcessing}
              onClick={() => onAccept?.(item.id)}
              className="inline-flex items-center gap-1.5 rounded-full bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow-md hover:bg-emerald-500 disabled:opacity-50 transition-all"
            >
              <Check className="size-3.5" aria-hidden="true" />
              <span>Accept</span>
            </button>
          </>
        )}

        {(item.category === "outdated" || item.category === "unstable") && (
          <>
            {item.canRetryAiFix !== false && (
              <button
                type="button"
                data-testid="action-retry-ai-fix"
                disabled={isProcessing}
                onClick={() => onRetryAiFix?.(item.workflowId)}
                className="inline-flex items-center gap-1.5 rounded-full border border-sky-400/40 bg-sky-500/10 px-4 py-2 text-xs font-bold text-sky-300 hover:bg-sky-500/20 disabled:opacity-50 transition-colors"
              >
                <Sparkles className="size-3.5 text-sky-400" aria-hidden="true" />
                <span>Retry AI Fix</span>
              </button>
            )}

            <button
              type="button"
              data-testid="action-regenerate"
              disabled={isProcessing}
              onClick={() => onRegenerate?.(item.workflowId)}
              className="inline-flex items-center gap-1.5 rounded-full bg-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-md hover:bg-indigo-500 disabled:opacity-50 transition-all"
            >
              <RefreshCw className={`size-3.5 ${isProcessing ? "animate-spin" : ""}`} aria-hidden="true" />
              <span>Regenerate</span>
            </button>
          </>
        )}

        {item.category === "cant_check" && (
          <>
            {isSessionExpired && (
              <Link
                href="/runs/new?target=github"
                data-testid="action-reauth"
                className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/40 bg-amber-500/10 px-4 py-2 text-xs font-bold text-amber-300 hover:bg-amber-500/20 transition-colors"
              >
                <KeyRound className="size-3.5" aria-hidden="true" />
                <span>Re-authenticate Session</span>
                <ExternalLink className="size-3 opacity-60" aria-hidden="true" />
              </Link>
            )}

            <button
              type="button"
              data-testid="action-retry-check"
              disabled={isProcessing}
              onClick={() => onRetryCheck?.(item.workflowId)}
              className="inline-flex items-center gap-1.5 rounded-full bg-white/10 px-4 py-2 text-xs font-bold text-white hover:bg-white/20 disabled:opacity-50 transition-colors"
            >
              <RotateCcw className={`size-3.5 ${isProcessing ? "animate-spin" : ""}`} aria-hidden="true" />
              <span>Retry Check</span>
            </button>
          </>
        )}
      </div>
    </article>
  );
}
