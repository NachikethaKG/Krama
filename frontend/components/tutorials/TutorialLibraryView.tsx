"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { type ApiClient, errorMessage, getApiClient } from "@/lib/api";
import type { TargetPlatform, TutorialStatus, TutorialSummary } from "@/types/tutorial";
import { TutorialCard } from "./TutorialCard";
import { TutorialSearchFilter } from "./TutorialSearchFilter";

/** Cards shown at first and added by each "Show more" (#318: the list used to render all of them at once). */
export const PAGE_SIZE = 12;

export interface TutorialLibraryViewProps {
  client?: ApiClient;
  initialTutorials?: TutorialSummary[];
}

export function TutorialLibraryView({
  client,
  initialTutorials,
}: TutorialLibraryViewProps) {
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [tutorials, setTutorials] = useState<TutorialSummary[] | null>(
    initialTutorials ?? null,
  );
  const [isLoading, setIsLoading] = useState<boolean>(!initialTutorials);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<"all" | TutorialStatus>("all");
  const [reloadKey, setReloadKey] = useState<number>(0);
  const [visible, setVisible] = useState<number>(PAGE_SIZE);

  useEffect(() => {
    if (initialTutorials) return;
    let isMounted = true;

    const fetchPromise =
      typeof apiClient.getTutorials === "function"
        ? apiClient.getTutorials({ status: "all" })
        : apiClient.getWorkflows(100, "all").then((page) =>
            page.items.map((w) => ({
              id: w.id,
              title: w.title,
              description: undefined,
              taskPrompt: w.title,
              target: (w.target_app === "github" ? "github" : w.target_app === "custom" ? "custom" : "gitea") as TargetPlatform,
              status: (w.status === "verified" ? "verified" : "outdated") as TutorialStatus,
              stepCount: w.step_count,
              durationMs: w.step_count * 18000,
              createdAt: w.created_at ?? new Date().toISOString(),
            })),
          );

    fetchPromise
      .then((items) => {
        if (!isMounted) return;
        setTutorials(items);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(errorMessage(err, "Failed to load tutorials. Please try again."));
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [apiClient, initialTutorials, reloadKey]);

  const handleRetry = useCallback(() => {
    setIsLoading(true);
    setError(null);
    setReloadKey((k) => k + 1);
  }, []);

  // Counts for status filter pills
  const counts = useMemo(() => {
    const list = tutorials ?? [];
    return {
      all: list.length,
      verified: list.filter((t) => t.status === "verified").length,
      outdated: list.filter((t) => t.status === "outdated").length,
    };
  }, [tutorials]);

  // Filtered tutorials based on search query, status filter, and optional target filter
  const filteredTutorials = useMemo(() => {
    if (!tutorials) return [];
    const q = searchQuery.trim().toLowerCase();

    return tutorials.filter((t) => {
      // Status filter
      if (statusFilter !== "all" && t.status !== statusFilter) {
        return false;
      }

      // Text search query across title, description, and task prompt
      if (q) {
        const matchTitle = t.title.toLowerCase().includes(q);
        const matchDesc = t.description?.toLowerCase().includes(q) ?? false;
        const matchPrompt = t.taskPrompt?.toLowerCase().includes(q) ?? false;
        const matchTarget = t.target.toLowerCase().includes(q);
        return matchTitle || matchDesc || matchPrompt || matchTarget;
      }

      return true;
    });
  }, [tutorials, searchQuery, statusFilter]);

  const hasActiveFilters = searchQuery.trim().length > 0 || statusFilter !== "all";

  const handleResetFilters = () => {
    setSearchQuery("");
    setStatusFilter("all");
    setVisible(PAGE_SIZE);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      {/* Header section */}
      <div className="flex flex-col gap-4 border-b border-zinc-200 pb-6 dark:border-zinc-800 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 sm:text-3xl">
            My tutorials
          </h1>
          <p className="mt-1.5 text-sm text-zinc-600 dark:text-zinc-400 max-w-2xl">
            Every task Krama did for you and checked step by step. Open one to watch it again.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 transition-colors"
          >
            <span>+ New tutorial</span>
          </Link>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="mt-6">
        <TutorialSearchFilter
          searchQuery={searchQuery}
          onSearchChange={(q) => {
            setSearchQuery(q);
            setVisible(PAGE_SIZE);
          }}
          statusFilter={statusFilter}
          onStatusFilterChange={(f) => {
            setStatusFilter(f);
            setVisible(PAGE_SIZE);
          }}
          counts={counts}
        />
      </div>

      {/* Error state */}
      {error ? (
        <div
          role="alert"
          data-testid="tutorials-error"
          className="mt-8 rounded-xl border border-rose-200 bg-rose-50 p-6 text-center dark:border-rose-900/50 dark:bg-rose-950/20"
        >
          <div className="mx-auto flex size-10 items-center justify-center rounded-full bg-rose-100 text-rose-600 dark:bg-rose-900/40 dark:text-rose-400">
            <svg
              className="size-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
              />
            </svg>
          </div>
          <h2 className="mt-3 text-sm font-semibold text-rose-900 dark:text-rose-200">
            Couldn&apos;t load your tutorials
          </h2>
          <p className="mt-1 text-xs text-rose-700 dark:text-rose-400">{error}</p>
          <button
            type="button"
            onClick={handleRetry}
            className="mt-4 inline-flex items-center gap-1.5 rounded-md border border-rose-300 bg-white px-3 py-1.5 text-xs font-medium text-rose-700 hover:bg-rose-100 dark:border-rose-800 dark:bg-zinc-900 dark:text-rose-300 dark:hover:bg-zinc-800 transition-colors"
          >
            Try again
          </button>
        </div>
      ) : null}

      {/* Loading state */}
      {isLoading ? (
        <div
          role="status"
          data-testid="tutorials-loading"
          className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3"
        >
          <span className="sr-only">Loading tutorials…</span>
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="flex flex-col justify-between rounded-xl border border-zinc-200 bg-white p-5 animate-pulse dark:border-zinc-800 dark:bg-zinc-950"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="h-5 w-16 rounded-full bg-zinc-200 dark:bg-zinc-800" />
                  <div className="h-5 w-20 rounded-full bg-zinc-200 dark:bg-zinc-800" />
                </div>
                <div className="h-5 w-4/5 rounded bg-zinc-200 dark:bg-zinc-800 mb-2" />
                <div className="h-4 w-full rounded bg-zinc-100 dark:bg-zinc-900 mb-1" />
                <div className="h-4 w-2/3 rounded bg-zinc-100 dark:bg-zinc-900" />
              </div>
              <div className="mt-6 pt-4 border-t border-zinc-100 dark:border-zinc-800/80">
                <div className="flex justify-between mb-3">
                  <div className="h-3 w-24 rounded bg-zinc-200 dark:bg-zinc-800" />
                  <div className="h-3 w-16 rounded bg-zinc-200 dark:bg-zinc-800" />
                </div>
                <div className="h-8 w-full rounded bg-zinc-200 dark:bg-zinc-800" />
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {/* Empty states */}
      {!isLoading && !error && filteredTutorials.length === 0 ? (
        <div
          data-testid="empty-tutorials"
          className="mt-12 rounded-xl border border-dashed border-zinc-300 p-12 text-center dark:border-zinc-800"
        >
          <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-zinc-100 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-500">
            <svg
              className="size-6 stroke-current fill-none stroke-2"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
          {hasActiveFilters ? (
            <>
              <h2 className="mt-4 text-base font-semibold text-zinc-900 dark:text-zinc-100">
                No tutorials match your search
              </h2>
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                Try other words, or clear the search to see all your tutorials.
              </p>
              <button
                type="button"
                data-testid="reset-filters-btn"
                onClick={handleResetFilters}
                className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-zinc-900 px-3.5 py-2 text-xs font-semibold text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 transition-colors"
              >
                Reset filters
              </button>
            </>
          ) : (
            <>
              <h2 className="mt-4 text-base font-semibold text-zinc-900 dark:text-zinc-100">
                No tutorials yet
              </h2>
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                Ask Krama for one, e.g. &ldquo;Show me how to create a GitHub repository&rdquo;.
              </p>
              <Link
                href="/"
                className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                New tutorial
              </Link>
            </>
          )}
        </div>
      ) : null}

      {/* Grid of Tutorial Cards */}
      {!isLoading && !error && filteredTutorials.length > 0 ? (
        <div className="mt-8">
          <div className="mb-4 flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
            <span>
              Showing {Math.min(visible, filteredTutorials.length)} of {filteredTutorials.length}{" "}
              {filteredTutorials.length === 1 ? "tutorial" : "tutorials"}
            </span>
          </div>

          <div
            data-testid="tutorial-grid"
            className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3"
          >
            {filteredTutorials.slice(0, visible).map((tutorial) => (
              <TutorialCard key={tutorial.id} tutorial={tutorial} />
            ))}
          </div>
          {visible < filteredTutorials.length && (
            <div className="mt-6 flex justify-center">
              <button
                type="button"
                data-testid="tutorials-show-more"
                onClick={() => setVisible((v) => v + PAGE_SIZE)}
                className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
              >
                Show more
              </button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
