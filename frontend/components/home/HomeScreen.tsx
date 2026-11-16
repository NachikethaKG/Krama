"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GraduationCap, Loader2 } from "lucide-react";
import { TaskInput } from "@/components/task-input";
import { TutorialCard } from "@/components/tutorials";
import { STAGES } from "@/components/ui";
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
    <main data-testid="home-screen" className="mx-auto flex max-w-5xl flex-col gap-14 px-4 py-10 sm:px-6">
      <section className="flex flex-col gap-5">
        <div className="kr-rise flex flex-col items-start gap-4">
          <span className="kr-chip kr-ask">
            <span className="kr-dot kr-dot-live !size-1.5" />
            Ask anything about a website
          </span>
          <h1
            aria-label="Learn any task by watching it done"
            className="kr-display text-4xl font-extrabold leading-[1.02] text-white sm:text-6xl"
          >
            Learn any task by <span className="kr-gradient-text">watching it done</span>
          </h1>
          <p className="max-w-2xl text-base text-ink-300 sm:text-lg">
            Describe what you want to do. Krama plans the steps, you approve them, then it does the task in a real
            browser, checks every step and turns it into an interactive tutorial.
          </p>
          {/* the pipeline, as a row of coloured beads */}
          <div aria-hidden="true" className="flex flex-wrap items-center gap-1.5">
            {STAGES.map((stage, i) => {
              const Icon = stage.icon;
              return (
                <span key={stage.key} className="flex items-center gap-1.5">
                  <span
                    className="kr-rise flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold text-ink-950"
                    style={{
                      background: stage.color,
                      boxShadow: `0 0 16px -4px ${stage.color}`,
                      animationDelay: `${200 + i * 70}ms`,
                    }}
                  >
                    <Icon className="size-3" />
                    {stage.label}
                  </span>
                  {i < STAGES.length - 1 && <span className="h-px w-3 bg-white/25" />}
                </span>
              );
            })}
          </div>
        </div>
        <TaskInput client={apiClient} className="kr-rise mt-2 [animation-delay:120ms]" />
      </section>

      <section aria-labelledby="recent-heading" className="kr-learn flex flex-col gap-5">
        <div className="flex items-end justify-between gap-3">
          <div className="flex items-center gap-3">
            <span
              aria-hidden="true"
              className="flex size-10 items-center justify-center rounded-2xl text-ink-950"
              style={{ background: "var(--learn)", boxShadow: "0 0 24px -4px var(--learn)" }}
            >
              <GraduationCap className="size-5" />
            </span>
            <h2 id="recent-heading" className="kr-display text-2xl font-extrabold text-white sm:text-3xl">
              Recent tutorials
            </h2>
          </div>
          <Link href="/tutorials" className="text-sm font-bold text-learn transition-colors hover:text-white">
            See all →
          </Link>
        </div>
        <div aria-hidden="true" className="h-px w-full bg-gradient-to-r from-learn via-ask/40 to-transparent" />
        {recent === null ? (
          <p className="flex items-center gap-2 text-sm text-ink-400">
            <Loader2 aria-hidden="true" className="size-4 animate-spin text-learn" />
            Loading…
          </p>
        ) : recent.length === 0 ? (
          <p
            data-testid="home-no-tutorials"
            className="rounded-3xl border border-dashed border-white/15 bg-white/[0.02] px-6 py-10 text-center text-sm text-ink-400"
          >
            No tutorials yet. Your first one will show up here.
          </p>
        ) : (
          <div data-testid="home-recent-tutorials" className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((tutorial, i) => (
              <div key={tutorial.id} className="kr-rise" style={{ animationDelay: `${i * 70}ms` }}>
                <TutorialCard tutorial={tutorial} index={i} />
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
