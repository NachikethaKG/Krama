"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Loader2, ShieldAlert } from "lucide-react";
import { type ApiClient, errorMessage, getApiClient } from "@/lib/api";
import { ReviewQueueFilterTabs, type ReviewQueueCounts } from "./ReviewQueueFilterTabs";
import { ReviewQueueItemCard } from "./ReviewQueueItemCard";
import type { ReviewFilterCategory, ReviewQueueItem } from "@/types/review";

export interface ReviewQueueViewProps {
  initialItems?: ReviewQueueItem[];
  client?: ApiClient;
  className?: string;
}

export function ReviewQueueView({
  initialItems,
  client,
  className = "",
}: ReviewQueueViewProps) {
  const router = useRouter();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [items, setItems] = useState<ReviewQueueItem[]>(() => initialItems ?? []);
  const [isLoading, setIsLoading] = useState<boolean>(!initialItems);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<ReviewFilterCategory>("all");
  const [inFlightIds, setInFlightIds] = useState<Set<string>>(new Set());
  const [quotaErrors, setQuotaErrors] = useState<Record<string, string>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    if (initialItems) return;

    let isMounted = true;
    apiClient
      .getReviewQueue()
      .then((data) => {
        if (!isMounted) return;
        setItems(data);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(errorMessage(err, "Failed to load review queue."));
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [apiClient, initialItems]);

  // Dismiss toast automatically after 5 seconds
  useEffect(() => {
    if (!toastMessage) return;
    const timer = setTimeout(() => setToastMessage(null), 5000);
    return () => clearTimeout(timer);
  }, [toastMessage]);

  const dispatchCountChange = (newCount: number) => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("krama:review-count-changed", { detail: { count: newCount } })
      );
    }
  };

  const counts: ReviewQueueCounts = useMemo(() => {
    return {
      all: items.length,
      outdated: items.filter((i) => i.category === "outdated").length,
      heal_pending: items.filter((i) => i.category === "heal_pending").length,
      unstable: items.filter((i) => i.category === "unstable").length,
      cant_check: items.filter((i) => i.category === "cant_check").length,
    };
  }, [items]);

  const filteredItems = useMemo(() => {
    if (selectedCategory === "all") return items;
    return items.filter((item) => item.category === selectedCategory);
  }, [items, selectedCategory]);

  const handleAccept = async (id: string) => {
    setInFlightIds((prev) => new Set(prev).add(id));
    try {
      await apiClient.acceptReview(id);
      const updated = items.filter((item) => item.id !== id);
      setItems(updated);
      dispatchCountChange(updated.length);
      setToastMessage("Healed version is now live");
    } catch (err) {
      setError(errorMessage(err, "Failed to accept healed version."));
    } finally {
      setInFlightIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleReject = async (id: string) => {
    setInFlightIds((prev) => new Set(prev).add(id));
    try {
      await apiClient.rejectReview(id);
      // D8: rejecting leaves the workflow in outdated state and decrements pending queue
      const updated = items.map((item) => {
        if (item.id === id) {
          return {
            ...item,
            category: "outdated" as const,
            reason: `Pending heal rejected. Workflow requires regeneration or replanning.`,
            pendingVersion: undefined,
            stepDiffs: undefined,
          };
        }
        return item;
      });
      setItems(updated);
      // Decrement pending heal count from active badge
      const activePendingCount = updated.filter((i) => i.category === "heal_pending").length;
      dispatchCountChange(activePendingCount);
      setToastMessage("Pending heal rejected. Workflow marked outdated.");
    } catch (err) {
      setError(errorMessage(err, "Failed to reject healed version."));
    } finally {
      setInFlightIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleRegenerate = async (workflowId: string) => {
    setInFlightIds((prev) => new Set(prev).add(workflowId));
    try {
      const res = await apiClient.regenerateWorkflow(workflowId);
      const newRunId = res.run_id || res.id;
      router.push(`/runs/${encodeURIComponent(newRunId)}`);
    } catch (err) {
      setError(errorMessage(err, "Failed to start workflow regeneration."));
      setInFlightIds((prev) => {
        const next = new Set(prev);
        next.delete(workflowId);
        return next;
      });
    }
  };

  const handleRetryAiFix = async (workflowId: string) => {
    setInFlightIds((prev) => new Set(prev).add(workflowId));
    setQuotaErrors((prev) => {
      const next = { ...prev };
      delete next[workflowId];
      return next;
    });

    try {
      await apiClient.retryAiFix(workflowId);
      setToastMessage("AI Fix initiated. Checking workflow in background...");
    } catch (err) {
      const msg = errorMessage(err, "Daily AI fix quota reached (5/day).");
      setQuotaErrors((prev) => ({
        ...prev,
        [workflowId]: msg.includes("quota")
          ? "Daily AI fix limit reached (5/day). Please regenerate the workflow or retry tomorrow."
          : msg,
      }));
    } finally {
      setInFlightIds((prev) => {
        const next = new Set(prev);
        next.delete(workflowId);
        return next;
      });
    }
  };

  const handleRetryCheck = async (workflowId: string) => {
    setInFlightIds((prev) => new Set(prev).add(workflowId));
    try {
      setToastMessage("Verification run scheduled for workflow.");
    } catch (err) {
      setError(errorMessage(err, "Failed to trigger retry check."));
    } finally {
      setInFlightIds((prev) => {
        const next = new Set(prev);
        next.delete(workflowId);
        return next;
      });
    }
  };

  return (
    <div data-testid="review-queue-view" className={`flex flex-col gap-8 ${className}`}>
      {/* Toast Notification */}
      {toastMessage && (
        <div
          data-testid="review-queue-toast"
          role="status"
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-2xl border border-emerald-500/40 bg-zinc-900/90 px-5 py-3 text-sm font-semibold text-emerald-400 shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-2 duration-200"
        >
          <CheckCircle2 className="size-5 text-emerald-400" aria-hidden="true" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header section */}
      <section className="flex flex-col gap-3">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="flex size-10 items-center justify-center rounded-2xl text-oncolor"
            style={{ background: "var(--plan)", boxShadow: "0 0 24px -4px var(--plan)" }}
          >
            <ShieldAlert className="size-5" />
          </span>
          <div>
            <h1 className="kr-display text-3xl font-extrabold text-white sm:text-4xl">
              Owner Review Queue
            </h1>
            <p className="mt-1 text-sm text-ink-300">
              Inspect and resolve workflows requiring human review, heal acceptance, or regeneration.
            </p>
          </div>
        </div>
      </section>

      {/* Category filter tabs */}
      <section>
        <ReviewQueueFilterTabs
          selectedCategory={selectedCategory}
          onSelectCategory={setSelectedCategory}
          counts={counts}
        />
      </section>

      {/* Error alert */}
      {error && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300"
        >
          <p>{error}</p>
        </div>
      )}

      {/* Loading state */}
      {isLoading ? (
        <div className="flex items-center justify-center p-12 text-sm text-ink-400">
          <Loader2 aria-hidden="true" className="mr-2 size-5 animate-spin text-purple-400" />
          <span>Loading review queue items…</span>
        </div>
      ) : items.length === 0 ? (
        /* Empty Queue Zero State */
        <div
          data-testid="review-queue-empty"
          className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-white/15 bg-white/[0.02] px-6 py-16 text-center"
        >
          <div className="flex size-14 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-400 mb-4">
            <CheckCircle2 className="size-7" aria-hidden="true" />
          </div>
          <h3 className="kr-display text-xl font-bold text-white">
            All tutorials are healthy — nothing needs review
          </h3>
          <p className="mt-2 max-w-md text-sm text-ink-300">
            No workflows currently have broken locators, outdated steps, or validation blocks.
          </p>
        </div>
      ) : filteredItems.length === 0 ? (
        /* Category Filter Zero State */
        <div
          data-testid="review-queue-filter-empty"
          className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-white/10 bg-white/[0.01] p-12 text-center text-sm text-ink-400"
        >
          <p>No review items match this category filter.</p>
        </div>
      ) : (
        /* List of Review Items */
        <div data-testid="review-queue-list" className="flex flex-col gap-4">
          {filteredItems.map((item) => (
            <ReviewQueueItemCard
              key={item.id}
              item={item}
              onAccept={handleAccept}
              onReject={handleReject}
              onRegenerate={handleRegenerate}
              onRetryAiFix={handleRetryAiFix}
              onRetryCheck={handleRetryCheck}
              isProcessing={inFlightIds.has(item.id) || inFlightIds.has(item.workflowId)}
              quotaError={quotaErrors[item.workflowId]}
            />
          ))}
        </div>
      )}
    </div>
  );
}
