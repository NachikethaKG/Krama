"use client";

import Link from "next/link";
import type { TutorialFreshnessStatus } from "@/types/tutorial";

export interface TutorialStatusBadgeProps {
  status: TutorialFreshnessStatus;
  onInspectDiff?: () => void;
  diffHref?: string;
  className?: string;
  size?: "sm" | "md";
  "data-testid"?: string;
}

export function TutorialStatusBadge({
  status,
  onInspectDiff,
  diffHref,
  className = "",
  size = "md",
  "data-testid": testId,
}: TutorialStatusBadgeProps) {
  const sizeClasses =
    size === "sm"
      ? "px-2 py-0.5 text-[11px]"
      : "px-2.5 py-0.5 text-xs";

  switch (status) {
    case "verified":
      return (
        <span
          data-testid={testId || "tutorial-status-badge"}
          data-status="verified"
          data-tutorial-status="verified"
          role="status"
          aria-label="Freshness status: Verified"
          className={`inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 font-semibold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 ${sizeClasses} ${className}`}
        >
          <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" aria-hidden="true" />
          <span>Verified</span>
        </span>
      );

    case "auto-updated":
      return (
        <span
          data-testid={testId || "tutorial-status-badge"}
          data-status="auto-updated"
          data-tutorial-status="auto-updated"
          role="status"
          aria-label="Freshness status: Auto-Updated"
          className={`inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 font-semibold text-sky-700 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-300 ${sizeClasses} ${className}`}
        >
          <svg
            className="size-3.5 fill-none stroke-current stroke-2"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span>Auto-Updated</span>
          {onInspectDiff ? (
            <button
              type="button"
              data-testid="inspect-diff-button"
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                onInspectDiff();
              }}
              aria-label="View healed step diff"
              className="ml-1 inline-flex items-center gap-0.5 rounded px-1.5 py-0.2 text-[10px] font-medium bg-sky-200/80 hover:bg-sky-300/80 text-sky-900 dark:bg-sky-900/60 dark:hover:bg-sky-800 dark:text-sky-200 transition-colors"
            >
              Diff
            </button>
          ) : diffHref ? (
            <Link
              href={diffHref}
              data-testid="inspect-diff-button"
              onClick={(e) => e.stopPropagation()}
              aria-label="View healed step diff"
              className="ml-1 inline-flex items-center gap-0.5 rounded px-1.5 py-0.2 text-[10px] font-medium bg-sky-200/80 hover:bg-sky-300/80 text-sky-900 dark:bg-sky-900/60 dark:hover:bg-sky-800 dark:text-sky-200 transition-colors"
            >
              Diff
            </Link>
          ) : null}
        </span>
      );

    case "outdated":
      return (
        <span
          data-testid={testId || "tutorial-status-badge"}
          data-status="outdated"
          data-tutorial-status="outdated"
          role="status"
          aria-label="Freshness status: Outdated"
          className={`inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 font-semibold text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300 ${sizeClasses} ${className}`}
        >
          <span className="size-1.5 rounded-full bg-amber-500" aria-hidden="true" />
          <span>Outdated</span>
        </span>
      );

    case "not_auto_checked":
      return (
        <span
          data-testid={testId || "tutorial-status-badge"}
          data-status="not_auto_checked"
          data-tutorial-status="not_auto_checked"
          role="status"
          aria-label="Freshness status: Not Auto-Checked"
          className={`inline-flex items-center gap-1.5 rounded-full border border-zinc-300 bg-zinc-100 font-semibold text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 ${sizeClasses} ${className}`}
        >
          <svg
            className="size-3 fill-none stroke-current stroke-2 text-zinc-400"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9" />
            <path strokeLinecap="round" d="M9 12h6" />
          </svg>
          <span>Not Auto-Checked</span>
        </span>
      );

    default:
      return (
        <span
          data-testid={testId || "tutorial-status-badge"}
          data-status={status}
          data-tutorial-status={status}
          role="status"
          className={`inline-flex items-center gap-1.5 rounded-full border border-zinc-200 bg-zinc-50 font-semibold text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400 ${sizeClasses} ${className}`}
        >
          <span>{status}</span>
        </span>
      );
  }
}
