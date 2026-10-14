import { Suspense, use } from "react";
import { RunDetailView } from "@/components/runs";

export interface RunDetailPageProps {
  params: Promise<{ id: string }>;
}

function RunDetailInner({ params }: RunDetailPageProps) {
  const { id } = use(params);
  return <RunDetailView runId={id} />;
}

export default function RunDetailPage({ params }: RunDetailPageProps) {
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
              Loading Run Verification Evidence…
            </h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              Fetching step screenshots and multi-layer verification scores from artifact store
            </p>
          </div>
        </main>
      }
    >
      <RunDetailInner params={params} />
    </Suspense>
  );
}
