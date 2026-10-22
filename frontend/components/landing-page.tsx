import Link from "next/link";
import { ApiStatus } from "@/components/api-status";
import { TaskInput } from "@/components/task-input";
import type { ApiClient } from "@/lib/api";

export interface LandingPageProps {
  client?: ApiClient;
}

export function LandingPage({ client }: LandingPageProps = {}) {
  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      {/* Navigation Header */}
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-900/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 font-bold text-white shadow-sm dark:bg-indigo-500">
                K
              </span>
              <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-white">
                Krama
              </h1>
            </Link>
            <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
              Verified UI Tutorial Engine
            </span>
          </div>

          <nav className="flex items-center gap-4 text-sm font-medium">
            <Link
              href="/dashboard"
              className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
            >
              Dashboard
            </Link>
            <Link
              href="/tutorials"
              className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
            >
              Tutorials
            </Link>
            <Link
              href="/runs"
              className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
            >
              Runs
            </Link>
            <Link
              href="/runs/new"
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-white shadow hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              + Create Workflow
            </Link>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-12 px-4 py-12 sm:px-6">
        {/* Hero Section */}
        <section className="flex flex-col items-center text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50/50 px-3 py-1 text-xs font-medium text-indigo-700 dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-300">
            <span className="flex h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
            Autonomous Headless Verification
          </div>

          <h2 className="mt-4 max-w-3xl text-4xl font-extrabold tracking-tight sm:text-5xl text-zinc-900 dark:text-white">
            Interactive Tutorials Recorded From Real UI Actions
          </h2>

          <p className="mt-4 max-w-2xl text-base text-zinc-600 dark:text-zinc-400 sm:text-lg">
            Krama plans, executes, and verifies workflows headlessly on real sites, compiling
            them into interactive step-by-step guides with synchronized narration and focal camera zoom.
          </p>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 dark:bg-indigo-500 dark:hover:bg-indigo-400"
            >
              Go to Dashboard
            </Link>
            <Link
              href="/tutorials"
              className="inline-flex items-center justify-center rounded-lg border border-zinc-300 bg-white px-5 py-2.5 text-sm font-semibold text-zinc-800 shadow-sm hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              Explore Tutorials
            </Link>
            <Link
              href="/runs/new"
              className="inline-flex items-center justify-center rounded-lg border border-transparent px-4 py-2.5 text-sm font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 dark:hover:text-indigo-300"
            >
              Create Workflow →
            </Link>
          </div>
        </section>

        {/* Feature Cards */}
        <section className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 className="mt-3 text-sm font-semibold text-zinc-900 dark:text-white">
              Autonomous Execution
            </h3>
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              Agent drives real headless browsers with natural wrist motion trajectories on target web applications.
            </p>
          </div>

          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="mt-3 text-sm font-semibold text-zinc-900 dark:text-white">
              Multi-Layer Verification
            </h3>
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              Independent verifier checks URL transitions, DOM tree changes, and visual invariants for high confidence.
            </p>
          </div>

          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50 text-purple-600 dark:bg-purple-950/60 dark:text-purple-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="mt-3 text-sm font-semibold text-zinc-900 dark:text-white">
              Interactive Replay
            </h3>
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              Compiled into zoomable step-by-step guides with natural speech rate progress sizing and full privacy masking.
            </p>
          </div>
        </section>

        {/* Workflow Generator Section */}
        <section id="create-workflow" className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mb-6 flex flex-col gap-1 border-b border-zinc-100 pb-4 dark:border-zinc-800">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-white">
              Quick Workflow Generator
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Submit a task instruction below or select a benchmark target to generate and verify a tutorial.
            </p>
          </div>
          <TaskInput client={client} />
        </section>
      </main>

      {/* Footer with Discreet Status Indicator */}
      <footer className="mt-auto border-t border-zinc-200 bg-white py-6 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
          <div className="flex flex-col gap-1 text-center sm:text-left">
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Krama Verified UI Tutorial Engine &bull; Phase 3 MVP
            </p>
            <div className="flex items-center justify-center gap-4 text-xs text-zinc-400 dark:text-zinc-500 sm:justify-start">
              <Link href="/dashboard" className="hover:text-zinc-700 dark:hover:text-zinc-300">
                Dashboard
              </Link>
              <Link href="/tutorials" className="hover:text-zinc-700 dark:hover:text-zinc-300">
                Library
              </Link>
              <Link href="/runs" className="hover:text-zinc-700 dark:hover:text-zinc-300">
                Runs
              </Link>
              <Link href="/runs/new" className="hover:text-zinc-700 dark:hover:text-zinc-300">
                New Run
              </Link>
            </div>
          </div>

          <div className="flex items-center">
            <ApiStatus client={client} />
          </div>
        </div>
      </footer>
    </div>
  );
}

export { LandingPage as HomePage };
