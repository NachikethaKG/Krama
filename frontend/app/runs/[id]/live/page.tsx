import { LiveExecutionView } from "@/components/execution/live-execution-view";

export interface RunLivePageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ speed?: string }>;
}

/** Live view of one run, keyed by the RUN id (POST /plans/{id}/approve returns the Run). */
export default async function RunLivePage({ params, searchParams }: RunLivePageProps) {
  const { id } = await params;
  const { speed: rawSpeed } = await searchParams;
  const speed = rawSpeed ? Number(rawSpeed) : undefined;

  return <LiveExecutionView runId={id} speed={speed !== undefined && Number.isFinite(speed) ? speed : undefined} />;
}
