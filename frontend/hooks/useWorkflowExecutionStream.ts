"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ApiError,
  ExpectedState,
  ObservedSummary,
  PauseReason,
  RunEvent,
  Step,
  Workflow,
} from "@krama/contracts-ts";

import { type ApiClient, getApiClient } from "@/lib/api";

export type RunExecutionStatus =
  | "idle"
  | "running"
  | "paused"
  | "failed"
  | "completed"
  | "cancelled"
  | "stopped";
export type StepStatus = "pending" | "started" | "verified" | "failed";
export type ReplanStatus =
  | "idle"
  | "re-locating"
  | "retrying"
  | "replanning"
  | "exhausted"
  | "succeeded";

export interface BarrierDetails {
  barrierType: string;
  reason?: string;
  message?: string;
  targetUrl?: string;
  stepSeq?: number | null;
}

export interface ReplanState {
  status: ReplanStatus;
  attempt: number;
  maxAttempts: number;
  reason?: string;
  strategy?: string;
  timeoutSeconds?: number;
  stepSeq?: number;
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
  screenshotUrl?: string;
  expectedScreenshotUrl?: string;
  expectedState?: ExpectedState;
  observedSummary?: ObservedSummary;
  failureLayer?: string;
}

interface ExtendedStepFailedEvent {
  expected_screenshot_url?: string;
  expectedScreenshotUrl?: string;
  error?: string;
  failure_layer?: string;
  failureLayer?: string;
}

interface ExtendedStep {
  expected_screenshot_url?: string;
  expectedScreenshotUrl?: string;
}

interface ExtendedReplanningEvent {
  status?: ReplanStatus;
  max_attempts?: number;
  strategy?: string;
  timeout_seconds?: number;
  step_seq?: number;
  reason?: string;
  attempt?: number;
}

interface ExtendedCustomEvent {
  type?: string;
  attempt?: number;
  max_attempts?: number;
  status?: ReplanStatus;
  reason?: string;
  strategy?: string;
  timeout_seconds?: number;
  step_seq?: number;
}

export interface PauseDetails {
  reason: PauseReason;
  stepSeq: number;
  message?: string;
}

export interface UseWorkflowExecutionStreamOptions {
  workflowId: string;
  client?: ApiClient;
  autoStart?: boolean;
  speed?: number;
  initialWorkflow?: Workflow;
}

export interface UseWorkflowExecutionStreamResult {
  runStatus: RunExecutionStatus;
  workflow: Workflow | null;
  steps: StepExecutionState[];
  stepStates: Record<number, StepExecutionState>;
  activeStepSeq: number | null;
  pauseDetails: PauseDetails | null;
  barrierDetails: BarrierDetails | null;
  runError: ApiError | null;
  replanState: ReplanState;
  elapsedSeconds: number;
  progressPercent: number;
  verifiedCount: number;
  totalSteps: number;
  isLoading: boolean;
  isCancelling: boolean;
  isConfirming: boolean;
  error: string | null;
  start: () => void;
  cancel: () => Promise<void>;
  confirm: (decision: "allow" | "deny") => Promise<void>;
  resume: () => void;
  deny: () => void;
  reset: () => void;
}


function buildInitialStepStates(wf?: Workflow | null): {
  states: Record<number, StepExecutionState>;
  total: number;
} {
  if (!wf) return { states: {}, total: 0 };
  const map: Record<number, StepExecutionState> = {};
  const stepsList = wf.steps || [];
  stepsList.forEach((s: Step) => {
    map[s.seq] = {
      seq: s.seq,
      status: "pending",
      instructionText: s.instruction_text,
      actionType: s.action?.type,
      targetRole: s.target?.role,
      targetName: s.target?.name,
      risk: s.risk,
    };
  });
  return { states: map, total: stepsList.length };
}

