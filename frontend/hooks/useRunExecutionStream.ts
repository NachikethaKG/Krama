"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ApiError,
  ExpectedState,
  ObservedSummary,
  PauseReason,
  Plan,
  PlannedStep,
  Run,
  RunEvent,
  Task,
} from "@krama/contracts-ts";

import { type ApiClient, type ConfirmDecision, errorMessage, getApiClient, isApiError } from "@/lib/api";
import { artifactUrl } from "@/lib/artifacts";

export type RunExecutionStatus = "idle" | "queued" | "running" | "paused" | "failed" | "completed" | "cancelled";
export type StepStatus = "pending" | "started" | "verified" | "failed";
export type StreamState = "idle" | "connecting" | "open" | "reconnecting" | "closed" | "lost";

/** What the replan indicator shows. Only contract data: `run.replanning` {reason, attempt} and pauses. */
export interface ReplanState {
  status: "idle" | "replanning" | "exhausted";
  attempt: number;
  reason?: string;
}

export interface StepExecutionState {
  seq: number;
  status: StepStatus;
  instructionText: string;
  actionType?: string;
  targetRole?: string | null;
  targetName?: string | null;
  risk?: string | null;
  methods?: string[];
  confidence?: number;
  error?: string;
  observedUrl?: string;
  observedTitle?: string;
  /** Loadable URL of the latest screenshot for this step. */
  screenshotUrl?: string;
  /** Loadable URL of the screenshot taken before this step (the previous step's last one), if any. */
  previousScreenshotUrl?: string;
  expectedState?: ExpectedState;
  observedSummary?: ObservedSummary;
}

export interface PauseDetails {
  reason: PauseReason;
  stepSeq: number;
  message?: string;
  /** replan_review: the plan holding the proposed steps. */
  planId?: string;
}

export interface ProposedPlanState {
  planId: string;
  plan: Plan | null;
  /** The proposed steps from the paused step on (what "allow" will run). */
  steps: PlannedStep[];
  loading: boolean;
  error: string | null;
}

/**
 * A policy STOP (CAPTCHA, bot wall, login wall): the backend ends the run with `run.failed` and
 * `error.details.reason === "policy_stop"`. The run is already failed; there is no resume.
 */
export interface PolicyStopDetails {
  policyReason: string;
  message: string;
  stepSeq: number | null;
}

export interface UseRunExecutionStreamOptions {
  runId: string;
  client?: ApiClient;
  autoStart?: boolean;
  /** Mock replay speed. */
  speed?: number;
  /** Reconnect tuning (tests). */
  reconnectDelayMs?: number;
  maxReconnects?: number;
}

export interface UseRunExecutionStreamResult {
  runStatus: RunExecutionStatus;
  run: Run | null;
  plan: Plan | null;
  task: Task | null;
  steps: StepExecutionState[];
  activeStepSeq: number | null;
  pauseDetails: PauseDetails | null;
  proposedPlan: ProposedPlanState | null;
  policyStop: PolicyStopDetails | null;
  runError: ApiError | null;
  workflowId: string | null;
  replanState: ReplanState;
  elapsedSeconds: number;
  progressPercent: number;
  verifiedCount: number;
  totalSteps: number;
  isLoading: boolean;
  /** The run (or its plan) could not be loaded: nothing else can be shown. */
  loadError: string | null;
  streamState: StreamState;
  isCancelling: boolean;
  isConfirming: boolean;
  /** The latest action/stream error, shown in a banner. */
  error: string | null;
  dismissError: () => void;
  cancel: () => Promise<void>;
  confirm: (decision: ConfirmDecision) => Promise<void>;
  resume: () => Promise<void>;
  deny: () => Promise<void>;
  /** Re-open the event stream after it was lost (resumes from the last seq). */
  reconnect: () => void;
}

const FINAL_STATUSES: ReadonlySet<RunExecutionStatus> = new Set(["completed", "failed", "cancelled"]);

function statusFromRun(status: Run["status"]): RunExecutionStatus {
  return status === "verified" ? "completed" : status;
}

function stepFromPlan(s: PlannedStep): StepExecutionState {
  return {
    seq: s.seq,
    status: "pending",
    instructionText: s.instruction_text,
    actionType: s.action?.type,
    targetRole: s.target?.role,
    targetName: s.target?.name,
    risk: s.risk,
    expectedState: s.expected_state,
  };
}

