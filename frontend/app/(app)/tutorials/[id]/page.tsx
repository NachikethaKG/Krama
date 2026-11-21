import { Suspense, use } from "react";
import { getTranslations } from "next-intl/server";
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
        {stored ? <WorkflowTutorial workflowId={id} /> : <TutorialPlayer spec={spec} workflowId={id} />}
      </main>
    </div>
  );
}

export default async function TutorialDetailPage({ params }: TutorialDetailPageProps) {
  const t = await getTranslations("shell.tutorialPage");
  return (
    <Suspense
      fallback={
        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20">
          <div className="flex flex-col items-center justify-center p-10 text-center">
            <div className="kr-spectrum-border mb-5 size-14 animate-spin rounded-full bg-ink-900 [animation-duration:2.5s]" />
            <h2 className="kr-display text-lg font-bold text-white">
              {t("loading")}
            </h2>
          </div>
        </main>
      }
    >
      <TutorialDetailInner params={params} />
    </Suspense>
  );
}