export function useWorkflowExecutionStream({
  workflowId,
  client,
  autoStart = true,
  speed,
  initialWorkflow,
}: UseWorkflowExecutionStreamOptions): UseWorkflowExecutionStreamResult {
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [workflow, setWorkflow] = useState<Workflow | null>(initialWorkflow ?? null);
  const [runStatus, setRunStatus] = useState<RunExecutionStatus>("idle");
  const [activeStepSeq, setActiveStepSeq] = useState<number | null>(null);
  const [pauseDetails, setPauseDetails] = useState<PauseDetails | null>(null);
  const [barrierDetails, setBarrierDetails] = useState<BarrierDetails | null>(null);
  const [runError, setRunError] = useState<ApiError | null>(null);
  const [replanState, setReplanState] = useState<ReplanState>({
    status: "idle",
    attempt: 0,
    maxAttempts: 3,
  });
  const [stepStates, setStepStates] = useState<Record<number, StepExecutionState>>(
    () => buildInitialStepStates(initialWorkflow).states
  );
  const [totalSteps, setTotalSteps] = useState<number>(
    () => buildInitialStepStates(initialWorkflow).total
  );
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(!initialWorkflow);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [isConfirming, setIsConfirming] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const isStreamingRef = useRef<boolean>(false);
  const workflowRef = useRef<Workflow | null>(workflow);
  const activeStepSeqRef = useRef<number | null>(activeStepSeq);
  useEffect(() => {
    workflowRef.current = workflow;
  }, [workflow]);
  useEffect(() => {
    activeStepSeqRef.current = activeStepSeq;
  }, [activeStepSeq]);

  // Fetch workflow details if not supplied
  useEffect(() => {
    if (initialWorkflow) {
      return;
    }

    let isMounted = true;

    apiClient
      .getWorkflow(workflowId)
      .then((data) => {
        if (isMounted) {
          setWorkflow(data);
          const { states, total } = buildInitialStepStates(data);
          setStepStates(states);
          setTotalSteps(total);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load workflow");
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [apiClient, initialWorkflow, workflowId]);

  // Live timer tick
  useEffect(() => {
    if (runStatus === "running") {
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [runStatus]);

  const handleEvent = useCallback((event: RunEvent) => {
    switch (event.type) {
      case "run.started": {
        setRunStatus("running");
        if (event.total_steps) {
          setTotalSteps(event.total_steps);
        }
        break;
      }

      case "step.started": {
        const wfStep = workflowRef.current?.steps?.find((s) => s.seq === event.step_seq);
        setActiveStepSeq(event.step_seq);
        setStepStates((prev) => ({
          ...prev,
          [event.step_seq]: {
            ...(prev[event.step_seq] ?? {
              seq: event.step_seq,
              risk: wfStep?.risk || "low",
            }),
            seq: event.step_seq,
            status: "started",
            instructionText: event.instruction_text || prev[event.step_seq]?.instructionText || "",
            risk: prev[event.step_seq]?.risk || wfStep?.risk || "low",
          },
        }));
        break;
      }

      case "step.action_done": {
        if (event.screenshot_url) {
          setStepStates((prev) => ({
            ...prev,
            [event.step_seq]: {
              ...prev[event.step_seq],
              screenshotUrl: event.screenshot_url ?? undefined,
            },
          }));
        }
        break;
      }

      case "step.verified": {
        setStepStates((prev) => ({
          ...prev,
          [event.step_seq]: {
            ...prev[event.step_seq],
            status: "verified",
            methods: event.method,
            confidence: event.confidence,
          },
        }));
        break;
      }

      case "step.failed": {
        const wfStep = workflowRef.current?.steps?.find((s) => s.seq === event.step_seq);
        const extEvent = event as unknown as ExtendedStepFailedEvent;
        const extStep = wfStep as unknown as ExtendedStep | undefined;
        const expectedScreenshotUrl =
          extEvent.expected_screenshot_url ||
          extEvent.expectedScreenshotUrl ||
          extStep?.expected_screenshot_url ||
          extStep?.expectedScreenshotUrl ||
          wfStep?.before_state?.screenshot ||
          wfStep?.before_state?.screenshot_path;

        setStepStates((prev) => ({
          ...prev,
          [event.step_seq]: {
            ...prev[event.step_seq],
            status: "failed",
            error:
              extEvent.error ||
              "Verification failed: observed state did not match expected preconditions.",
            observedUrl: event.observed?.url,
            observedTitle: event.observed?.title,
            screenshotUrl: event.screenshot_url ?? prev[event.step_seq]?.screenshotUrl ?? undefined,
            expectedScreenshotUrl:
              expectedScreenshotUrl ?? prev[event.step_seq]?.expectedScreenshotUrl ?? undefined,
            expectedState:
              event.expected ?? prev[event.step_seq]?.expectedState ?? wfStep?.expected_state,
            observedSummary: event.observed ?? prev[event.step_seq]?.observedSummary,
            failureLayer:
              extEvent.failure_layer ||
              extEvent.failureLayer ||
              prev[event.step_seq]?.failureLayer,
          },
        }));
        break;
      }

      case "run.replanning": {
        const extEvent = event as unknown as ExtendedReplanningEvent;
        const status: ReplanStatus = extEvent.status || "replanning";
        const maxAttempts = extEvent.max_attempts || 3;
        setReplanState({
          status,
          attempt: event.attempt,
          maxAttempts,
          reason: event.reason,
          strategy:
            extEvent.strategy ||
            "Adaptive element re-location & alternative branch replay",
          timeoutSeconds: extEvent.timeout_seconds ?? 30,
          stepSeq: extEvent.step_seq,
        });
        break;
      }

      case "run.paused": {
        setRunStatus("paused");
        setPauseDetails({
          reason: event.reason,
          stepSeq: event.step_seq,
          message: event.message,
        });
        if (event.reason === "captcha" || event.reason === "auth_wall") {
          setBarrierDetails({
            barrierType: event.reason,
            reason: event.reason,
            message:
              event.message ||
              (event.reason === "captcha"
                ? "A bot detection or CAPTCHA was encountered and requires human intervention."
                : "An authentication barrier was reached and requires manual sign-in."),
            targetUrl: workflowRef.current?.target_url || "http://localhost:3001",
            stepSeq: event.step_seq,
          });
        }
        if (event.reason === "recovery_exhausted") {
          setReplanState((prev) => ({
            ...prev,
            status: "exhausted",
            reason: event.message || prev.reason || "Recovery budget exhausted across all attempts",
          }));
        } else if (event.reason === "replan_review") {
          setReplanState((prev) => ({
            ...prev,
            status: "exhausted",
            reason: event.message || "Replan requires human review before proceeding",
          }));
        }
        break;
      }

      case "run.resumed": {
        setRunStatus("running");
        setPauseDetails(null);
        setBarrierDetails(null);
        setReplanState((prev) =>
          prev.status === "exhausted" ? { ...prev, status: "idle" } : prev
        );
        break;
      }

      case "run.stopped" as string: {
        const ev = event as unknown as {
          barrier_type?: string;
          barrier?: string;
          reason?: string;
          message?: string;
          target_url?: string;
          step_seq?: number;
        };
        setRunStatus("stopped");
        setBarrierDetails({
          barrierType: ev.barrier_type || ev.barrier || "cloudflare_turnstile",
          reason: ev.reason,
          message:
            ev.message ||
            "Cloudflare Turnstile challenge detected on target page. Automation restricted per safety baseline.",
          targetUrl: ev.target_url || workflowRef.current?.target_url || "http://localhost:3001/login",
          stepSeq: ev.step_seq ?? activeStepSeqRef.current,
        });
        break;
      }

      case "run.cancelled": {
        setRunStatus("cancelled");
        setActiveStepSeq(null);
        break;
      }

      case "run.failed": {
        setRunStatus("failed");
        setRunError(event.error);
        break;
      }

      case "run.completed": {
        setRunStatus("completed");
        setActiveStepSeq(null);
        break;
      }

      default: {
        const ev = event as unknown as ExtendedCustomEvent;
        if (ev.type === "step.replan_started" || ev.type === "run.replan_started") {
          const attempt = ev.attempt ?? 1;
          const maxAttempts = ev.max_attempts ?? 3;
          const status: ReplanStatus = ev.status || "re-locating";
          setReplanState({
            status,
            attempt,
            maxAttempts,
            reason: ev.reason,
            strategy:
              ev.strategy || "Adaptive element re-location & alternative branch replay",
            timeoutSeconds: ev.timeout_seconds ?? 30,
            stepSeq: ev.step_seq,
          });
        } else if (ev.type === "step.replan_succeeded" || ev.type === "run.replan_succeeded") {
          setReplanState((prev) => ({
            ...prev,
            status: "succeeded",
          }));
        } else if (ev.type === "step.replan_failed" || ev.type === "run.replan_failed") {
          setReplanState((prev) => ({
            ...prev,
            status: "exhausted",
          }));
        }
        break;
      }
    }
  }, []);

  const startStream = useCallback(async () => {
    if (isStreamingRef.current) return;
    isStreamingRef.current = true;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setRunStatus("running");
    setError(null);

    try {
      const stream = apiClient.streamWorkflowEvents(workflowId, {
        speed,
        signal: controller.signal,
      });

      for await (const event of stream) {
        if (controller.signal.aborted) break;
        handleEvent(event);
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      setError(err instanceof Error ? err.message : "Error streaming workflow events");
    } finally {
      isStreamingRef.current = false;
    }
  }, [apiClient, handleEvent, speed, workflowId]);

  const cancel = useCallback(async () => {
    if (isCancelling) return;
    setIsCancelling(true);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    isStreamingRef.current = false;
    setRunStatus("cancelled");
    setPauseDetails(null);
    setBarrierDetails(null);
    setActiveStepSeq(null);
    try {
      const runId = workflow?.run_id || workflow?.id || workflowId;
      if (typeof apiClient.cancelRun === "function") {
        await apiClient.cancelRun(runId);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to cancel run");
    } finally {
      setIsCancelling(false);
    }
  }, [apiClient, isCancelling, workflow, workflowId]);

  const confirm = useCallback(
    async (decision: "allow" | "deny") => {
      if (isConfirming) return;
      setIsConfirming(true);
      const stepSeq = pauseDetails?.stepSeq ?? 1;
      const runId = workflow?.run_id || workflow?.id || workflowId;
      if (decision === "allow") {
        setRunStatus("running");
        setPauseDetails(null);
        setBarrierDetails(null);
      } else {
        if (abortControllerRef.current) {
          abortControllerRef.current.abort();
        }
        isStreamingRef.current = false;
        setRunStatus("cancelled");
        setPauseDetails(null);
        setBarrierDetails(null);
        setActiveStepSeq(null);
      }
      try {
        if (typeof apiClient.confirmRunAction === "function") {
          await apiClient.confirmRunAction(runId, decision, stepSeq);
        } else if (typeof apiClient.confirmRun === "function") {
          await apiClient.confirmRun(runId, stepSeq, decision);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : `Failed to ${decision} paused run`);
      } finally {
        setIsConfirming(false);
      }
    },
    [apiClient, isConfirming, pauseDetails?.stepSeq, workflow, workflowId]
  );

  const resume = useCallback(() => {
    setRunStatus("running");
    setPauseDetails(null);
    setBarrierDetails(null);
    const stepSeq = pauseDetails?.stepSeq ?? 1;
    const runId = workflow?.run_id || workflow?.id || workflowId;
    if (typeof apiClient.confirmRunAction === "function") {
      apiClient.confirmRunAction(runId, "allow", stepSeq).catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to confirm run (allow)");
      });
    } else if (typeof apiClient.confirmRun === "function") {
      apiClient.confirmRun(runId, stepSeq, "allow").catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to confirm run (allow)");
      });
    }
  }, [apiClient, pauseDetails, workflow, workflowId]);

  const deny = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    isStreamingRef.current = false;
    setRunStatus("cancelled");
    setPauseDetails(null);
    setBarrierDetails(null);
    setActiveStepSeq(null);
    const stepSeq = pauseDetails?.stepSeq ?? 1;
    const runId = workflow?.run_id || workflow?.id || workflowId;
    if (typeof apiClient.confirmRunAction === "function") {
      apiClient.confirmRunAction(runId, "deny", stepSeq).catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to confirm run (deny)");
      });
    } else if (typeof apiClient.confirmRun === "function") {
      apiClient.confirmRun(runId, stepSeq, "deny").catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to confirm run (deny)");
      });
    }
  }, [apiClient, pauseDetails, workflow, workflowId]);

  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    isStreamingRef.current = false;
    setRunStatus("idle");
    setActiveStepSeq(null);
    setPauseDetails(null);
    setBarrierDetails(null);
    setRunError(null);
    setElapsedSeconds(0);
    setReplanState({
      status: "idle",
      attempt: 0,
      maxAttempts: 3,
    });
    if (workflow) {
      const { states, total } = buildInitialStepStates(workflow);
      setStepStates(states);
      setTotalSteps(total);
    }
  }, [workflow]);

  // Auto-start stream once workflow is loaded
  useEffect(() => {
    if (!autoStart || isLoading || error || runStatus !== "idle") {
      return;
    }

    let isMounted = true;
    const timer = setTimeout(() => {
      if (isMounted) {
        startStream();
      }
    }, 0);

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, [autoStart, isLoading, error, runStatus, startStream]);

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // Compute metrics
  const stepsList = Object.values(stepStates).sort((a, b) => a.seq - b.seq);
  const verifiedCount = stepsList.filter((s) => s.status === "verified").length;
  const denominator = totalSteps > 0 ? totalSteps : stepsList.length;
  const progressPercent =
    runStatus === "completed"
      ? 100
      : denominator > 0
        ? Math.round((verifiedCount / denominator) * 100)
        : 0;

  return {
    runStatus,
    workflow,
    steps: stepsList,
    stepStates,
    activeStepSeq,
    pauseDetails,
    barrierDetails,
    runError,
    replanState,
    elapsedSeconds,
    progressPercent,
    verifiedCount,
    totalSteps: denominator,
    isLoading,
    isCancelling,
    isConfirming,
    error,
    start: startStream,
    cancel,
    confirm,
    resume,
    deny,
    reset,
  };
}
