"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiBaseUrl } from "@/lib/artifacts";

export type StreamStepStatus = "pending" | "running" | "completed" | "paused" | "failed";

export interface StreamStep {
  seq: number;
  instructionText: string;
  status: StreamStepStatus;
  durationMs?: number;
  error?: string;
  expectedState?: {
    url_matches?: string;
    title_contains?: string;
    visible?: Array<{ role: string; name: string }>;
    absent?: Array<{ role: string; name: string }>;
  };
  observedState?: {
    url?: string;
    title?: string;
    visible?: Array<{ role: string; name: string }>;
  };
}

export interface LiveScreenshotFrame {
  imageUrl: string;
  timestampMs?: number;
  stepSeq?: number;
}

export interface PausedState {
  reason: string;
  message?: string;
  stepSeq?: number;
  triggerContext?: string;
}

export interface FailedState {
  error: string;
  stepSeq?: number;
  expected?: string | Record<string, unknown>;
  observed?: string | Record<string, unknown>;
}

export interface UseRunStreamOptions {
  runId: string;
  autoConnect?: boolean;
  initialSteps?: StreamStep[];
  initialStatus?: "idle" | "running" | "paused" | "failed" | "completed";
  targetUrl?: string;
}

export interface UseRunStreamResult {
  runId: string;
  status: "idle" | "running" | "paused" | "failed" | "completed";
  steps: StreamStep[];
  currentStepSeq: number | null;
  latestScreenshot: LiveScreenshotFrame | null;
  pausedState: PausedState | null;
  failedState: FailedState | null;
  workflowId: string | null;
  targetUrl: string | undefined;
  isConnected: boolean;
  isReconnecting: boolean;
  error: string | null;
  resume: () => Promise<void>;
  abort: () => Promise<void>;
}

