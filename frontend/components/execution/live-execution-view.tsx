"use client";

import Link from "next/link";
import type { PauseReason } from "@krama/contracts-ts";

import { VerificationFailureCard } from "@/components/diagnostics";
import { ExecutionHeader } from "@/components/execution/execution-header";
import { FailureBanner } from "@/components/execution/failure-banner";
import { PauseBanner } from "@/components/execution/pause-banner";
import { ReplanStatusIndicator } from "@/components/execution/ReplanStatusIndicator";
import { StepProgressItem } from "@/components/execution/step-progress-item";
import { RiskBadge } from "@/components/risk-badge";
import { AutomationRestrictedScreen, PolicyConfirmationModal } from "@/components/safety";
import { type ProposedPlanState, useRunExecutionStream } from "@/hooks/useRunExecutionStream";
import type { ApiClient } from "@/lib/api";

/** Pauses the safety policy raises before an action: confirmed in the modal. Every other pause uses the banner. */
const MODAL_REASONS: ReadonlySet<PauseReason> = new Set(["destructive_action", "sensitive_data", "prompt_injection"]);

export interface LiveExecutionViewProps {
  /** The RUN id (POST /plans/{id}/approve returns the Run). */
  runId: string;
  speed?: number;
  client?: ApiClient;
  className?: string;
}

function ProposedSteps({ proposal }: { proposal: ProposedPlanState | null }) {
  if (!proposal || proposal.loading) {
    return (
      <p data-testid="proposed-steps-loading" className="text-xs text-amber-900 dark:text-amber-200">
        Loading the proposed steps…
      </p>
    );
  }
  if (proposal.error) {
    return (
      <p data-testid="proposed-steps-error" role="alert" className="text-xs font-medium text-rose-700 dark:text-rose-300">
        {proposal.error} Allow is disabled; deny cancels the run.
      </p>
    );
  }
  return (
    <div data-testid="proposed-steps" className="rounded-lg border border-amber-200 bg-white p-3 dark:border-amber-900/60 dark:bg-zinc-900">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-amber-900 dark:text-amber-200">
        Proposed remaining steps ({proposal.steps.length})
      </h4>
      <ol className="flex flex-col gap-2">
        {proposal.steps.map((s) => (
          <li
            key={s.seq}
            data-testid="proposed-step-item"
            data-step-seq={s.seq}
            className="flex items-start justify-between gap-3 text-xs text-zinc-800 dark:text-zinc-200"
          >
            <span className="flex items-start gap-2">
              <span className="rounded bg-amber-100 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-amber-900 dark:bg-amber-900/60 dark:text-amber-100">
                {s.seq}
              </span>
              <span>{s.instruction_text}</span>
            </span>
            <RiskBadge level={s.risk} size="sm" />
          </li>
        ))}
      </ol>
    </div>
  );
}

