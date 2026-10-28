"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { TaskInput } from "@/components/task-input";
import { TutorialCard } from "@/components/tutorials";
import { type ApiClient, getApiClient } from "@/lib/api";
import type { TutorialSummary } from "@/types/tutorial";

/** The signed-in home (#318): ask for a tutorial in plain words, and get back to recent ones. PRD §41. */
export function HomeScreen({ client }: { client?: ApiClient }) {
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [recent, setRecent] = useState<TutorialSummary[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .getTutorials({ limit: 6 })
      .then((items) => !cancelled && setRecent(items.slice(0, 6)))
      .catch(() => !cancelled && setRecent([]));
    return () => {
      cancelled = true;
    };
  }, [apiClient]);

  return (
    <main data-testid="home-screen" className="mx-auto flex max-w-4xl flex-col gap-10 px-4 py-10 sm:px-6">
      <section className="flex flex-col gap-3">
        <h1 className="text-2xl font-bold tracking-tight text-zinc-900 sm:text-3xl dark:text-zinc-100">
          Learn any task by watching it done
        </h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Describe what you want to do. Krama plans the steps, you approve them, then it does the task in a real
          browser, checks every step and turns it into an interactive tutorial.
        </p>
        <TaskInput client={apiClient} className="mt-2" />
      </section>

      <section aria-labelledby="recent-heading" className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between">
          <h2 id="recent-heading" className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            Recent tutorials
          </h2>
          <Link href="/tutorials" className="text-sm font-medium text-indigo-600 hover:text-indigo-500">
            See all →
          </Link>
        </div>
        {recent === null ? (
          <p className="text-sm text-zinc-500">Loading…</p>
        ) : recent.length === 0 ? (
          <p data-testid="home-no-tutorials" className="text-sm text-zinc-500">
            No tutorials yet. Your first one will show up here.
          </p>
        ) : (
          <div data-testid="home-recent-tutorials" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((tutorial) => (
              <TutorialCard key={tutorial.id} tutorial={tutorial} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
