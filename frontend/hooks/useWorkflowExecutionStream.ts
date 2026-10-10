"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ApiError,
  PauseReason,
  RunEvent,
  Step,
  Workflow,
} from "@krama/contracts-ts";

import { type ApiClient, createApiClient } from "@/lib/api";

export type RunExecutionStatus = "idle" | "running" | "paused" | "failed" | "completed";
export type StepStatus = "pending" | "started" | "verified" | "failed";

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
  runError: ApiError | null;
  elapsedSeconds: number;
  progressPercent: number;
  verifiedCount: number;
  totalSteps: number;
  isLoading: boolean;
  error: string | null;
  start: () => void;
  resume: () => void;
  reset: () => void;
}

export function useWorkflowExecutionStream({
  workflowId,
  client,
  autoStart = true,
  speed,
  initialWorkflow,
}: UseWorkflowExecutionStreamOptions): UseWorkflowExecutionStreamResult {
  const [apiClient] = useState<ApiClient>(() => client ?? createApiClient());
  const [workflow, setWorkflow] = useState<Workflow | null>(initialWorkflow ?? null);
  const [runStatus, setRunStatus] = useState<RunExecutionStatus>("idle");
  const [activeStepSeq, setActiveStepSeq] = useState<number | null>(null);
  const [pauseDetails, setPauseDetails] = useState<PauseDetails | null>(null);
  const [runError, setRunError] = useState<ApiError | null>(null);
  const [stepStates, setStepStates] = useState<Record<number, StepExecutionState>>({});
  const [totalSteps, setTotalSteps] = useState<number>(0);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(!initialWorkflow);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const isStreamingRef = useRef<boolean>(false);

  // Initialize step states from workflow
  const initStepStates = useCallback((wf: Workflow) => {
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
    setStepStates(map);
    setTotalSteps(stepsList.length);
  }, []);

  // Fetch workflow details if not supplied
  useEffect(() => {
    if (initialWorkflow) {
      initStepStates(initialWorkflow);
      setIsLoading(false);
      return;
    }

    let isMounted = true;
    setIsLoading(true);

    apiClient
      .getWorkflow(workflowId)
      .then((data) => {
        if (isMounted) {
          setWorkflow(data);
          initStepStates(data);
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
  }, [apiClient, initialWorkflow, workflowId, initStepStates]);

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
        setActiveStepSeq(event.step_seq);
        setStepStates((prev) => ({
          ...prev,
          [event.step_seq]: {
            ...(prev[event.step_seq] ?? {
              seq: event.step_seq,
              risk: "low",
            }),
            seq: event.step_seq,
            status: "started",
            instructionText: event.instruction_text || prev[event.step_seq]?.instructionText || "",
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
        setStepStates((prev) => ({
          ...prev,
          [event.step_seq]: {
            ...prev[event.step_seq],
            status: "failed",
            error: "Verification failed: observed state did not match expected preconditions.",
            observedUrl: event.observed?.url,
            observedTitle: event.observed?.title,
            screenshotUrl: event.screenshot_url ?? undefined,
          },
        }));
        break;
      }

      case "run.paused": {
        setRunStatus("paused");
        setPauseDetails({
          reason: event.reason,
          stepSeq: event.step_seq,
          message: event.message,
        });
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

      default:
        break;
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

  const resume = useCallback(() => {
    setRunStatus("running");
    setPauseDetails(null);
  }, []);

  const reset = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    isStreamingRef.current = false;
    setRunStatus("idle");
    setActiveStepSeq(null);
    setPauseDetails(null);
    setRunError(null);
    setElapsedSeconds(0);
    if (workflow) {
      initStepStates(workflow);
    }
  }, [initStepStates, workflow]);

  // Auto-start stream once workflow is loaded
  useEffect(() => {
    if (autoStart && !isLoading && !error && runStatus === "idle") {
      startStream();
    }
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
    runError,
    elapsedSeconds,
    progressPercent,
    verifiedCount,
    totalSteps: denominator,
    isLoading,
    error,
    start: startStream,
    resume,
    reset,
  };
}
