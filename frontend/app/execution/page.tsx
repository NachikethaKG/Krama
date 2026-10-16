import { LiveExecutionView } from "@/components/execution/live-execution-view";

export interface ExecutionPageProps {
  searchParams: Promise<{ speed?: string }>;
}

/** Mock-mode demo of the live view (the scripted "default" run). Real runs live at /runs/{runId}/live. */
export default async function ExecutionPage({ searchParams }: ExecutionPageProps) {
  const { speed: rawSpeed } = await searchParams;
  const speed = rawSpeed ? Number(rawSpeed) : undefined;

  return <LiveExecutionView runId="default" speed={speed !== undefined && Number.isFinite(speed) ? speed : undefined} />;
}
