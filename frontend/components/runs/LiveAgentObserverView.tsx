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
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-zinc-200 pb-4 dark:border-zinc-800">
        <div>
          <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
            <Link
              href="/runs"
              data-testid="observer-back-to-runs"
              className="hover:text-zinc-900 dark:hover:text-zinc-100 font-medium transition-colors"
            >
              ← All Runs
            </Link>
            <span>/</span>
            <span
              data-testid="run-detail-id"
              className="font-mono text-zinc-700 dark:text-zinc-300"
            >
              {runId}
            </span>
          </div>

          <h1
            data-testid="run-detail-prompt"
            className="mt-1 text-lg sm:text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100"
          >
            {prompt || "Live Agent Headless Execution"}
          </h1>
        </div>

        {/* Connection status pill */}
        <div className="flex items-center gap-3 shrink-0">
          <div
            data-testid="stream-connection-badge"
            className="flex items-center gap-1.5 rounded-full bg-zinc-100 px-2.5 py-1 text-xs font-semibold text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
          >
            <span
              className={`size-2 rounded-full ${
                isConnected
                  ? "bg-emerald-500 animate-pulse"
                  : isReconnecting
                    ? "bg-amber-500 animate-ping"
                    : "bg-zinc-400"
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
          className="flex items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-2.5 text-xs font-medium text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200"
        >
          <div className="size-2 rounded-full bg-amber-500 animate-pulse" />
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
            className="rounded-2xl border border-zinc-200 bg-white p-4 text-xs shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
          >
            <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-2">
              Observer Stream Activity
            </h3>
            <div className="space-y-1.5 font-mono text-[11px] text-zinc-600 dark:text-zinc-400">
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
