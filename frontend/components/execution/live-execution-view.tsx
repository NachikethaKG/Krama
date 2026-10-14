"use client";

import type { Workflow } from "@krama/contracts-ts";

import { VerificationFailureCard } from "@/components/diagnostics";
import { ExecutionHeader } from "@/components/execution/execution-header";
import { FailureBanner } from "@/components/execution/failure-banner";
import { PauseBanner } from "@/components/execution/pause-banner";
import { ReplanStatusIndicator } from "@/components/execution/ReplanStatusIndicator";
import { StepProgressItem } from "@/components/execution/step-progress-item";
import { useWorkflowExecutionStream } from "@/hooks/useWorkflowExecutionStream";
import type { ApiClient } from "@/lib/api";

export interface LiveExecutionViewProps {
  workflowId?: string;
  speed?: number;
  client?: ApiClient;
  initialWorkflow?: Workflow;
  className?: string;
}

export function LiveExecutionView({
  workflowId = "default",
  speed,
  client,
  initialWorkflow,
  className = "",
}: LiveExecutionViewProps) {
  const {
    runStatus,
    workflow,
    steps,
    pauseDetails,
    runError,
    replanState,
    elapsedSeconds,
    progressPercent,
    verifiedCount,
    totalSteps,
    isLoading,
    isCancelling,
    isConfirming,
    error,
    cancel,
    resume,
    deny,
    reset,
  } = useWorkflowExecutionStream({
    workflowId,
    client,
    speed,
    initialWorkflow,
  });

  if (isLoading) {
    return (
      <main
        data-testid="live-execution-loading"
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-3 px-4 py-20 text-center"
      >
        <div className="size-8 animate-spin rounded-full border-2 border-indigo-300 border-t-indigo-600 dark:border-indigo-800 dark:border-t-indigo-400" />
        <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
          Initializing live execution…
        </p>
      </main>
    );
  }

  if (error && !workflow) {
    return (
      <main
        data-testid="live-execution-error"
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
    (workflow?.title ? `Execute: ${workflow.title}` : "Create a repository in local Gitea");
  const targetUrl = workflow?.target_url || workflow?.target?.base_url || "http://localhost:3001";
  const failedStep = steps.find((s) => s.status === "failed");

  return (
    <main
      data-testid="live-execution-view"
      className={`mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8 sm:py-12 ${className}`}
    >
      {/* 1. Header with live status, timer & progress */}
      <ExecutionHeader
        title={workflow?.title || "Workflow Execution"}
        prompt={promptText}
        targetUrl={targetUrl}
        targetApp={workflow?.target_app || workflow?.target?.app || "gitea"}
        runStatus={runStatus}
        elapsedSeconds={elapsedSeconds}
        progressPercent={progressPercent}
        verifiedCount={verifiedCount}
        totalSteps={totalSteps}
      />

      {/* 2. Run Control Action Bar (Cancel Run) */}
      {(runStatus === "running" || runStatus === "paused") && (
        <div
          data-testid="run-controls-bar"
          className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white p-4 shadow-xs dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div className="flex items-center gap-2.5">
            <span
              className={`size-2.5 rounded-full ${
                runStatus === "paused" ? "bg-amber-500" : "animate-pulse bg-indigo-500"
              }`}
            />
            <span className="text-xs font-medium text-zinc-600 sm:text-sm dark:text-zinc-300">
              {runStatus === "paused"
                ? "Execution awaiting human confirmation"
                : "Workflow is actively executing…"}
            </span>
          </div>

          <button
            type="button"
            data-testid="cancel-run-btn"
            disabled={isCancelling}
            onClick={cancel}
            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-50 focus:outline-hidden focus:ring-2 focus:ring-rose-500/50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-rose-900/60 dark:bg-zinc-900 dark:text-rose-400 dark:hover:bg-rose-950/40"
          >
            <svg
              aria-hidden="true"
              className="size-3.5"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            {isCancelling ? "Cancelling…" : "Cancel Run"}
          </button>
        </div>
      )}

      {/* 3. Replan Status Indicator */}
      {replanState.status !== "idle" && (
        <ReplanStatusIndicator
          status={replanState.status}
          attempt={replanState.attempt}
          maxAttempts={replanState.maxAttempts}
          reason={replanState.reason}
          strategy={replanState.strategy}
          timeoutSeconds={replanState.timeoutSeconds}
          onTakeover={resume}
          onResume={resume}
          onAbort={cancel}
        />
      )}

      {/* 4. Lifecycle Interruption Banners */}
      {runStatus === "paused" && pauseDetails && (
        <PauseBanner
          reason={pauseDetails.reason}
          stepSeq={pauseDetails.stepSeq}
          message={pauseDetails.message}
          onResume={resume}
          onDeny={deny}
          isConfirming={isConfirming}
        />
      )}

      {runStatus === "failed" && (
        <FailureBanner
          error={runError}
          failedStep={failedStep}
          workflowId={workflowId}
          onRetry={reset}
        />
      )}

      {/* 5. Detailed Step Verification Failure Diagnostic Card */}
      {failedStep && (
        <VerificationFailureCard
          stepSeq={failedStep.seq}
          instructionText={failedStep.instructionText}
          failureReason={failedStep.error}
          failedLayer={failedStep.failureLayer}
          expected={failedStep.expectedState}
          observed={
            failedStep.observedSummary || {
              url: failedStep.observedUrl || "",
              title: failedStep.observedTitle || "",
              error: failedStep.error,
            }
          }
          expectedScreenshotUrl={failedStep.expectedScreenshotUrl}
          observedScreenshotUrl={failedStep.screenshotUrl}
          onRetryReplan={reset}
        />
      )}

      {runStatus === "cancelled" && (
        <div
          role="status"
          data-testid="cancelled-banner"
          className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-zinc-50 p-4 shadow-xs sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800 dark:bg-zinc-900/60"
        >
          <div className="flex items-start gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
              <svg className="size-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                Workflow Execution Cancelled
              </h3>
              <p className="text-xs text-zinc-600 dark:text-zinc-400">
                The run was halted before all steps could be completed.
              </p>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2 pl-12 sm:pl-0">
            <button
              type="button"
              data-testid="retry-run-btn"
              onClick={reset}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
            >
              Restart Run
            </button>
            <a
              href={`/workflows/${workflowId}/approval`}
              data-testid="back-to-plan-btn"
              className="rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              Back to Plan
            </a>
          </div>
        </div>
      )}

      {runStatus === "completed" && (
        <div
          role="status"
          data-testid="completion-banner"
          className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-900 shadow-xs dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100"
        >
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-900/60 dark:text-emerald-300">
            <svg className="size-5" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          </div>
          <div>
            <div>Workflow Execution Complete!</div>
            <div className="text-xs font-normal text-emerald-800/80 dark:text-emerald-300/80">
              All {totalSteps} steps successfully verified against live system state.
            </div>
          </div>
        </div>
      )}

      {/* 3. Steps List with real-time transition items */}
      <section aria-label="Execution steps" className="flex flex-col gap-3">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Execution Steps ({steps.length})
          </h2>
          <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
            {verifiedCount}/{totalSteps} verified
          </span>
        </div>

        <ol data-testid="execution-step-list" className="flex flex-col gap-3">
          {steps.map((step) => (
            <StepProgressItem
              key={step.seq}
              seq={step.seq}
              instructionText={step.instructionText}
              actionType={step.actionType}
              targetRole={step.targetRole}
              targetName={step.targetName}
              risk={step.risk}
              status={step.status}
              methods={step.methods}
              confidence={step.confidence}
              error={step.error}
              observedUrl={step.observedUrl}
              observedTitle={step.observedTitle}
            />
          ))}
        </ol>
      </section>
    </main>
  );
}
