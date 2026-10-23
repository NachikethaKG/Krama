import { Suspense } from "react";
import { RunDetailRouter } from "./RunDetailRouter";

export interface RunDetailPageProps {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{ view?: string; speed?: string }>;
}

export default async function RunDetailPage({ params, searchParams }: RunDetailPageProps) {
  const { id } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const viewParam = resolvedSearchParams?.view;

  return (
    <Suspense
      fallback={
        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20">
          <div
            data-testid="run-details-loading"
            className="flex flex-col items-center justify-center p-10 text-center"
          >
            <div className="size-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4" />
            <h2 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">
              Loading Run…
            </h2>
          </div>
        </main>
      }
    >
      <RunDetailRouter runId={id} viewParam={viewParam} />
    </Suspense>
  );
}
