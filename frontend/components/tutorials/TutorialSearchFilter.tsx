"use client";

import type { TutorialStatus } from "@/types/tutorial";

export interface StatusCounts {
  all: number;
  verified: number;
  outdated: number;
}

export interface TutorialSearchFilterProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  statusFilter: "all" | TutorialStatus;
  onStatusFilterChange: (status: "all" | TutorialStatus) => void;
  counts: StatusCounts;
}

export function TutorialSearchFilter({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  counts,
}: TutorialSearchFilterProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      {/* Search Bar */}
      <div className="relative flex-1 max-w-md">
        <label htmlFor="tutorial-search" className="sr-only">
          Search tutorials
        </label>
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-zinc-400">
          <svg
            className="size-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth="2"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
            />
          </svg>
        </div>
        <input
          id="tutorial-search"
          type="search"
          data-testid="tutorial-search-input"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search tutorials by title, description, or prompt..."
          className="w-full rounded-lg border border-zinc-200 bg-white py-2 pl-9 pr-9 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder:text-zinc-500"
        />
        {searchQuery ? (
          <button
            type="button"
            data-testid="tutorial-search-clear"
            onClick={() => onSearchChange("")}
            className="absolute inset-y-0 right-0 flex items-center pr-3 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
            aria-label="Clear search"
          >
            <svg
              className="size-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        ) : null}
      </div>

      {/* Status Filter Tabs / Pills */}
      <div
        role="tablist"
        aria-label="Filter by verification status"
        className="flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-zinc-100/70 p-1 dark:border-zinc-800 dark:bg-zinc-900/60"
      >
        <button
          type="button"
          role="tab"
          data-testid="filter-status-all"
          aria-selected={statusFilter === "all"}
          onClick={() => onStatusFilterChange("all")}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
            statusFilter === "all"
              ? "bg-white text-zinc-900 shadow-xs dark:bg-zinc-800 dark:text-zinc-100"
              : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
          }`}
        >
          <span>All</span>
          <span
            className={`rounded-full px-1.5 py-0.2 text-[10px] font-medium ${
              statusFilter === "all"
                ? "bg-zinc-100 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200"
                : "bg-zinc-200/70 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
            }`}
          >
            {counts.all}
          </span>
        </button>

        <button
          type="button"
          role="tab"
          data-testid="filter-status-verified"
          aria-selected={statusFilter === "verified"}
          onClick={() => onStatusFilterChange("verified")}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
            statusFilter === "verified"
              ? "bg-white text-emerald-700 shadow-xs dark:bg-zinc-800 dark:text-emerald-400"
              : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
          }`}
        >
          <span className="size-1.5 rounded-full bg-emerald-500" />
          <span>Verified</span>
          <span
            className={`rounded-full px-1.5 py-0.2 text-[10px] font-medium ${
              statusFilter === "verified"
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                : "bg-zinc-200/70 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
            }`}
          >
            {counts.verified}
          </span>
        </button>

        <button
          type="button"
          role="tab"
          data-testid="filter-status-outdated"
          aria-selected={statusFilter === "outdated"}
          onClick={() => onStatusFilterChange("outdated")}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-all ${
            statusFilter === "outdated"
              ? "bg-white text-amber-700 shadow-xs dark:bg-zinc-800 dark:text-amber-400"
              : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
          }`}
        >
          <span className="size-1.5 rounded-full bg-amber-500" />
          <span>Outdated</span>
          <span
            className={`rounded-full px-1.5 py-0.2 text-[10px] font-medium ${
              statusFilter === "outdated"
                ? "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300"
                : "bg-zinc-200/70 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
            }`}
          >
            {counts.outdated}
          </span>
        </button>
      </div>
    </div>
  );
}
