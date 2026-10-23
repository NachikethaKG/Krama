"use client";

import { useState } from "react";
import Link from "next/link";
import type { TutorialSummary } from "@/types/tutorial";

export interface MyTutorialsSectionProps {
  tutorials: TutorialSummary[];
}

function formatDuration(durationMs: number): string {
  if (!durationMs || durationMs <= 0) return "< 1 min";
  if (durationMs < 60000) return "< 1 min";
  const minutes = Math.round(durationMs / 60000);
  return `~${minutes} min`;
}

function formatDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return isoString;
  }
}

export function MyTutorialsSection({ tutorials }: MyTutorialsSectionProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopyLink = async (tutorialId: string) => {
    try {
      const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost:3000";
      const shareUrl = `${origin}/tutorials/${tutorialId}`;
      await navigator.clipboard.writeText(shareUrl);
      setCopiedId(tutorialId);
      setTimeout(() => {
        setCopiedId((current) => (current === tutorialId ? null : current));
      }, 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <section aria-labelledby="my-tutorials-heading">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2
            id="my-tutorials-heading"
            className="text-lg font-bold tracking-tight text-zinc-900 dark:text-zinc-100 flex items-center gap-2"
          >
            <span>My Recorded Tutorials</span>
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-semibold text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
              {tutorials.length}
            </span>
          </h2>
          <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
            Interactive walk-throughs compiled and verified from your task execution runs
          </p>
        </div>

        <Link
          href="/tutorials"
          className="text-xs font-semibold text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
        >
          View all library →
        </Link>
      </div>

      {tutorials.length === 0 ? (
        <div
          data-testid="empty-my-tutorials"
          className="rounded-xl border border-dashed border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950"
        >
          <div className="mx-auto flex size-10 items-center justify-center rounded-full bg-zinc-100 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-500 mb-3">
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
                d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"
              />
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            You haven&apos;t recorded any tutorials yet
          </h3>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400 max-w-sm mx-auto">
            When your agent runs complete successfully, verified step workflows are automatically compiled into interactive player tutorials.
          </p>
          <Link
            href="/runs/new"
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
          >
            + Create Your First Workflow
          </Link>
        </div>
      ) : (
        <div
          data-testid="my-tutorials-list"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          {tutorials.map((tutorial) => (
            <div
              key={tutorial.id}
              data-testid="dashboard-tutorial-item"
              className="flex flex-col justify-between rounded-xl border border-zinc-200 bg-white p-5 shadow-xs hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-700 transition-all"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <span
                    data-testid="tutorial-target-badge"
                    className="inline-flex items-center gap-1 rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-0.5 text-[10px] font-semibold text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 capitalize"
                  >
                    {tutorial.target}
                  </span>

                  <span
                    data-testid="tutorial-status-badge"
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-semibold border ${
                      tutorial.status === "verified"
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
                        : "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
                    }`}
                  >
                    <span
                      className={`size-1.5 rounded-full ${
                        tutorial.status === "verified" ? "bg-emerald-500" : "bg-amber-500"
                      }`}
                    />
                    <span className="capitalize">{tutorial.status}</span>
                  </span>
                </div>

                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 line-clamp-2">
                  {tutorial.title}
                </h3>

                <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                  {tutorial.stepCount} steps · {formatDuration(tutorial.durationMs)} · {formatDate(tutorial.createdAt)}
                </p>
              </div>

              <div className="mt-4 pt-3.5 border-t border-zinc-100 dark:border-zinc-800/80 flex items-center justify-between gap-2">
                <Link
                  href={`/tutorials/${tutorial.id}`}
                  data-testid="dashboard-open-tutorial"
                  className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 transition-colors"
                >
                  <span>Open Player</span>
                  <span aria-hidden="true">→</span>
                </Link>

                <button
                  type="button"
                  data-testid="dashboard-share-tutorial"
                  onClick={() => handleCopyLink(tutorial.id)}
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 transition-colors"
                >
                  <svg
                    className="size-3.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z"
                    />
                  </svg>
                  <span>{copiedId === tutorial.id ? "Copied!" : "Share Link"}</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
