"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { PlannedStep, Step, Workflow } from "@krama/contracts-ts";

import { ApprovalControls } from "@/components/approval-controls";
import { StepList } from "@/components/step-list";
import { TaskHeader } from "@/components/task-header";
import { type ApiClient, getApiClient } from "@/lib/api";

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
  const router = useRouter();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [workflow, setWorkflow] = useState<Workflow | null>(initialWorkflow ?? null);
  const [planRevision, setPlanRevision] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(!initialWorkflow);
  const [isPending, setIsPending] = useState<boolean>(false);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [conflictError, setConflictError] = useState<string | null>(null);
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

          if (typeof apiClient.getPlan === "function") {
            apiClient
              .getPlan(initialWorkflowId)
              .then((plan) => {
                if (isMounted) {
                  setPlanRevision(plan.revision);
                }
              })
              .catch(() => {
                // Ignore fallback error; default revision 1 is maintained
              });
          }
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

  const handleMoveUp = (stepSeq: number) => {
    if (!workflow) return;
    const idx = workflow.steps.findIndex((s) => s.seq === stepSeq);
    if (idx <= 0) return;
    const newSteps = [...workflow.steps];
    const temp = newSteps[idx - 1];
    newSteps[idx - 1] = newSteps[idx];
    newSteps[idx] = temp;
    const reindexed = newSteps.map((s, i) => ({ ...s, seq: i + 1 }));
    setWorkflow({ ...workflow, steps: reindexed });
  };

  const handleMoveDown = (stepSeq: number) => {
    if (!workflow) return;
    const idx = workflow.steps.findIndex((s) => s.seq === stepSeq);
    if (idx === -1 || idx >= workflow.steps.length - 1) return;
    const newSteps = [...workflow.steps];
    const temp = newSteps[idx + 1];
    newSteps[idx + 1] = newSteps[idx];
    newSteps[idx] = temp;
    const reindexed = newSteps.map((s, i) => ({ ...s, seq: i + 1 }));
    setWorkflow({ ...workflow, steps: reindexed });
  };

  const handleDeleteStep = (stepSeq: number) => {
    if (!workflow || workflow.steps.length <= 1) return;
    const filtered = workflow.steps.filter((s) => s.seq !== stepSeq);
    const reindexed = filtered.map((s, i) => ({ ...s, seq: i + 1 }));
    setWorkflow({ ...workflow, steps: reindexed });
  };

  const handleToggleEdit = async () => {
    if (!isEditing) {
      setConflictError(null);
      setIsEditing(true);
      return;
    }

    if (!workflow) {
      setIsEditing(false);
      return;
    }

    setIsPending(true);
    setError(null);
    setConflictError(null);

    const plannedSteps = workflow.steps.map((s) => ({
      seq: s.seq,
      action: s.action,
      target: s.target,
      instruction_text: s.instruction_text,
      expected_state: s.expected_state,
      risk: s.risk,
    })) as [PlannedStep, ...PlannedStep[]];

    try {
      if (typeof apiClient.updatePlan === "function") {
        const updated = await apiClient.updatePlan(
          workflow.id || initialWorkflowId,
          planRevision,
          { steps: plannedSteps }
        );
        setPlanRevision(updated.revision);
      }
      setIsEditing(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (
        msg.includes("409") ||
        msg.toLowerCase().includes("conflict") ||
        msg.toLowerCase().includes("stale")
      ) {
        setConflictError(msg);
      } else {
        setError(msg);
      }
    } finally {
      setIsPending(false);
    }
  };

  const handleReloadPlan = async () => {
    setIsLoading(true);
    setConflictError(null);
    setError(null);
    try {
      const planId = workflow?.id || initialWorkflowId;
      const plan = await apiClient.getPlan(planId);
      setPlanRevision(plan.revision);
      setWorkflow({
        id: plan.id,
        title: plan.expected_result || "Generated Workflow Plan",
        task: plan.expected_result,
        target_url: workflow?.target_url || "http://localhost:3001",
        target_app: workflow?.target_app || "gitea",
        status: plan.status === "proposed" ? "draft" : (plan.status as Workflow["status"]),
        steps: plan.steps.map((s) => ({
          id: `${plan.id}-${s.seq}`,
          seq: s.seq,
          action: s.action,
          target: s.target,
          instruction_text: s.instruction_text,
          risk: s.risk,
          expected_state: s.expected_state,
          observed_state: { url: "" },
          verification: { result: "skipped" as const, method: ["url" as const], confidence: 1 },
        })),
      });
      setIsEditing(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reload plan");
    } finally {
      setIsLoading(false);
    }
  };

  const handleApprove = async () => {
    setIsPending(true);
    setError(null);
    setConflictError(null);
    try {
      if (typeof apiClient.approvePlan === "function") {
        await apiClient.approvePlan(workflow?.id || initialWorkflowId, planRevision);
      }
      setStatus("approved");
      if (workflow) {
        setWorkflow({ ...workflow, status: "approved" });
      }
      setIsEditing(false);

      const targetId = workflow?.id || initialWorkflowId;
      setTimeout(() => {
        router.push(`/workflows/${targetId}/execution`);
      }, 600);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Approval failed";
      if (
        msg.includes("409") ||
        msg.toLowerCase().includes("conflict") ||
        msg.toLowerCase().includes("stale")
      ) {
        setConflictError(msg);
      } else {
        setError(msg);
      }
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

      {/* Conflict error banner */}
      {conflictError && (
        <div
          role="alert"
          data-testid="plan-conflict-banner"
          className="flex flex-col gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 sm:flex-row sm:items-center sm:justify-between dark:border-amber-800 dark:bg-amber-950/40"
        >
          <div className="flex items-start gap-3">
            <svg
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0 text-amber-600 dark:text-amber-400"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
              />
            </svg>
            <div>
              <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-100">
                Plan Revision Conflict
              </h3>
              <p className="text-xs text-amber-800 dark:text-amber-300">
                {conflictError}
              </p>
            </div>
          </div>
          <button
            type="button"
            data-testid="reload-plan-btn"
            onClick={handleReloadPlan}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-amber-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-amber-500 focus:outline-hidden dark:bg-amber-500 dark:hover:bg-amber-400"
          >
            Reload Latest Plan
          </button>
        </div>
      )}

      {/* 2. Step list with instruction text, reordering, deletion, and risk badges */}
      <StepList
        steps={workflow?.steps || []}
        isEditing={isEditing}
        onInstructionChange={handleInstructionChange}
        onMoveUp={handleMoveUp}
        onMoveDown={handleMoveDown}
        onDeleteStep={handleDeleteStep}
      />

      {/* 3. Action controls: Edit / Approve / Reject */}
      <ApprovalControls
        workflowId={workflow?.id || initialWorkflowId}
        status={status}
        isEditing={isEditing}
        isPending={isPending}
        error={error}
        onToggleEdit={handleToggleEdit}
        onApprove={handleApprove}
        onReject={handleReject}
      />
    </main>
  );
}
