import { Suspense } from "react";
import { getTranslations } from "next-intl/server";
import { RunDetailRouter } from "./RunDetailRouter";

export interface RunDetailPageProps {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{ view?: string; speed?: string }>;
}

export default async function RunDetailPage({ params, searchParams }: RunDetailPageProps) {
  const { id } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const viewParam = resolvedSearchParams?.view;
  const t = await getTranslations("shell.runDetail");

  return (
    <Suspense
      fallback={
        <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20">
          <div
            data-testid="run-details-loading"
            className="flex flex-col items-center justify-center p-10 text-center"
          >
            <div className="mb-4 size-12 animate-spin rounded-full border-4 border-white/10 border-t-run shadow-[0_0_30px_-4px_var(--run)]" />
            <h2 className="font-mono text-sm font-semibold text-run">
              {t("loading")}
            </h2>
          </div>
        </main>
      }
    >
      <RunDetailRouter runId={id} viewParam={viewParam} />
    </Suspense>
  );
}
