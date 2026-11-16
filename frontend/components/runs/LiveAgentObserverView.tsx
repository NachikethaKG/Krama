"use client";

import Link from "next/link";
import { useRunStream, type StreamStep } from "@/hooks/useRunStream";
import { LiveViewportStream } from "./LiveViewportStream";
import { StepChecklist } from "./StepChecklist";
import { RunStatusBanners } from "./RunStatusBanners";

export interface LiveAgentObserverViewProps {
  runId: string;
  prompt?: string | null;
  targetUrl?: string;
  initialSteps?: StreamStep[];
  initialStatus?: "idle" | "running" | "paused" | "failed" | "completed";
  autoConnect?: boolean;
  className?: string;
}

export function LiveAgentObserverView({
  runId,
  prompt,
  targetUrl,
  initialSteps,
  initialStatus,
  autoConnect = true,
  className = "",
}: LiveAgentObserverViewProps) {
  const {
    status,
    steps,
    currentStepSeq,
    latestScreenshot,
    pausedState,
    failedState,
    workflowId,
    targetUrl: streamTargetUrl,
    isConnected,
    isReconnecting,
    resume,
    abort,
  } = useRunStream({
    runId,
    autoConnect,
    initialSteps,
    initialStatus,
    targetUrl,
  });

  const effectiveTargetUrl = streamTargetUrl || targetUrl;

  return (
    <div
      data-testid="live-agent-observer-view"
      className={`mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 sm:p-6 ${className}`}
    >
      {/* Top Header & Breadcrumb */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b pb-4 border-white/10">
        <div>
          <div className="flex items-center gap-2 text-xs text-ink-400">
            <Link
              href="/runs"
              data-testid="observer-back-to-runs"
              className="hover:text-white font-medium transition-colors"
            >
              ← All Runs
            </Link>
            <span>/</span>
            <span
              data-testid="run-detail-id"
              className="font-mono text-ink-300"
            >
              {runId}
            </span>
          </div>

          <h1
            data-testid="run-detail-prompt"
            className="kr-display mt-1 text-3xl font-extrabold text-white sm:text-4xl"
          >
            {prompt || "Live Agent Headless Execution"}
          </h1>
        </div>

        {/* Connection status pill */}
        <div className="flex items-center gap-3 shrink-0">
          <div
            data-testid="stream-connection-badge"
            className="kr-glass flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold text-ink-300"
          >
            <span
              className={`size-2 rounded-full ${
                isConnected
                  ? "kr-dot-live bg-verify shadow-[0_0_10px_var(--verify)]"
                  : isReconnecting
                    ? "animate-ping bg-plan"
                    : "bg-ink-400"
              }`}
            />
            <span>
              {isConnected
                ? "SSE Stream Connected"
                : isReconnecting
                  ? "Reconnecting Stream…"
                  : "Stream Standby"}
            </span>
          </div>
        </div>
      </div>

      {/* Stream reconnection warning banner if drop detected */}
      {isReconnecting && (
        <div
          data-testid="stream-reconnecting-banner"
          className="kr-plan kr-tone-card flex items-center gap-2 rounded-2xl px-4 py-2.5 text-xs font-semibold text-plan"
        >
          <div className="kr-dot kr-dot-live !size-2" />
          <span>Stream connection lost. Reconnecting to live observer stream…</span>
        </div>
      )}

      {/* 2-Column Responsive Layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Column (Desktop 2/3): Actionable status banners and live screenshot viewport */}
        <div className="flex flex-col gap-5 lg:col-span-2">
          {/* Status Banners (Paused / Failed / Completed) */}
          <RunStatusBanners
            status={status}
            pausedState={pausedState}
            failedState={failedState}
            workflowId={workflowId}
            onResume={resume}
            onAbort={abort}
          />

          {/* Live Viewport Stream */}
          <LiveViewportStream
            frame={latestScreenshot}
            targetUrl={effectiveTargetUrl}
            isLoading={status === "running" && !latestScreenshot}
          />
        </div>

        {/* Right Column (Desktop 1/3): Real-Time Step Checklist & Activity Log */}
        <div className="flex flex-col gap-5 lg:col-span-1">
          <StepChecklist
            steps={steps}
            currentStepSeq={currentStepSeq}
          />

          {/* Activity Log Tracker */}
          <div
            data-testid="activity-log-card"
            className="kr-approve kr-tone-card rounded-3xl p-4 text-xs"
          >
            <h3 className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-approve">
              Observer Stream Activity
            </h3>
            <div className="space-y-1.5 font-mono text-[11px] text-ink-400">
              <p>• Run: {runId}</p>
              <p>• Status: <span className="font-semibold uppercase">{status}</span></p>
              {currentStepSeq && <p>• Active Step: {currentStepSeq}</p>}
              {effectiveTargetUrl && <p className="truncate">• Target: {effectiveTargetUrl}</p>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