export function LiveExecutionView({ runId, speed, client, className = "" }: LiveExecutionViewProps) {
  const {
    runStatus,
    run,
    plan,
    task,
    steps,
    pauseDetails,
    proposedPlan,
    policyStop,
    runError,
    replanState,
    elapsedSeconds,
    progressPercent,
    verifiedCount,
    totalSteps,
    workflowId,
    isLoading,
    loadError,
    streamState,
    isCancelling,
    isConfirming,
    error,
    dismissError,
    cancel,
    resume,
    deny,
    reconnect,
  } = useRunExecutionStream({ runId, client, speed });

  if (isLoading) {
    return (
      <main
        data-testid="live-execution-loading"
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-3 px-4 py-20 text-center"
      >
        <div className="size-8 animate-spin rounded-full border-2 border-indigo-300 border-t-indigo-600 dark:border-indigo-800 dark:border-t-indigo-400" />
        <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">Loading the run…</p>
      </main>
    );
  }

  if (loadError) {
    return (
      <main
        data-testid="live-execution-error"
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20 text-center"
      >
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Run Not Found</h1>
        <p className="max-w-md text-sm text-zinc-600 dark:text-zinc-400">{loadError}</p>
        <Link href="/" className="text-sm font-semibold text-indigo-600 underline dark:text-indigo-400">
          Start a new task
        </Link>
      </main>
    );
  }

  const planId = run?.plan_id ?? plan?.id;
  const failedStep = steps.find((s) => s.status === "failed");
  const pausedStep = pauseDetails ? steps.find((s) => s.seq === pauseDetails.stepSeq) : undefined;
  const useModal = runStatus === "paused" && pauseDetails !== null && MODAL_REASONS.has(pauseDetails.reason);
  const useBanner = runStatus === "paused" && pauseDetails !== null && !useModal;
  const isLive = runStatus === "running" || runStatus === "paused" || runStatus === "queued";

  return (
    <main
      data-testid="live-execution-view"
      data-run-id={runId}
      className={`mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-4 py-8 sm:py-12 ${className}`}
    >
      <ExecutionHeader
        title={plan?.expected_result ? `Goal: ${plan.expected_result}` : "Doing the task"}
        prompt={task?.prompt}
        targetUrl={task?.target_url}
        targetApp={task?.interpretation?.app}
        runStatus={runStatus}
        elapsedSeconds={elapsedSeconds}
        progressPercent={progressPercent}
        verifiedCount={verifiedCount}
        totalSteps={totalSteps}
      />

      {/* Errors from the stream or from cancel/confirm are always visible, even after the run loaded. */}
      {error && (
        <div
          role="alert"
          data-testid="execution-error-banner"
          className="flex flex-col gap-3 rounded-xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-900 sm:flex-row sm:items-center sm:justify-between dark:border-rose-900/80 dark:bg-rose-950/40 dark:text-rose-200"
        >
          <span data-testid="execution-error-message">{error}</span>
          <div className="flex shrink-0 items-center gap-2">
            {streamState === "lost" && isLive && (
              <button
                type="button"
                data-testid="reconnect-stream-btn"
                onClick={reconnect}
                className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-500"
              >
                Reconnect
              </button>
            )}
            <button
              type="button"
              data-testid="dismiss-error-btn"
              onClick={dismissError}
              className="text-xs text-rose-700 underline hover:text-rose-900 dark:text-rose-300"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {streamState === "reconnecting" && (
        <div
          role="status"
          data-testid="stream-reconnecting"
          className="rounded-xl border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
        >
          Connection to the live view dropped. Reconnecting and resuming from the last event…
        </div>
      )}

      {isLive && (
        <div
          data-testid="run-controls-bar"
          className="flex items-center justify-between rounded-xl border border-zinc-200 bg-white p-4 shadow-xs dark:border-zinc-800 dark:bg-zinc-900"
        >
          <div className="flex items-center gap-2.5">
            <span
              className={`size-2.5 rounded-full ${runStatus === "paused" ? "bg-amber-500" : "animate-pulse bg-indigo-500"}`}
            />
            <span className="text-xs font-medium text-zinc-600 sm:text-sm dark:text-zinc-300">
              {runStatus === "paused"
                ? "Waiting for you to confirm a step"
                : runStatus === "queued"
                  ? "Waiting for the run to start…"
                  : "Workflow is actively executing…"}
            </span>
          </div>

          <button
            type="button"
            data-testid="cancel-run-btn"
            disabled={isCancelling || isConfirming}
            onClick={cancel}
            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-50 focus:outline-hidden focus:ring-2 focus:ring-rose-500/50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-rose-900/60 dark:bg-zinc-900 dark:text-rose-400 dark:hover:bg-rose-950/40"
          >
            {isCancelling ? "Cancelling…" : "Cancel Run"}
          </button>
        </div>
      )}

      {/* Recovery status: information only. Decisions go through the single pause control below. */}
      {replanState.status !== "idle" && isLive && (
        <ReplanStatusIndicator status={replanState.status} attempt={replanState.attempt} reason={replanState.reason} />
      )}

      {/* Policy STOP (CAPTCHA / bot wall / login wall): the run already failed; the user takes over manually. */}
      {policyStop && (
        <AutomationRestrictedScreen
          barrierType={policyStop.policyReason}
          message={policyStop.message}
          targetUrl={task?.target_url}
          stepSeq={policyStop.stepSeq}
          runHref={`/runs/${runId}`}
        />
      )}

      {/* ONE confirmation control per pause: the modal for policy pauses, the banner for everything else. */}
      {useModal && pauseDetails && (
        <PolicyConfirmationModal
          isOpen={true}
          stepSeq={pauseDetails.stepSeq}
          stepInstruction={pausedStep?.instructionText || pauseDetails.message || "Execute the paused step"}
          actionType={pausedStep?.actionType}
          targetRole={pausedStep?.targetRole}
          targetName={pausedStep?.targetName}
          risk={pausedStep?.risk || "high"}
          reason={pauseDetails.reason}
          rationale={pauseDetails.message}
          onAllow={resume}
          onDeny={deny}
          isConfirming={isConfirming}
        />
      )}

      {useBanner && pauseDetails && (
        <PauseBanner
          reason={pauseDetails.reason}
          stepSeq={pauseDetails.stepSeq}
          message={pauseDetails.message}
          onResume={resume}
          onDeny={deny}
          isConfirming={isConfirming}
          allowDisabled={pauseDetails.reason === "replan_review" && !proposedPlan?.plan}
        >
          {pauseDetails.reason === "replan_review" ? <ProposedSteps proposal={proposedPlan} /> : null}
        </PauseBanner>
      )}

      {runStatus === "failed" && !policyStop && (
        <FailureBanner error={runError} failedStep={failedStep} planId={planId} />
      )}

      {failedStep && (
        <VerificationFailureCard
          stepSeq={failedStep.seq}
          instructionText={failedStep.instructionText}
          failureReason={failedStep.error}
          expected={failedStep.expectedState}
          observed={failedStep.observedSummary || { url: failedStep.observedUrl || "", title: failedStep.observedTitle || "" }}
          previousScreenshotUrl={failedStep.previousScreenshotUrl}
          observedScreenshotUrl={failedStep.screenshotUrl}
        />
      )}

      {runStatus === "cancelled" && (
        <div
          role="status"
          data-testid="cancelled-banner"
          className="flex flex-col gap-4 rounded-xl border border-zinc-200 bg-zinc-50 p-4 shadow-xs sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800 dark:bg-zinc-900/60"
        >
          <div>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Workflow Execution Cancelled</h3>
            <p className="text-xs text-zinc-600 dark:text-zinc-400">
              The run was halted before all steps could be completed.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {planId && (
              <a
                href={`/workflows/${planId}/approval`}
                data-testid="back-to-plan-btn"
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
              >
                Back to Plan
              </a>
            )}
            <Link
              href="/"
              data-testid="new-task-link"
              className="rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              New Task
            </Link>
          </div>
        </div>
      )}

      {runStatus === "completed" && (
        <div
          role="status"
          data-testid="completion-banner"
          className="flex flex-col gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-900 shadow-xs sm:flex-row sm:items-center sm:justify-between dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-100"
        >
          <div>
            <div>Tutorial ready</div>
            <div className="text-xs font-normal text-emerald-800/80 dark:text-emerald-300/80">
              {totalSteps} verified {totalSteps === 1 ? "step" : "steps"} · 0 failed actions · 0 unresolved states
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            {/* The point of a verified run: the tutorial built from it (#83 newcomer test). */}
            {workflowId && (
              <a
                href={`/tutorials/${workflowId}`}
                data-testid="watch-tutorial-link"
                className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500"
              >
                &#9654; Start tutorial
              </a>
            )}
            <a
              href={`/runs/${runId}`}
              data-testid="view-workflow-link"
              className="rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500"
            >
              See each step&apos;s checks &rarr;
            </a>
          </div>
        </div>
      )}

      <section aria-label="Execution steps" className="flex flex-col gap-3">
        <div className="flex items-center justify-between px-1">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">Execution Steps ({steps.length})</h2>
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
