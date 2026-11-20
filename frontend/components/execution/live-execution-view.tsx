"use client";

import Link from "next/link";
import { useState } from "react";
import type { PauseReason } from "@krama/contracts-ts";

import { VerificationFailureCard } from "@/components/diagnostics";
import { ExecutionHeader } from "@/components/execution/execution-header";
import { FailureBanner } from "@/components/execution/failure-banner";
import { PauseBanner } from "@/components/execution/pause-banner";
import { ReplanStatusIndicator } from "@/components/execution/ReplanStatusIndicator";
import { StepProgressItem } from "@/components/execution/step-progress-item";
import { TakeoverViewer } from "@/components/execution/takeover-viewer";
import { RiskBadge } from "@/components/risk-badge";
import { AutomationRestrictedScreen, PolicyConfirmationModal } from "@/components/safety";
import { type ProposedPlanState, useRunExecutionStream } from "@/hooks/useRunExecutionStream";
import { type ApiClient, errorMessage, getApiClient } from "@/lib/api";

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
      <p data-testid="proposed-steps-loading" className="text-xs text-ink-300">
        Loading the proposed steps…
      </p>
    );
  }
  if (proposal.error) {
    return (
      <p data-testid="proposed-steps-error" role="alert" className="text-xs font-semibold text-danger">
        {proposal.error} Allow is disabled; deny cancels the run.
      </p>
    );
  }
  return (
    <div data-testid="proposed-steps" className="rounded-2xl border border-approve/40 bg-ink-950/60 p-3">
      <h4 className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-approve">
        Proposed remaining steps ({proposal.steps.length})
      </h4>
      <ol className="flex flex-col gap-2">
        {proposal.steps.map((s) => (
          <li
            key={s.seq}
            data-testid="proposed-step-item"
            data-step-seq={s.seq}
            className="flex items-start justify-between gap-3 text-xs text-ink-300"
          >
            <span className="flex items-start gap-2">
              <span className="rounded-md bg-approve/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-approve">
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
    takeover,
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
  const api = client ?? getApiClient();
  const [watching, setWatching] = useState(false);
  const [takeoverError, setTakeoverError] = useState<string | null>(null);
  const startTakeover = async () => {
    setTakeoverError(null);
    try {
      await api.startTakeover(runId);
      setWatching(true);
    } catch (err) {
      setTakeoverError(errorMessage(err, "The page can't be taken over right now."));
    }
  };

  if (isLoading) {
    return (
      <main
        data-testid="live-execution-loading"
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-3 px-4 py-20 text-center"
      >
        <div className="size-12 animate-spin rounded-full border-4 border-white/10 border-t-run shadow-[0_0_30px_-4px_var(--run)]" />
        <p className="font-mono text-sm text-run">Loading the run…</p>
      </main>
    );
  }

  if (loadError) {
    return (
      <main
        data-testid="live-execution-error"
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col items-center justify-center gap-4 px-4 py-20 text-center"
      >
        <h1 className="kr-display text-4xl font-extrabold text-white">Run Not Found</h1>
        <p className="max-w-md text-sm text-ink-300">{loadError}</p>
        <Link href="/" className="kr-btn kr-btn-primary px-5 py-2 text-sm">
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
          className="kr-danger kr-tone-card flex flex-col gap-3 rounded-2xl p-4 text-sm text-white sm:flex-row sm:items-center sm:justify-between"
        >
          <span data-testid="execution-error-message">{error}</span>
          <div className="flex shrink-0 items-center gap-2">
            {streamState === "lost" && isLive && (
              <button
                type="button"
                data-testid="reconnect-stream-btn"
                onClick={reconnect}
                className="kr-btn kr-btn-tone px-3 py-1.5 text-xs"
              >
                Reconnect
              </button>
            )}
            <button
              type="button"
              data-testid="dismiss-error-btn"
              onClick={dismissError}
              className="text-xs text-ink-300 underline hover:text-white"
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
          className="kr-plan kr-tone-card rounded-2xl p-3 text-xs text-ink-300"
        >
          Connection to the live view dropped. Reconnecting and resuming from the last event…
        </div>
      )}

      {isLive && (
        <div
          data-testid="run-controls-bar"
          className="kr-glass flex items-center justify-between rounded-2xl p-4"
        >
          <div className="flex items-center gap-2.5">
            <span
              className={`kr-dot kr-dot-live ${runStatus === "paused" ? "kr-plan" : "kr-run"}`}
            />
            <span className="text-xs font-semibold text-ink-300 sm:text-sm">
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
            className="kr-btn kr-btn-ghost kr-danger px-3.5 py-1.5 text-xs text-danger"
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
          {pauseDetails.takeoverAvailable && !watching && !takeover.active ? (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                data-testid="take-over-btn"
                onClick={startTakeover}
                className="kr-btn kr-btn-tone px-3.5 py-1.5 text-xs"
              >
                Take over the page
              </button>
              <span className="text-xs text-ink-300">Do it yourself in Krama&apos;s browser, then hand it back.</span>
              {takeoverError ? (
                <span role="alert" data-testid="take-over-error" className="text-xs font-semibold text-danger">
                  {takeoverError}
                </span>
              ) : null}
            </div>
          ) : null}
        </PauseBanner>
      )}

      {watching && pauseDetails && runStatus === "paused" && (
        <TakeoverViewer runId={runId} stepSeq={pauseDetails.stepSeq} client={api} onEnded={() => setWatching(false)} />
      )}

      {runStatus === "failed" && !policyStop && (
        <FailureBanner
          error={runError}
          failedStep={failedStep}
          planId={planId}
          doIt={
            run?.kind === "do_it"
              ? {
                  done: steps.filter((s) => s.status === "verified").length,
                  total: steps.length,
                  planFreshHref: `/?prompt=${encodeURIComponent(plan?.expected_result ?? "")}`,
                }
              : undefined
          }
        />
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
          className="kr-glass flex flex-col gap-4 rounded-2xl p-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <h3 className="kr-display text-lg font-bold text-white">Workflow Execution Cancelled</h3>
            <p className="text-xs text-ink-400">
              The run was halted before all steps could be completed.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {planId && (
              <a
                href={`/workflows/${planId}/approval`}
                data-testid="back-to-plan-btn"
                className="kr-btn kr-btn-ghost kr-approve px-3 py-1.5 text-xs"
              >
                Back to Plan
              </a>
            )}
            <Link
              href="/"
              data-testid="new-task-link"
              className="kr-btn kr-btn-primary px-3.5 py-1.5 text-xs"
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
          className="kr-spectrum-border kr-verify flex flex-col gap-3 rounded-3xl bg-ink-900/85 p-5 text-sm font-semibold text-white sm:flex-row sm:items-center sm:justify-between"
        >
          <div>
            <div className="kr-display kr-gradient-text text-2xl font-extrabold">Tutorial ready</div>
            <div className="text-xs font-normal text-ink-300">
              {totalSteps} verified {totalSteps === 1 ? "step" : "steps"} · 0 failed actions · 0 unresolved states
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            {/* The point of a verified run: the tutorial built from it (#83 newcomer test). */}
            {workflowId && (
              <a
                href={`/tutorials/${workflowId}`}
                data-testid="watch-tutorial-link"
                className="kr-btn kr-btn-primary px-4 py-2 text-xs"
              >
                &#9654; Start tutorial
              </a>
            )}
            <a
              href={`/runs/${runId}`}
              data-testid="view-workflow-link"
              className="kr-btn kr-btn-tone kr-verify px-4 py-2 text-xs"
            >
              See each step&apos;s checks &rarr;
            </a>
          </div>
        </div>
      )}

      <section aria-label="Execution steps" className="flex flex-col gap-3">
        <div className="flex items-center justify-between px-1">
          <h2 className="kr-display text-xl font-bold text-white">Execution Steps ({steps.length})</h2>
          <span className="kr-chip kr-verify">
            {verifiedCount}/{totalSteps} verified
          </span>
        </div>

        <div className="relative">
          {/* the level map: a spectrum rail every step node hangs on */}
          <div
            aria-hidden="true"
            className="absolute bottom-4 left-[1.85rem] top-4 w-[3px] rounded-full opacity-60"
            style={{ background: "linear-gradient(var(--run), var(--approve), var(--verify), var(--learn))" }}
          />
          <ol data-testid="execution-step-list" className="relative flex flex-col gap-3">
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
        </div>
      </section>
    </main>
  );
}
