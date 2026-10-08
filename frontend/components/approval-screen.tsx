"use client";

import { useEffect, useState } from "react";
import type { Step, Workflow } from "@krama/contracts-ts";

import { ApprovalControls } from "@/components/approval-controls";
import { StepList } from "@/components/step-list";
import { TaskHeader } from "@/components/task-header";
import { type ApiClient, createApiClient } from "@/lib/api";

export interface ApprovalScreenProps {
  initialWorkflowId?: string;
  client?: ApiClient;
  initialWorkflow?: Workflow;
}

export function ApprovalScreen({
  initialWorkflowId = "default",
  client,
  initialWorkflow,
}: ApprovalScreenProps) {
  const [apiClient] = useState<ApiClient>(() => client ?? createApiClient());
  const [workflow, setWorkflow] = useState<Workflow | null>(initialWorkflow ?? null);
  const [isLoading, setIsLoading] = useState<boolean>(!initialWorkflow);
  const [isPending, setIsPending] = useState<boolean>(false);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(initialWorkflow?.status ?? "draft");

  useEffect(() => {
    if (initialWorkflow) {
      return;
    }

    let isMounted = true;

    apiClient
      .getWorkflow(initialWorkflowId)
      .then((data) => {
        if (isMounted) {
          setWorkflow(data);
          setStatus(data.status ?? "draft");
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load workflow plan");
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [apiClient, initialWorkflow, initialWorkflowId]);

  const handleInstructionChange = (stepSeq: number, newInstruction: string) => {
    if (!workflow) return;
    const updatedSteps = workflow.steps.map((s: Step) =>
      s.seq === stepSeq ? { ...s, instruction_text: newInstruction } : s
    );
    setWorkflow({ ...workflow, steps: updatedSteps });
  };

  const handleApprove = async () => {
    setIsPending(true);
    setError(null);
    try {
      // Simulate network roundtrip if needed
      await new Promise((resolve) => setTimeout(resolve, 80));
      setStatus("approved");
      if (workflow) {
        setWorkflow({ ...workflow, status: "approved" });
      }
      setIsEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setIsPending(false);
    }
  };

  const handleReject = async () => {
    setIsPending(true);
    setError(null);
    try {
      await new Promise((resolve) => setTimeout(resolve, 80));
      setStatus("rejected");
      if (workflow) {
        setWorkflow({ ...workflow, status: "failed" });
      }
      setIsEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Rejection failed");
    } finally {
      setIsPending(false);
    }
  };

  if (isLoading) {
    return (
      <main
        data-testid="approval-screen-loading"
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-3 px-4 py-20 text-center"
      >
        <div className="size-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-800 dark:border-zinc-700 dark:border-t-zinc-200" />
        <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
          Loading workflow plan…
        </p>
      </main>
    );
  }

  if (error && !workflow) {
    return (
      <main
        data-testid="approval-screen-error"
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20 text-center"
      >
        <div className="rounded-full bg-rose-100 p-3 text-rose-600 dark:bg-rose-950/50 dark:text-rose-400">
          <svg className="size-6" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
        </div>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
          Workflow Not Found
        </h1>
        <p className="max-w-md text-sm text-zinc-600 dark:text-zinc-400">{error}</p>
      </main>
    );
  }

  const promptText =
    workflow?.task ||
    (workflow?.title ? `Execute task: ${workflow.title}` : "Create a repository in local Gitea");
  const targetUrl = workflow?.target_url || workflow?.target?.base_url || "http://localhost:3001";

  return (
    <main
      data-testid="approval-screen"
      className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8 sm:py-12"
    >
      {/* 1. Task input view with prompt and target URL */}
      <TaskHeader
        title={workflow?.title || "Create a repository in local Gitea"}
        prompt={promptText}
        targetUrl={targetUrl}
        targetApp={workflow?.target_app || workflow?.target?.app || "gitea"}
        status={status}
      />

      {/* 2. Step list with instruction text and risk badges */}
      <StepList
        steps={workflow?.steps || []}
        isEditing={isEditing}
        onInstructionChange={handleInstructionChange}
      />

      {/* 3. Action controls: Edit / Approve / Reject */}
      <ApprovalControls
        workflowId={workflow?.id || initialWorkflowId}
        status={status}
        isEditing={isEditing}
        isPending={isPending}
        error={error}
        onToggleEdit={() => setIsEditing(!isEditing)}
        onApprove={handleApprove}
        onReject={handleReject}
      />
    </main>
  );
}
