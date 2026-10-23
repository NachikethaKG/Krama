"use client";

import { useEffect, useState } from "react";
import { type ApiClient, errorMessage, getApiClient } from "@/lib/api";
import type { RunListItem } from "@/lib/types";
import type { TutorialSummary } from "@/types/tutorial";
import type { User } from "@krama/contracts-ts";
import { DashboardHeader } from "./DashboardHeader";
import { MyTutorialsSection } from "./MyTutorialsSection";
import { RecentRunsSection } from "./RecentRunsSection";

export interface DashboardViewProps {
  client?: ApiClient;
  initialUser?: User;
  initialTutorials?: TutorialSummary[];
  initialRuns?: RunListItem[];
}

export function DashboardView({
  client,
  initialUser,
  initialTutorials,
  initialRuns,
}: DashboardViewProps) {
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [user, setUser] = useState<User | null>(initialUser ?? null);
  const [tutorials, setTutorials] = useState<TutorialSummary[]>(initialTutorials ?? []);
  const [runs, setRuns] = useState<RunListItem[]>(initialRuns ?? []);
  const [isLoading, setIsLoading] = useState<boolean>(!initialUser);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialUser && initialTutorials && initialRuns) return;

    let isMounted = true;

    Promise.all([
      apiClient.getMe(),
      apiClient.getTutorials ? apiClient.getTutorials({ status: "all" }) : Promise.resolve([]),
      apiClient.getRuns({ limit: 10 }),
    ])
      .then(([userData, tutorialsData, runsPage]) => {
        if (!isMounted) return;
        setUser(userData);
        setTutorials(tutorialsData);
        setRuns(runsPage.items);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(errorMessage(err, "Failed to load dashboard data."));
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [apiClient, initialUser, initialTutorials, initialRuns]);

  if (isLoading) {
    return (
      <div
        data-testid="dashboard-loading"
        className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex flex-col justify-center items-center py-20"
      >
        <div className="size-10 rounded-full border-3 border-indigo-600 border-t-transparent animate-spin mb-4" />
        <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Loading your dashboard…</p>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 px-4 py-16">
        <div
          role="alert"
          data-testid="dashboard-error"
          className="mx-auto max-w-lg rounded-xl border border-rose-200 bg-rose-50 p-6 text-center dark:border-rose-900/60 dark:bg-rose-950/30"
        >
          <h2 className="text-sm font-semibold text-rose-900 dark:text-rose-200">
            Unable to Load Dashboard
          </h2>
          <p className="mt-1 text-xs text-rose-700 dark:text-rose-400">{error ?? "Authentication required."}</p>
          <a
            href="/login"
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-rose-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-rose-500 transition-colors"
          >
            Go to Sign In
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900/50">
      <DashboardHeader user={user} client={apiClient} />

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-10">
        <MyTutorialsSection tutorials={tutorials} />
        <RecentRunsSection runs={runs} />
      </main>
    </div>
  );
}