function statesFromPlan(plan: Plan): Record<number, StepExecutionState> {
  const map: Record<number, StepExecutionState> = {};
  for (const s of plan.steps) map[s.seq] = stepFromPlan(s);
  return map;
}

function failureText(expected: ExpectedState | undefined, observed: ObservedSummary | undefined): string {
  const parts: string[] = [];
  if (expected?.url_matches) parts.push(`URL should match ${expected.url_matches}`);
  if (expected?.title_contains) parts.push(`title should contain "${expected.title_contains}"`);
  if (expected?.visible?.length) {
    parts.push(`should show ${expected.visible.map((e) => `${e.role} "${e.name}"`).join(", ")}`);
  }
  if (expected?.absent?.length) {
    parts.push(`should not show ${expected.absent.map((e) => `${e.role} "${e.name}"`).join(", ")}`);
  }
  const want = parts.length ? parts.join("; ") : "the expected state";
  const got = observed ? ` Observed ${observed.url || "(no URL)"}${observed.title ? ` — "${observed.title}"` : ""}.` : "";
  return `Verification failed: ${want}.${got}`;
}

function policyStopFrom(error: ApiError, fallbackSeq: number | null): PolicyStopDetails | null {
  const details = (error.details ?? {}) as Record<string, unknown>;
  if (details.reason !== "policy_stop") return null;
  const seq = typeof details.step_seq === "number" ? details.step_seq : fallbackSeq;
  return {
    policyReason: typeof details.policy_reason === "string" ? details.policy_reason : "unknown",
    message: error.message,
    stepSeq: seq,
  };
}

