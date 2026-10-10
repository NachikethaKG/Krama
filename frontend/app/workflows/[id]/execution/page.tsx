import { LiveExecutionView } from "@/components/execution/live-execution-view";

export interface WorkflowExecutionPageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ mock?: string; speed?: string }>;
}

export default async function WorkflowExecutionPage({
  params,
  searchParams,
}: WorkflowExecutionPageProps) {
  const { id } = await params;
  const resolvedSearchParams = await searchParams;
  const speed = resolvedSearchParams.speed ? Number(resolvedSearchParams.speed) : undefined;

  return <LiveExecutionView workflowId={id} speed={speed} />;
}