export function useRunStream({
  runId,
  autoConnect = true,
  initialSteps = [],
  initialStatus = "idle",
  targetUrl: initialTargetUrl,
}: UseRunStreamOptions): UseRunStreamResult {
  const [status, setStatus] = useState<"idle" | "running" | "paused" | "failed" | "completed">(initialStatus);
  const [steps, setSteps] = useState<StreamStep[]>(initialSteps);
  const [currentStepSeq, setCurrentStepSeq] = useState<number | null>(null);
  const currentStepSeqRef = useRef<number | null>(null);
  const [latestScreenshot, setLatestScreenshot] = useState<LiveScreenshotFrame | null>(null);
  const [pausedState, setPausedState] = useState<PausedState | null>(null);
  const [failedState, setFailedState] = useState<FailedState | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [targetUrl, setTargetUrl] = useState<string | undefined>(initialTargetUrl);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isReconnecting, setIsReconnecting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  const handleEvent = useCallback((eventType: string, dataRaw: string) => {
    let payload: Record<string, unknown> = {};
    try {
      payload = typeof dataRaw === "string" ? JSON.parse(dataRaw) : dataRaw;
    } catch {
      payload = { raw: dataRaw };
    }

    switch (eventType) {
      case "plan": {
        const rawSteps = (payload.steps || payload.planned_steps || []) as Array<Record<string, unknown>>;
        const parsedSteps: StreamStep[] = rawSteps.map((s, idx) => ({
          seq: typeof s.seq === "number" ? s.seq : idx + 1,
          instructionText: (s.instruction_text || s.instructionText || s.title || `Step ${idx + 1}`) as string,
          status: "pending",
        }));
        setSteps(parsedSteps);
        setStatus("running");
        if (payload.target_url) {
          setTargetUrl(String(payload.target_url));
        }
        break;
      }

      case "step_started":
      case "step.started": {
        const seq = Number(payload.step_seq ?? payload.seq ?? 1);
        currentStepSeqRef.current = seq;
        setCurrentStepSeq(seq);
        setStatus("running");
        setSteps((prev) =>
          prev.map((step) =>
            step.seq === seq
              ? { ...step, status: "running" }
              : step.seq < seq && step.status === "running"
                ? { ...step, status: "completed" }
                : step,
          ),
        );
        break;
      }

      case "step_completed":
      case "step.action_done":
      case "step.verified": {
        const seq = Number(payload.step_seq ?? payload.seq ?? currentStepSeqRef.current);
        const duration = typeof payload.duration_ms === "number" ? payload.duration_ms : undefined;
        setSteps((prev) =>
          prev.map((step) =>
            step.seq === seq
              ? { ...step, status: "completed", durationMs: duration ?? step.durationMs }
              : step,
          ),
        );
        break;
      }

      case "screenshot":
      case "step.screenshot": {
        const imageUrl = (payload.image_url || payload.screenshot_url || payload.url || payload.frame) as string;
        const timestampMs = typeof payload.timestamp_ms === "number" ? payload.timestamp_ms : Date.now();
        const stepSeq = typeof payload.step_seq === "number" ? payload.step_seq : undefined;
        if (imageUrl) {
          setLatestScreenshot({ imageUrl, timestampMs, stepSeq });
        }
        break;
      }

      case "paused":
      case "run.paused": {
        const reason = (payload.reason || "Action requires manual approval") as string;
        const message = (payload.message || "Manual confirmation required before proceeding") as string;
        const stepSeq = payload.step_seq ? Number(payload.step_seq) : (currentStepSeqRef.current ?? undefined);
        const triggerContext = (payload.trigger_context || payload.context || (reason.includes("danger") ? "GitHub Danger Zone" : undefined)) as string | undefined;

        setStatus("paused");
        setPausedState({ reason, message, stepSeq, triggerContext });
        if (stepSeq) {
          setSteps((prev) =>
            prev.map((step) => (step.seq === stepSeq ? { ...step, status: "paused" } : step)),
          );
        }
        break;
      }

      case "failed":
      case "run.failed":
      case "step.failed": {
        const errMessage = (payload.error || payload.message || "Workflow execution encountered an error") as string;
        const stepSeq = payload.step_seq ? Number(payload.step_seq) : (currentStepSeqRef.current ?? undefined);
        const expected = payload.expected_state || payload.expected;
        const observed = payload.observed_state || payload.observed;

        setStatus("failed");
        setFailedState({
          error: errMessage,
          stepSeq,
          expected: expected as FailedState["expected"],
          observed: observed as FailedState["observed"],
        });

        if (stepSeq) {
          setSteps((prev) =>
            prev.map((step) =>
              step.seq === stepSeq
                ? {
                    ...step,
                    status: "failed",
                    error: errMessage,
                    expectedState: expected as StreamStep["expectedState"],
                    observedState: observed as StreamStep["observedState"],
                  }
                : step,
            ),
          );
        }
        break;
      }

      case "completed":
      case "run.completed":
      case "run.verified": {
        setStatus("completed");
        const wId = (payload.workflow_id || payload.workflowId || payload.id) as string | undefined;
        if (wId) {
          setWorkflowId(wId);
        }
        setSteps((prev) =>
          prev.map((step) => (step.status === "running" ? { ...step, status: "completed" } : step)),
        );
        break;
      }

      default:
        break;
    }
  }, []);

  const handleEventRef = useRef(handleEvent);
  useEffect(() => {
    handleEventRef.current = handleEvent;
  });

  useEffect(() => {
    if (!autoConnect || !runId) return;

    // In browser environment with EventSource support
    if (typeof window === "undefined" || typeof EventSource === "undefined") return;

    let isMounted = true;
    const base = apiBaseUrl().replace(/\/+$/, "");
    // The live view is GET /api/v1/runs/{id}/events (docs/api-contract.md).
    const streamUrl = base.endsWith("/api/v1")
      ? `${base}/runs/${encodeURIComponent(runId)}/events`
      : `${base}/api/v1/runs/${encodeURIComponent(runId)}/events`;

    let es: EventSource | null = null;
    try {
      // withCredentials: the API needs the session cookie (#94).
      es = new EventSource(streamUrl, { withCredentials: true });
      eventSourceRef.current = es;

      es.onopen = () => {
        if (!isMounted) return;
        setIsConnected(true);
        setIsReconnecting(false);
        setError(null);
      };

      const eventNames = [
        "plan",
        "step_started",
        "step.started",
        "step_completed",
        "step.action_done",
        "step.verified",
        "screenshot",
        "step.screenshot",
        "paused",
        "run.paused",
        "failed",
        "run.failed",
        "step.failed",
        "completed",
        "run.completed",
        "run.verified",
      ];

      eventNames.forEach((name) => {
        es?.addEventListener(name, (evt: MessageEvent) => {
          if (!isMounted) return;
          handleEventRef.current(name, evt.data);
        });
      });

      es.onmessage = (evt: MessageEvent) => {
        if (!isMounted) return;
        try {
          const parsed = JSON.parse(evt.data);
          const type = parsed.type || parsed.event;
          if (type) {
            handleEventRef.current(type, evt.data);
          }
        } catch {
          // Ignore unformatted raw heartbeat
        }
      };

      es.onerror = () => {
        if (!isMounted) return;
        setIsConnected(false);
        setIsReconnecting(true);
        // Do not throw uncaught exceptions on drop/reconnect
      };
    } catch {
      // EventSource failed to instantiate, fallback gracefully without uncaught crash
    }

    return () => {
      isMounted = false;
      if (es) {
        es.close();
        eventSourceRef.current = null;
      }
    };
  }, [runId, autoConnect]);

  const resume = useCallback(async () => {
    const base = apiBaseUrl().replace(/\/+$/, "");
    const resumeUrl = base.endsWith("/api/v1")
      ? `${base}/runs/${encodeURIComponent(runId)}/resume`
      : `${base}/api/v1/runs/${encodeURIComponent(runId)}/resume`;

    try {
      const res = await fetch(resumeUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Krama": "1",
        },
      });

      if (!res.ok) {
        // Fallback to /confirm if /resume 404s
        const confirmUrl = base.endsWith("/api/v1")
          ? `${base}/runs/${encodeURIComponent(runId)}/confirm`
          : `${base}/api/v1/runs/${encodeURIComponent(runId)}/confirm`;
        await fetch(confirmUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Krama": "1",
          },
          body: JSON.stringify({ decision: "allow" }),
        });
      }

      setStatus("running");
      setPausedState(null);
    } catch {
      // Optimistically resume locally
      setStatus("running");
      setPausedState(null);
    }
  }, [runId]);

  const abort = useCallback(async () => {
    const base = apiBaseUrl().replace(/\/+$/, "");
    const abortUrl = base.endsWith("/api/v1")
      ? `${base}/runs/${encodeURIComponent(runId)}/abort`
      : `${base}/api/v1/runs/${encodeURIComponent(runId)}/abort`;

    try {
      const res = await fetch(abortUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Krama": "1",
        },
      });

      if (!res.ok) {
        // Fallback to /cancel if /abort 404s
        const cancelUrl = base.endsWith("/api/v1")
          ? `${base}/runs/${encodeURIComponent(runId)}/cancel`
          : `${base}/api/v1/runs/${encodeURIComponent(runId)}/cancel`;
        await fetch(cancelUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Krama": "1",
          },
        });
      }

      setStatus("failed");
      setPausedState(null);
    } catch {
      setStatus("failed");
      setPausedState(null);
    }
  }, [runId]);

  return {
    runId,
    status,
    steps,
    currentStepSeq,
    latestScreenshot,
    pausedState,
    failedState,
    workflowId,
    targetUrl,
    isConnected,
    isReconnecting,
    error,
    resume,
    abort,
  };
}
