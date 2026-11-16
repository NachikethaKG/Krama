"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertTriangle, BookOpenText, ChevronDown, RotateCcw, SearchX } from "lucide-react";
import { PageHero } from "@/components/ui";
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
      <PageHero
        stage="learn"
        eyebrow="Your library"
        title="My tutorials"
        subtitle="Every task Krama did for you and checked step by step. Open one to watch it again."
        actions={
          <Link href="/" className="kr-btn kr-btn-primary px-4 py-2.5 text-xs">
            <span>+ New tutorial</span>
          </Link>
        }
      />

      {/* Search and Filters */}
      <div className="mt-10">
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
          className="kr-danger kr-tone-card mt-8 rounded-3xl p-8 text-center"
        >
          <div
            className="mx-auto flex size-12 items-center justify-center rounded-2xl text-oncolor"
            style={{ background: "var(--danger)", boxShadow: "0 0 30px -4px var(--danger)" }}
          >
            <AlertTriangle className="size-6" aria-hidden="true" />
          </div>
          <h2 className="kr-display mt-4 text-lg font-bold text-white">Couldn&apos;t load your tutorials</h2>
          <p className="mt-1 text-sm text-danger">{error}</p>
          <button
            type="button"
            onClick={handleRetry}
            className="kr-btn kr-btn-ghost kr-danger mt-5 px-4 py-2 text-xs"
          >
            <RotateCcw aria-hidden="true" className="size-3.5" />
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
              className="relative flex h-64 flex-col justify-between overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03] p-5"
            >
              <div
                aria-hidden="true"
                className="absolute inset-0 -translate-x-full animate-[kr-shimmer_1.6s_linear_infinite] bg-[linear-gradient(90deg,transparent,rgb(255_255_255/0.06),transparent)] bg-[length:200%_100%]"
              />
              <div>
                <div className="mb-4 flex items-center justify-between">
                  <div className="h-5 w-16 rounded-full bg-white/10" />
                  <div className="h-5 w-20 rounded-full bg-white/10" />
                </div>
                <div className="mb-2 h-5 w-4/5 rounded bg-white/10" />
                <div className="mb-1 h-4 w-full rounded bg-white/5" />
                <div className="h-4 w-2/3 rounded bg-white/5" />
              </div>
              <div className="h-9 w-full rounded-full bg-white/10" />
            </div>
          ))}
        </div>
      ) : null}

      {/* Empty states */}
      {!isLoading && !error && filteredTutorials.length === 0 ? (
        <div
          data-testid="empty-tutorials"
          className="mt-12 rounded-[2rem] border border-dashed border-white/15 bg-white/[0.02] p-12 text-center"
        >
          <div
            className="kr-float mx-auto flex size-16 items-center justify-center rounded-3xl text-oncolor"
            style={{
              background: "linear-gradient(135deg, var(--learn), var(--ask))",
              boxShadow: "0 0 40px -6px var(--learn)",
            }}
          >
            {hasActiveFilters ? (
              <SearchX className="size-7" aria-hidden="true" />
            ) : (
              <BookOpenText className="size-7" aria-hidden="true" />
            )}
          </div>
          {hasActiveFilters ? (
            <>
              <h2 className="kr-display mt-5 text-xl font-bold text-white">No tutorials match your search</h2>
              <p className="mt-1 text-sm text-ink-300">
                Try other words, or clear the search to see all your tutorials.
              </p>
              <button
                type="button"
                data-testid="reset-filters-btn"
                onClick={handleResetFilters}
                className="kr-btn kr-btn-ghost kr-learn mt-5 px-4 py-2 text-xs"
              >
                Reset filters
              </button>
            </>
          ) : (
            <>
              <h2 className="kr-display mt-5 text-xl font-bold text-white">No tutorials yet</h2>
              <p className="mt-1 text-sm text-ink-300">
                Ask Krama for one, e.g. &ldquo;Show me how to create a GitHub repository&rdquo;.
              </p>
              <Link href="/" className="kr-btn kr-btn-primary mt-5 px-5 py-2.5 text-xs">
                New tutorial
              </Link>
            </>
          )}
        </div>
      ) : null}

      {/* Grid of Tutorial Cards */}
      {!isLoading && !error && filteredTutorials.length > 0 ? (
        <div className="mt-8">
          <div className="mb-4 flex items-center gap-3 text-xs text-ink-400">
            <span>
              Showing {Math.min(visible, filteredTutorials.length)} of {filteredTutorials.length}{" "}
              {filteredTutorials.length === 1 ? "tutorial" : "tutorials"}
            </span>
            <span aria-hidden="true" className="h-px flex-1 bg-gradient-to-r from-learn/60 to-transparent" />
          </div>

          <div data-testid="tutorial-grid" className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {filteredTutorials.slice(0, visible).map((tutorial, i) => (
              <div key={tutorial.id} className="kr-rise" style={{ animationDelay: `${(i % PAGE_SIZE) * 50}ms` }}>
                <TutorialCard tutorial={tutorial} index={i} />
              </div>
            ))}
          </div>
          {visible < filteredTutorials.length && (
            <div className="mt-8 flex justify-center">
              <button
                type="button"
                data-testid="tutorials-show-more"
                onClick={() => setVisible((v) => v + PAGE_SIZE)}
                className="kr-btn kr-btn-ghost kr-learn px-5 py-2.5 text-sm"
              >
                Show more
                <ChevronDown aria-hidden="true" className="size-4" />
              </button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
