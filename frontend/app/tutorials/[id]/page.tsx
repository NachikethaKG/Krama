import { Suspense, use } from "react";
import Link from "next/link";
import { compileWorkflow, type TutorialSpec } from "@krama/tutorial-compiler";
import { TutorialPlayer, WorkflowTutorial } from "@/components/player";
import {
  giteaTutorialSpecFixture,
  tutorialSpecFixtures,
  workflowFixtures,
} from "@/lib/fixtures";

export interface TutorialDetailPageProps {
  params: Promise<{ id: string }>;
}

function resolveTutorialSpec(id: string): TutorialSpec {
  if (tutorialSpecFixtures[id]) {
    return tutorialSpecFixtures[id];
  }

  const workflow = workflowFixtures[id];
  if (workflow) {
    try {
      return compileWorkflow(workflow);
    } catch {
      // Fallback if compilation fails on custom workflow
      return giteaTutorialSpecFixture;
    }
  }

  return giteaTutorialSpecFixture;
}

/** Real API mode: an id that isn't a fixture is a stored workflow, loaded and played over its recording. */
function isStoredWorkflow(id: string): boolean {
  return process.env.NEXT_PUBLIC_API_MODE === "http" && !tutorialSpecFixtures[id] && !workflowFixtures[id];
}

function TutorialDetailInner({ params }: TutorialDetailPageProps) {
  const { id } = use(params);
  const spec = resolveTutorialSpec(id);
  const stored = isStoredWorkflow(id);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900/50">
      <nav className="border-b border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-sm font-semibold tracking-tight text-zinc-900 dark:text-zinc-100 hover:text-indigo-600 dark:hover:text-indigo-400"
            >
              ← Krama Home
            </Link>
            <span className="text-zinc-300 dark:text-zinc-700">/</span>
            <Link
              href="/tutorials"
              className="text-sm font-medium text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-200"
            >
              Tutorials
            </Link>
            <span className="text-zinc-300 dark:text-zinc-700">/</span>
            <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate max-w-xs">
              {stored ? "Tutorial" : spec.title}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/runs"
              className="rounded-md border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              Runs History
            </Link>
          </div>
        </div>
      </nav>

      <main className="py-6">
        {stored ? <WorkflowTutorial workflowId={id} /> : <TutorialPlayer spec={spec} />}
      </main>
    </div>
  );
}

export default function TutorialDetailPage({ params }: TutorialDetailPageProps) {
  return (
    <Suspense
      fallback={
        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20">
          <div className="flex flex-col items-center justify-center p-10 text-center">
            <div className="size-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mb-4" />
            <h2 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">
              Loading Tutorial…
            </h2>
          </div>
        </main>
      }
    >
      <TutorialDetailInner params={params} />
    </Suspense>
  );
}
