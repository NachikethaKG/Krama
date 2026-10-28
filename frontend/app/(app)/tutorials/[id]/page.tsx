import { Suspense, use } from "react";
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
    <div>
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
              Loading tutorial…
            </h2>
          </div>
        </main>
      }
    >
      <TutorialDetailInner params={params} />
    </Suspense>
  );
}
