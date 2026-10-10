import { LiveExecutionView } from "@/components/execution/live-execution-view";

export interface ExecutionPageProps {
  searchParams: Promise<{ mock?: string; speed?: string }>;
}

export default async function ExecutionPage({ searchParams }: ExecutionPageProps) {
  const resolvedSearchParams = await searchParams;
  const speed = resolvedSearchParams.speed ? Number(resolvedSearchParams.speed) : undefined;

  return <LiveExecutionView workflowId="default" speed={speed} />;
}
