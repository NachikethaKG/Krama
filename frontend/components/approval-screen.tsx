"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Plan, PlannedStep, Task } from "@krama/contracts-ts";

import { ApprovalControls } from "@/components/approval-controls";
import { StepList } from "@/components/step-list";
import { TaskHeader } from "@/components/task-header";
import { type ApiClient, errorMessage, getApiClient, isApiError } from "@/lib/api";

export interface ApprovalScreenProps {
  /** The PLAN id (Task.plan_id). */
  planId: string;
  client?: ApiClient;
  initialPlan?: Plan;
  initialTask?: Task | null;
}

function renumber(steps: PlannedStep[]): PlannedStep[] {
  return steps.map((s, i) => ({ ...s, seq: i + 1 }));
}

export function ApprovalScreen({ planId, client, initialPlan, initialTask = null }: ApprovalScreenProps) {
  const router = useRouter();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [plan, setPlan] = useState<Plan | null>(initialPlan ?? null);
  const [task, setTask] = useState<Task | null>(initialTask);
  /** The steps as shown (edited locally until "Done Editing" saves them with PATCH /plans/{id}). */
  const [steps, setSteps] = useState<PlannedStep[]>(initialPlan?.steps ?? []);
  const [runId, setRunId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(!initialPlan);
  const [isPending, setIsPending] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflictError, setConflictError] = useState<string | null>(null);

  useEffect(() => {
    if (initialPlan) return;
    let active = true;
    (async () => {
      try {
        const loaded = await apiClient.getPlan(planId);
        if (!active) return;
        setPlan(loaded);
        setSteps(loaded.steps);
        setIsLoading(false);
        try {
          const loadedTask = await apiClient.getTask(loaded.task_id);
          if (active) setTask(loadedTask);
        } catch {
          // The header falls back to the plan's expected result.
        }
      } catch (err) {
        if (!active) return;
        setError(errorMessage(err, "Failed to load the plan"));
        setIsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [apiClient, initialPlan, planId]);

  const handleInstructionChange = (seq: number, text: string) =>
    setSteps((prev) => prev.map((s) => (s.seq === seq ? { ...s, instruction_text: text } : s)));

  const handleMove = (seq: number, delta: -1 | 1) =>
    setSteps((prev) => {
      const idx = prev.findIndex((s) => s.seq === seq);
      const target = idx + delta;
      if (idx === -1 || target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[target]] = [next[target], next[idx]];
      return renumber(next);
    });

  const handleDeleteStep = (seq: number) =>
    setSteps((prev) => (prev.length <= 1 ? prev : renumber(prev.filter((s) => s.seq !== seq))));

  const reportPlanError = (err: unknown, fallback: string) => {
    if (isApiError(err, "conflict")) {
      setConflictError(errorMessage(err));
    } else if (isApiError(err, "plan_not_editable")) {
      setError(`${errorMessage(err)} Reload to see its current state.`);
    } else {
      setError(errorMessage(err, fallback));
    }
  };

  const handleToggleEdit = async () => {
    if (!isEditing) {
      setConflictError(null);
      setIsEditing(true);
      return;
    }
    if (!plan) return;
    setIsPending(true);
    setError(null);
    setConflictError(null);
    try {
      const updated = await apiClient.updatePlan(plan.id, plan.revision, steps);
      setPlan(updated);
      setSteps(updated.steps);
      setIsEditing(false);
    } catch (err) {
      reportPlanError(err, "Failed to save the plan");
    } finally {
      setIsPending(false);
    }
  };

  const handleReloadPlan = async () => {
    setIsLoading(true);
    setConflictError(null);
    setError(null);
    try {
      const fresh = await apiClient.getPlan(plan?.id ?? planId);
      setPlan(fresh);
      setSteps(fresh.steps);
      setIsEditing(false);
    } catch (err) {
      setError(errorMessage(err, "Failed to reload the plan"));
    } finally {
      setIsLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!plan || isEditing) return;
    setIsPending(true);
    setError(null);
    setConflictError(null);
    try {
      // Approves exactly the revision on screen. The response is the RUN; the live view is keyed by its id.
      const run = await apiClient.approvePlan(plan.id, plan.revision);
      setPlan({ ...plan, status: "approved" });
      setRunId(run.id);
      router.push(`/runs/${run.id}/live`);
    } catch (err) {
      reportPlanError(err, "Approval failed");
    } finally {
      setIsPending(false);
    }
  };

  const handleReject = async () => {
    if (!plan) return;
    setIsPending(true);
    setError(null);
    try {
      const rejected = await apiClient.rejectPlan(plan.id);
      setPlan(rejected);
      setIsEditing(false);
    } catch (err) {
      reportPlanError(err, "Rejection failed");
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
        <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Loading workflow plan…</p>
      </main>
    );
  }

  if (!plan) {
    return (
      <main
        data-testid="approval-screen-error"
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20 text-center"
      >
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Plan Not Found</h1>
        <p className="max-w-md text-sm text-zinc-600 dark:text-zinc-400">{error}</p>
      </main>
    );
  }

  return (
    <main data-testid="approval-screen" className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8 sm:py-12">
      <TaskHeader
        title={plan.expected_result ? `Goal: ${plan.expected_result}` : "Here's the plan"}
        prompt={task?.prompt ?? plan.expected_result}
        targetUrl={task?.target_url}
        targetApp={task?.interpretation?.app}
        status={plan.status}
      />

      {conflictError && (
        <div
          role="alert"
          data-testid="plan-conflict-banner"
          className="flex flex-col gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 sm:flex-row sm:items-center sm:justify-between dark:border-amber-800 dark:bg-amber-950/40"
        >
          <div>
            <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-100">This plan changed in the meantime</h3>
            <p className="text-xs text-amber-800 dark:text-amber-300">{conflictError}</p>
          </div>
          <button
            type="button"
            data-testid="reload-plan-btn"
            onClick={handleReloadPlan}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-amber-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs transition-colors hover:bg-amber-500 dark:bg-amber-500 dark:hover:bg-amber-400"
          >
            Load the latest version
          </button>
        </div>
      )}

      {/* PRD §41: "I found a 6-step workflow. No destructive actions detected. [Approve & Run]" (#318) */}
      <PlanSummary steps={steps} />

      <StepList
        steps={steps}
        isEditing={isEditing}
        onInstructionChange={handleInstructionChange}
        onMoveUp={(seq) => handleMove(seq, -1)}
        onMoveDown={(seq) => handleMove(seq, 1)}
        onDeleteStep={handleDeleteStep}
      />

      <ApprovalControls
        runId={runId}
        status={plan.status}
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

/** One line before the steps: how many, and whether any of them is risky (the policy marks risk per step). */
function PlanSummary({ steps }: { steps: { risk?: string | null }[] }) {
  const risky = steps.filter((s) => s.risk === "high" || s.risk === "critical").length;
  return (
    <p
      data-testid="plan-summary"
      className={`rounded-lg border px-4 py-3 text-sm ${
        risky
          ? "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
          : "border-zinc-200 bg-white text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
      }`}
    >
      I found a {steps.length}-step plan.{" "}
      {risky
        ? `${risky} ${risky === 1 ? "step changes or deletes something" : "steps change or delete something"}: Krama will ask you again before ${risky === 1 ? "it" : "each one"}.`
        : "No destructive actions detected."}{" "}
      Check the steps, then approve to run them.
    </p>
  );
}
