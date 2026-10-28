import Link from "next/link";
import { ApiStatus } from "@/components/api-status";
import type { ApiClient } from "@/lib/api";

export interface LandingPageProps {
  /** Signed-in visitors get "Open Krama" instead of "Sign in". */
  signedIn?: boolean;
  client?: ApiClient;
}

const STEPS = [
  {
    title: "Ask",
    text: "Write what you want to learn, e.g. “Show me how to create a GitHub repository”.",
  },
  {
    title: "Approve the plan",
    text: "Krama lists every step first. Nothing runs until you approve it.",
  },
  {
    title: "Watch it done",
    text: "Krama does the task in a real browser and checks that every step worked.",
  },
  {
    title: "Learn from the tutorial",
    text: "Replay it step by step with narration, highlights and zoom, at your own pace.",
  },
];

/** The public landing page (the design from before #318, for visitors who aren't signed in). */
export function LandingPage({ signedIn = false, client }: LandingPageProps = {}) {
  const primary = signedIn
    ? { href: "/", label: "Open Krama" }
    : { href: "/login", label: "Sign in" };

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      {/* Navigation Header */}
      <header className="border-b border-zinc-200 bg-white/80 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-900/80">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 font-bold text-white shadow-sm dark:bg-indigo-500">
                K
              </span>
              <span className="text-xl font-bold tracking-tight text-zinc-900 dark:text-white">Krama</span>
            </Link>
            <span className="hidden rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 sm:inline dark:bg-indigo-950/60 dark:text-indigo-300">
              Verified UI Tutorial Engine
            </span>
          </div>

          <nav className="flex items-center gap-4 text-sm font-medium">
            <a
              href="#how-it-works"
              className="hidden text-zinc-600 hover:text-zinc-900 sm:inline dark:text-zinc-400 dark:hover:text-zinc-100"
            >
              How it works
            </a>
            <Link
              href={primary.href}
              data-testid="landing-primary-nav"
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-white shadow hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              {primary.label}
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
            Recorded and checked on real websites
          </div>

          <h1 className="mt-4 max-w-3xl text-4xl font-extrabold tracking-tight sm:text-5xl text-zinc-900 dark:text-white">
            Interactive Tutorials Recorded From Real UI Actions
          </h1>

          <p className="mt-4 max-w-2xl text-base text-zinc-600 dark:text-zinc-400 sm:text-lg">
            Tell Krama what you want to learn. It plans the steps, does the task in a real browser, checks every
            step, and turns it into an interactive guide with narration and focal zoom.
          </p>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-4">
            <Link
              href={primary.href}
              data-testid="landing-primary-cta"
              className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 dark:bg-indigo-500 dark:hover:bg-indigo-400"
            >
              {signedIn ? "Open Krama" : "Sign in to start"}
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex items-center justify-center rounded-lg border border-zinc-300 bg-white px-5 py-2.5 text-sm font-semibold text-zinc-800 shadow-sm hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              See how it works
            </a>
          </div>
        </section>

        {/* Feature Cards */}
        <section className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 dark:bg-indigo-950/60 dark:text-indigo-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h2 className="mt-3 text-sm font-semibold text-zinc-900 dark:text-white">Done on the real site</h2>
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              Krama drives a real browser on the real website, so the tutorial shows exactly what you will see.
            </p>
          </div>

          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="mt-3 text-sm font-semibold text-zinc-900 dark:text-white">Every step checked</h2>
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              After each step Krama checks the page really changed, so a tutorial never teaches a step that failed.
            </p>
          </div>

          <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-purple-50 text-purple-600 dark:bg-purple-950/60 dark:text-purple-400">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="mt-3 text-sm font-semibold text-zinc-900 dark:text-white">Interactive replay</h2>
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              Step-by-step guides with narration, captions, highlights and zoom. Passwords and private fields are
              masked.
            </p>
          </div>
        </section>

        {/* How it works (replaces the old "Quick Workflow Generator": creating needs a signed-in account) */}
        <section
          id="how-it-works"
          className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div className="mb-6 flex flex-col gap-1 border-b border-zinc-100 pb-4 dark:border-zinc-800">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-white">How it works</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">From a question to an interactive tutorial in about a minute.</p>
          </div>
          <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <li key={step.title} className="flex gap-3">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
                  {i + 1}
                </span>
                <div>
                  <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">{step.title}</h3>
                  <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-6 flex justify-center">
            <Link
              href={primary.href}
              className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500"
            >
              {signedIn ? "Make a tutorial" : "Sign in to try it"}
            </Link>
          </div>
        </section>
      </main>

      {/* Footer with Discreet Status Indicator */}
      <footer className="mt-auto border-t border-zinc-200 bg-white py-6 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
          <div className="flex flex-col gap-1 text-center sm:text-left">
            <p className="text-xs text-zinc-500 dark:text-zinc-400">Krama &bull; Verified interactive tutorials</p>
            <div className="flex items-center justify-center gap-4 text-xs text-zinc-400 dark:text-zinc-500 sm:justify-start">
              <a href="#how-it-works" className="hover:text-zinc-700 dark:hover:text-zinc-300">
                How it works
              </a>
              <Link href={primary.href} className="hover:text-zinc-700 dark:hover:text-zinc-300">
                {primary.label}
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
