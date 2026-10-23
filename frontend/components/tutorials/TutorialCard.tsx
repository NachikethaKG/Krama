"use client";

import Link from "next/link";
import type { TargetPlatform, TutorialStatus, TutorialSummary } from "@/types/tutorial";

export interface TutorialCardProps {
  tutorial: TutorialSummary;
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

function TargetBadge({ target }: { target: TargetPlatform }) {
  switch (target) {
    case "github":
      return (
        <span
          data-testid="tutorial-card-target"
          data-target="github"
          className="inline-flex items-center gap-1 rounded-full border border-zinc-300 bg-zinc-100 px-2.5 py-0.5 text-xs font-semibold text-zinc-800 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200"
        >
          <svg
            className="size-3.5 fill-current"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
            />
          </svg>
          GitHub
        </span>
      );
    case "custom":
      return (
        <span
          data-testid="tutorial-card-target"
          data-target="custom"
          className="inline-flex items-center gap-1 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-0.5 text-xs font-semibold text-purple-700 dark:border-purple-800 dark:bg-purple-950/40 dark:text-purple-300"
        >
          <svg
            className="size-3.5 fill-none stroke-current stroke-2"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M12 2a14.5 14.5 0 000 20M2 12h20" />
          </svg>
          Custom
        </span>
      );
    case "gitea":
    default:
      return (
        <span
          data-testid="tutorial-card-target"
          data-target="gitea"
          className="inline-flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300"
        >
          <svg
            className="size-3.5 fill-none stroke-current stroke-2"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path d="M4 6a2 2 0 012-2h12a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V6z" />
            <path d="M9 10h6M9 14h6" />
          </svg>
          Gitea
        </span>
      );
  }
}

function StatusBadge({ status }: { status: TutorialStatus }) {
  if (status === "verified") {
    return (
      <span
        data-testid="tutorial-card-status"
        data-status="verified"
        className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
      >
        <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
        Verified
      </span>
    );
  }
  return (
    <span
      data-testid="tutorial-card-status"
      data-status="outdated"
      className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
    >
      <span className="size-1.5 rounded-full bg-amber-500" />
      Outdated
    </span>
  );
}

export function TutorialCard({ tutorial }: TutorialCardProps) {
  const durationLabel = formatDuration(tutorial.durationMs);
  const dateLabel = formatDate(tutorial.createdAt);

  return (
    <article
      data-testid="tutorial-card"
      data-tutorial-id={tutorial.id}
      className="group flex flex-col justify-between rounded-xl border border-zinc-200 bg-white p-5 shadow-xs transition-all hover:border-indigo-400 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-indigo-500"
    >
      <div>
        <div className="flex items-center justify-between gap-2 mb-3">
          <TargetBadge target={tutorial.target} />
          <StatusBadge status={tutorial.status} />
        </div>

        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors line-clamp-2">
          {tutorial.title}
        </h3>

        {tutorial.description ? (
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 line-clamp-2 leading-relaxed">
            {tutorial.description}
          </p>
        ) : tutorial.taskPrompt ? (
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400 italic line-clamp-2">
            &ldquo;{tutorial.taskPrompt}&rdquo;
          </p>
        ) : null}
      </div>

      <div className="mt-5 pt-4 border-t border-zinc-100 dark:border-zinc-800/80">
        <div
          data-testid="tutorial-card-meta"
          className="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400 mb-3"
        >
          <span className="flex items-center gap-1.5 font-medium">
            <svg
              className="size-3.5 stroke-current stroke-2 fill-none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            {tutorial.stepCount} {tutorial.stepCount === 1 ? "step" : "steps"} · {durationLabel}
          </span>
          <span className="text-zinc-400 dark:text-zinc-500">{dateLabel}</span>
        </div>

        <Link
          href={`/tutorials/${tutorial.id}`}
          data-testid="tutorial-card-open"
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-indigo-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-indigo-500 dark:hover:text-white"
        >
          <span>Open Tutorial</span>
          <span aria-hidden="true">→</span>
        </Link>
      </div>
    </article>
  );
}
