import { ApprovalScreen } from "@/components/approval-screen";

export interface WorkflowApprovalPageProps {
  params: Promise<{ id: string }>;
}

export default async function WorkflowApprovalPage({ params }: WorkflowApprovalPageProps) {
  const { id } = await params;
  return <ApprovalScreen initialWorkflowId={id} />;
}
