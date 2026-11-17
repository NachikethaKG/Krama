"use client";

import { Search, X } from "lucide-react";
import type { TutorialStatus } from "@/types/tutorial";

export interface StatusCounts {
  all: number;
  verified: number;
  outdated: number;
  autoUpdated?: number;
  notAutoChecked?: number;
}

export interface TutorialSearchFilterProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  statusFilter: "all" | TutorialStatus;
  onStatusFilterChange: (status: "all" | TutorialStatus) => void;
  counts: StatusCounts;
}

/** One filter tab: its own colour, solid and glowing when selected. */
function FilterTab({
  testId,
  selected,
  color,
  label,
  count,
  onClick,
}: {
  testId: string;
  selected: boolean;
  color: string;
  label: string;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="tab"
      data-testid={testId}
      aria-selected={selected}
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-bold transition-all ${
        selected ? "text-oncolor" : "text-ink-300 hover:text-white"
      }`}
      style={selected ? { background: color, boxShadow: `0 0 20px -4px ${color}` } : undefined}
    >
      {!selected && <span aria-hidden="true" className="size-1.5 rounded-full" style={{ background: color }} />}
      <span>{label}</span>
      <span
        className={`rounded-full px-1.5 text-[10px] font-extrabold ${
          selected ? "bg-ink-950/20 text-oncolor" : "bg-white/10 text-ink-300"
        }`}
      >
        {count}
      </span>
    </button>
  );
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
      <div className="kr-learn relative max-w-md flex-1">
        <label htmlFor="tutorial-search" className="sr-only">
          Search tutorials
        </label>
        <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-4 text-learn">
          <Search className="size-4" aria-hidden="true" />
        </div>
        <input
          id="tutorial-search"
          type="search"
          data-testid="tutorial-search-input"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search tutorials by title, description, or prompt..."
          className="kr-input w-full !rounded-full py-2.5 pl-10 pr-10 text-sm"
        />
        {searchQuery ? (
          <button
            type="button"
            data-testid="tutorial-search-clear"
            onClick={() => onSearchChange("")}
            className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-ink-400 hover:text-white"
            aria-label="Clear search"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>

      {/* Status Filter Tabs / Pills */}
      <div
        role="tablist"
        aria-label="Filter by verification status"
        className="kr-glass flex items-center gap-1 rounded-full p-1"
      >
        <FilterTab
          testId="filter-status-all"
          selected={statusFilter === "all"}
          color="var(--learn)"
          label="All"
          count={counts.all}
          onClick={() => onStatusFilterChange("all")}
        />
        <FilterTab
          testId="filter-status-verified"
          selected={statusFilter === "verified"}
          color="var(--verify)"
          label="Verified"
          count={counts.verified}
          onClick={() => onStatusFilterChange("verified")}
        />
        <FilterTab
          testId="filter-status-outdated"
          selected={statusFilter === "outdated"}
          color="var(--plan)"
          label="Outdated"
          count={counts.outdated}
          onClick={() => onStatusFilterChange("outdated")}
        />
        {counts.autoUpdated !== undefined && counts.autoUpdated > 0 ? (
          <FilterTab
            testId="filter-status-auto-updated"
            selected={statusFilter === "auto-updated"}
            color="#0284c7"
            label="Auto-Updated"
            count={counts.autoUpdated}
            onClick={() => onStatusFilterChange("auto-updated")}
          />
        ) : null}
        {counts.notAutoChecked !== undefined && counts.notAutoChecked > 0 ? (
          <FilterTab
            testId="filter-status-not-auto-checked"
            selected={statusFilter === "not_auto_checked"}
            color="#71717a"
            label="Not Checked"
            count={counts.notAutoChecked}
            onClick={() => onStatusFilterChange("not_auto_checked")}
          />
        ) : null}
      </div>
    </div>
  );
}