export function useRunExecutionStream({
  runId,
  client,
  autoStart = true,
  speed,
  reconnectDelayMs,
  maxReconnects,
}: UseRunExecutionStreamOptions): UseRunExecutionStreamResult {
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [run, setRun] = useState<Run | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [runStatus, setRunStatus] = useState<RunExecutionStatus>("idle");
  const [stepStates, setStepStates] = useState<Record<number, StepExecutionState>>({});
  const [totalSteps, setTotalSteps] = useState(0);
  const [activeStepSeq, setActiveStepSeq] = useState<number | null>(null);
  const [pauseDetails, setPauseDetailsState] = useState<PauseDetails | null>(null);
  const [proposedPlan, setProposedPlanState] = useState<ProposedPlanState | null>(null);
  const [policyStop, setPolicyStop] = useState<PolicyStopDetails | null>(null);
  const [runError, setRunError] = useState<ApiError | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [replanState, setReplanState] = useState<ReplanState>({ status: "idle", attempt: 0 });
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [streamState, setStreamState] = useState<StreamState>("idle");
  const [isCancelling, setIsCancelling] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [timing, setTiming] = useState<{ startTs: number | null; lastTs: number | null; lastAt: number | null; endTs: number | null }>(
    { startTs: null, lastTs: null, lastAt: null, endTs: null },
  );

  const lastSeqRef = useRef(0);
  const finalRef = useRef(false);
  const streamAbortRef = useRef<AbortController | null>(null);
  const streamingRef = useRef(false);
  const pauseRef = useRef<PauseDetails | null>(null);
  const answeredPauseRef = useRef<PauseDetails | null>(null);
  const proposedRef = useRef<ProposedPlanState | null>(null);
  const activeSeqRef = useRef<number | null>(null);
  const confirmBusyRef = useRef(false);
  const cancelBusyRef = useRef(false);
  const mountedRef = useRef(true);

  const setPause = useCallback((p: PauseDetails | null) => {
    pauseRef.current = p;
    setPauseDetailsState(p);
  }, []);
  const setProposed = useCallback((p: ProposedPlanState | null) => {
    proposedRef.current = p;
    setProposedPlanState(p);
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Load run → plan (via run.plan_id) → task (via plan.task_id, optional).
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const loadedRun = await apiClient.getRun(runId);
        if (!active) return;
        setRun(loadedRun);
        setRunStatus((prev) => (prev === "idle" ? statusFromRun(loadedRun.status) : prev));
        if (loadedRun.workflow_id) setWorkflowId(loadedRun.workflow_id);
        const loadedPlan = await apiClient.getPlan(loadedRun.plan_id);
        if (!active) return;
        setPlan(loadedPlan);
        setStepStates((prev) => ({ ...statesFromPlan(loadedPlan), ...prev }));
        setTotalSteps((prev) => prev || loadedPlan.steps.length);
        setIsLoading(false);
        try {
          const loadedTask = await apiClient.getTask(loadedPlan.task_id);
          if (active) setTask(loadedTask);
        } catch {
          // The prompt/target header is optional; the run itself is shown without it.
        }
      } catch (err) {
        if (!active) return;
        setLoadError(errorMessage(err, "Failed to load the run"));
        setIsLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [apiClient, runId]);

  const loadProposedPlan = useCallback(
    (planId: string, fromSeq: number) => {
      setProposed({ planId, plan: null, steps: [], loading: true, error: null });
      apiClient
        .getPlan(planId)
        .then((p) => {
          if (!mountedRef.current || proposedRef.current?.planId !== planId) return;
          setProposed({ planId, plan: p, steps: p.steps.filter((s) => s.seq >= fromSeq), loading: false, error: null });
        })
        .catch((err: unknown) => {
          if (!mountedRef.current || proposedRef.current?.planId !== planId) return;
          setProposed({
            planId,
            plan: null,
            steps: [],
            loading: false,
            error: errorMessage(err, "Could not load the proposed steps"),
          });
        });
    },
    [apiClient, setProposed],
  );

  const handleEvent = useCallback(
    (event: RunEvent) => {
      if (typeof event.seq === "number") {
        if (event.seq <= lastSeqRef.current) return; // already applied (replay after a reconnect)
        lastSeqRef.current = event.seq;
      }
      const ts = Date.parse(event.ts);
      setTiming((prev) => ({
        startTs: prev.startTs ?? (event.type === "run.started" && !Number.isNaN(ts) ? ts : prev.startTs),
        lastTs: Number.isNaN(ts) ? prev.lastTs : ts,
        lastAt: Date.now(),
        endTs:
          (event.type === "run.completed" || event.type === "run.failed" || event.type === "run.cancelled") &&
          !Number.isNaN(ts)
            ? ts
            : prev.endTs,
      }));

      switch (event.type) {
        case "run.started": {
          setRunStatus("running");
          if (event.total_steps) setTotalSteps(event.total_steps);
          break;
        }
        case "step.started": {
          activeSeqRef.current = event.step_seq;
          setActiveStepSeq(event.step_seq);
          setStepStates((prev) => {
            const existing = prev[event.step_seq];
            return {
              ...prev,
              [event.step_seq]: {
                ...(existing ?? { seq: event.step_seq, risk: "low" }),
                seq: event.step_seq,
                status: "started",
                instructionText: event.instruction_text || existing?.instructionText || "",
                error: undefined,
              },
            };
          });
          break;
        }
        case "step.action_done": {
          const url = artifactUrl(event.screenshot_url);
          if (url) {
            setStepStates((prev) => ({
              ...prev,
              [event.step_seq]: { ...prev[event.step_seq], seq: event.step_seq, screenshotUrl: url },
            }));
          }
          break;
        }
        case "step.verified": {
          setStepStates((prev) => ({
            ...prev,
            [event.step_seq]: {
              ...prev[event.step_seq],
              seq: event.step_seq,
              status: "verified",
              methods: event.method,
              confidence: event.confidence,
              error: undefined,
            },
          }));
          setReplanState((prev) => (prev.status === "idle" ? prev : { status: "idle", attempt: prev.attempt }));
          break;
        }
        case "step.failed": {
          const shot = artifactUrl(event.screenshot_url);
          setStepStates((prev) => {
            // "Before" image: the latest screenshot of an earlier step (the contract has no expected screenshot).
            const earlier = Object.values(prev)
              .filter((s) => s.seq < event.step_seq && s.screenshotUrl)
              .sort((a, b) => b.seq - a.seq)[0];
            const previous = earlier?.screenshotUrl;
            const existing = prev[event.step_seq];
            return {
              ...prev,
              [event.step_seq]: {
                ...existing,
                seq: event.step_seq,
                instructionText: existing?.instructionText ?? "",
                status: "failed",
                error: failureText(event.expected, event.observed),
                observedUrl: event.observed?.url,
                observedTitle: event.observed?.title,
                observedSummary: event.observed,
                expectedState: event.expected ?? existing?.expectedState,
                screenshotUrl: shot ?? existing?.screenshotUrl,
                previousScreenshotUrl: previous,
              },
            };
          });
          break;
        }
        case "run.replanning": {
          setReplanState({ status: "replanning", attempt: event.attempt, reason: event.reason });
          break;
        }
        case "run.paused": {
          setRunStatus("paused");
          answeredPauseRef.current = null;
          const pause: PauseDetails = {
            reason: event.reason,
            stepSeq: event.step_seq,
            message: event.message,
            planId: event.plan_id,
          };
          setPause(pause);
          if (event.reason === "replan_review") {
            setReplanState((prev) => ({ ...prev, status: "idle" }));
            if (event.plan_id) {
              loadProposedPlan(event.plan_id, event.step_seq);
            } else {
              setProposed({
                planId: "",
                plan: null,
                steps: [],
                loading: false,
                error: "The pause did not say which plan holds the proposed steps.",
              });
            }
          } else if (event.reason === "recovery_exhausted") {
            setReplanState((prev) => ({
              status: "exhausted",
              attempt: prev.attempt,
              reason: event.message || prev.reason,
            }));
          }
          break;
        }
        case "run.resumed": {
          const pause = pauseRef.current ?? answeredPauseRef.current;
          const proposal = proposedRef.current;
          if (pause?.reason === "replan_review" && proposal?.plan) {
            // The run continues with the proposed steps from the paused step on.
            const from = pause.stepSeq;
            const newSteps = proposal.plan.steps;
            setStepStates((prev) => {
              const next: Record<number, StepExecutionState> = {};
              for (const s of Object.values(prev)) if (s.seq < from) next[s.seq] = s;
              for (const s of newSteps) if (s.seq >= from) next[s.seq] = stepFromPlan(s);
              return next;
            });
            setTotalSteps(newSteps.length);
          }
          answeredPauseRef.current = null;
          setPause(null);
          setProposed(null);
          setRunStatus("running");
          setReplanState((prev) => (prev.status === "exhausted" ? { ...prev, status: "idle" } : prev));
          break;
        }
        case "run.completed": {
          finalRef.current = true;
          setRunStatus("completed");
          setWorkflowId(event.workflow_id);
          activeSeqRef.current = null;
          setActiveStepSeq(null);
          setPause(null);
          setProposed(null);
          setIsCancelling(false);
          break;
        }
        case "run.failed": {
          finalRef.current = true;
          setRunStatus("failed");
          setRunError(event.error);
          setPolicyStop(policyStopFrom(event.error, activeSeqRef.current));
          setPause(null);
          setProposed(null);
          setIsCancelling(false);
          break;
        }
        case "run.cancelled": {
          finalRef.current = true;
          setRunStatus("cancelled");
          activeSeqRef.current = null;
          setActiveStepSeq(null);
          setPause(null);
          setProposed(null);
          setIsCancelling(false);
          break;
        }
        default:
          // Unknown event types are ignored: the UI only relies on contract events.
          break;
      }
    },
    [loadProposedPlan, setPause, setProposed],
  );

  const startStream = useCallback(async () => {
    if (streamingRef.current || finalRef.current) return; // never re-stream a finished run
    streamingRef.current = true;
    streamAbortRef.current?.abort();
    const controller = new AbortController();
    streamAbortRef.current = controller;
    setStreamState("connecting");
    try {
      const stream = apiClient.streamRunEvents(runId, {
        signal: controller.signal,
        lastEventId: lastSeqRef.current,
        speed,
        reconnectDelayMs,
        maxReconnects,
        onReconnect: () => {
          if (!controller.signal.aborted) setStreamState("reconnecting");
        },
      });
      for await (const event of stream) {
        if (controller.signal.aborted) break;
        setStreamState("open");
        handleEvent(event);
      }
      if (!controller.signal.aborted) setStreamState("closed");
    } catch (err) {
      if (controller.signal.aborted || (err instanceof DOMException && err.name === "AbortError")) return;
      setStreamState("lost");
      setError(errorMessage(err, "Lost the live event stream"));
    } finally {
      if (streamAbortRef.current === controller) streamingRef.current = false;
    }
  }, [apiClient, handleEvent, maxReconnects, reconnectDelayMs, runId, speed]);

  // Start streaming once the plan (the step list) is loaded.
  useEffect(() => {
    if (!autoStart || isLoading || loadError) return;
    const timer = setTimeout(() => void startStream(), 0);
    return () => {
      clearTimeout(timer);
      streamAbortRef.current?.abort();
      streamingRef.current = false;
    };
  }, [autoStart, isLoading, loadError, startStream]);

  // Clock tick while the run is live.
  const isLive = runStatus === "running" || runStatus === "paused" || runStatus === "queued";
  useEffect(() => {
    if (!isLive) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [isLive]);

  const reconnect = useCallback(() => {
    if (finalRef.current) return;
    setError(null);
    void startStream();
  }, [startStream]);

  const cancel = useCallback(async () => {
    if (cancelBusyRef.current || finalRef.current) return;
    cancelBusyRef.current = true;
    setIsCancelling(true);
    setError(null);
    try {
      const updated = await apiClient.cancelRun(runId);
      if (!mountedRef.current) return;
      setRun(updated);
      // The server's answer is authoritative. While the run is still stopping, "Cancelling…" stays until the
      // stream delivers run.cancelled.
      const status = statusFromRun(updated.status);
      if (FINAL_STATUSES.has(status)) {
        setRunStatus(status);
        setPause(null);
        setProposed(null);
        setIsCancelling(false);
      }
    } catch (err) {
      if (!mountedRef.current) return;
      setIsCancelling(false);
      if (isApiError(err, "run_not_active")) {
        setError("The run has already finished, so it can't be cancelled.");
      } else {
        setError(errorMessage(err, "Failed to cancel the run"));
      }
    } finally {
      cancelBusyRef.current = false;
    }
  }, [apiClient, runId, setPause, setProposed]);

  const confirm = useCallback(
    async (decision: ConfirmDecision) => {
      const pause = pauseRef.current;
      if (!pause || confirmBusyRef.current) return;
      if (decision === "allow" && pause.reason === "replan_review" && !proposedRef.current?.plan) {
        setError("The proposed steps are not loaded yet, so they can't be allowed. Deny cancels the run.");
        return;
      }
      confirmBusyRef.current = true;
      setIsConfirming(true);
      setError(null);
      try {
        const updated = await apiClient.confirmRun(runId, pause.stepSeq, decision);
        if (!mountedRef.current) return;
        setRun(updated);
        // The server accepted the answer. Hide this pause's control unless a newer pause already replaced it.
        if (pauseRef.current === pause) {
          answeredPauseRef.current = pause;
          setPause(null);
          if (decision === "deny") setProposed(null);
          const status = statusFromRun(updated.status);
          if (!finalRef.current) setRunStatus(status === "paused" ? "running" : status);
        }
      } catch (err) {
        if (!mountedRef.current) return;
        if (isApiError(err, "run_not_active")) {
          setError(`The run is no longer waiting for an answer at step ${pause.stepSeq}. ${errorMessage(err)}`);
        } else {
          setError(errorMessage(err, `Failed to send "${decision}"`));
        }
      } finally {
        confirmBusyRef.current = false;
        if (mountedRef.current) setIsConfirming(false);
      }
    },
    [apiClient, runId, setPause, setProposed],
  );

  const resume = useCallback(() => confirm("allow"), [confirm]);
  const deny = useCallback(() => confirm("deny"), [confirm]);
  const dismissError = useCallback(() => setError(null), []);

  const steps = Object.values(stepStates).sort((a, b) => a.seq - b.seq);
  const verifiedCount = steps.filter((s) => s.status === "verified").length;
  const denominator = totalSteps > 0 ? totalSteps : steps.length;
  const progressPercent =
    runStatus === "completed" ? 100 : denominator > 0 ? Math.round((verifiedCount / denominator) * 100) : 0;

  // Elapsed = event time between run.started and the last event, plus wall time since then while live.
  let elapsedMs = 0;
  if (timing.startTs !== null) {
    const end = timing.endTs ?? timing.lastTs ?? timing.startTs;
    elapsedMs = end - timing.startTs;
    if (timing.endTs === null && isLive && timing.lastAt !== null) elapsedMs += Math.max(0, now - timing.lastAt);
  } else if (run?.started_at) {
    const start = Date.parse(run.started_at);
    const end = run.finished_at ? Date.parse(run.finished_at) : now;
    elapsedMs = end - start;
  }
  const elapsedSeconds = Math.max(0, Math.floor(elapsedMs / 1000));

  return {
    runStatus,
    run,
    plan,
    task,
    steps,
    activeStepSeq,
    pauseDetails,
    proposedPlan,
    policyStop,
    runError,
    workflowId,
    replanState,
    elapsedSeconds,
    progressPercent,
    verifiedCount,
    totalSteps: denominator,
    isLoading,
    loadError,
    streamState,
    isCancelling,
    isConfirming,
    error,
    dismissError,
    cancel,
    confirm,
    resume,
    deny,
    reconnect,
  };
}
