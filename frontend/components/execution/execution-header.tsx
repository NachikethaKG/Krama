import type { RunExecutionStatus } from "@/hooks/useWorkflowExecutionStream";

export interface ExecutionHeaderProps {
  title?: string | null;
  prompt?: string | null;
  targetApp?: string | null;
  targetUrl?: string | null;
  runStatus: RunExecutionStatus;
  elapsedSeconds: number;
  progressPercent: number;
  verifiedCount: number;
  totalSteps: number;
  className?: string;
}

export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
}

export function ExecutionHeader({
  title,
  prompt,
  targetApp,
  targetUrl,
  runStatus,
  elapsedSeconds,
  progressPercent,
  verifiedCount,
  totalSteps,
  className = "",
}: ExecutionHeaderProps) {
  const statusColorMap: Record<RunExecutionStatus, { bg: string; text: string; dot: string }> = {
    idle: {
      bg: "bg-zinc-100 dark:bg-zinc-800",
      text: "text-zinc-700 dark:text-zinc-300",
      dot: "bg-zinc-400",
    },
    running: {
      bg: "bg-indigo-50 border-indigo-200 dark:bg-indigo-950/50 dark:border-indigo-800",
      text: "text-indigo-700 dark:text-indigo-300",
      dot: "bg-indigo-500 animate-pulse",
    },
    paused: {
      bg: "bg-amber-50 border-amber-200 dark:bg-amber-950/50 dark:border-amber-800",
      text: "text-amber-700 dark:text-amber-300",
      dot: "bg-amber-500",
    },
    failed: {
      bg: "bg-rose-50 border-rose-200 dark:bg-rose-950/50 dark:border-rose-800",
      text: "text-rose-700 dark:text-rose-300",
      dot: "bg-rose-500",
    },
    completed: {
      bg: "bg-emerald-50 border-emerald-200 dark:bg-emerald-950/50 dark:border-emerald-800",
      text: "text-emerald-700 dark:text-emerald-300",
      dot: "bg-emerald-500",
    },
  };

  const statusStyle = statusColorMap[runStatus] ?? statusColorMap.idle;

  return (
    <header
      data-testid="execution-header"
      className={`rounded-xl border border-zinc-200 bg-white p-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900 ${className}`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
              Live Execution
            </span>
            {targetApp && (
              <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-400">
                {targetApp}
              </span>
            )}
            <span
              data-testid="execution-status-badge"
              data-status={runStatus}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider ${statusStyle.bg} ${statusStyle.text}`}
            >
              <span className={`size-1.5 rounded-full ${statusStyle.dot}`} />
              {runStatus}
            </span>
          </div>

          <h1 className="text-xl font-semibold tracking-tight text-zinc-900 sm:text-2xl dark:text-zinc-100">
            {title || "Workflow Live Execution"}
          </h1>
          {prompt && (
            <p className="text-sm font-medium text-zinc-600 dark:text-zinc-400">
              {prompt}
            </p>
          )}
        </div>

        {/* Live Elapsed Timer */}
        <div className="flex flex-row items-center gap-2 rounded-lg border border-zinc-100 bg-zinc-50 px-3.5 py-2 sm:flex-col sm:items-end dark:border-zinc-800 dark:bg-zinc-800/60">
          <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider dark:text-zinc-400">
            Elapsed
          </span>
          <span
            data-testid="elapsed-timer"
            className="font-mono text-base font-bold text-zinc-900 sm:text-lg dark:text-zinc-100"
          >
            {formatDuration(elapsedSeconds)}
          </span>
        </div>
      </div>

      {/* Progress Bar & Metrics */}
      <div className="mt-5 flex flex-col gap-2 border-t border-zinc-100 pt-4 dark:border-zinc-800">
        <div className="flex items-center justify-between text-xs font-medium">
          <span className="text-zinc-500 dark:text-zinc-400">
            Progress: {verifiedCount} of {totalSteps} steps verified
          </span>
          <span data-testid="progress-percent" className="font-mono font-bold text-zinc-800 dark:text-zinc-200">
            {progressPercent}%
          </span>
        </div>

        <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
          <div
            data-testid="execution-progress-bar"
            aria-valuenow={progressPercent}
            aria-valuemin={0}
            aria-valuemax={100}
            role="progressbar"
            style={{ width: `${progressPercent}%` }}
            className={`h-full transition-all duration-300 ease-out ${
              runStatus === "failed"
                ? "bg-rose-500"
                : runStatus === "completed"
                  ? "bg-emerald-500"
                  : "bg-indigo-600 dark:bg-indigo-500"
            }`}
          />
        </div>

        {targetUrl && (
          <div className="mt-1 flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
            <span>Target:</span>
            <a
              href={targetUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-blue-600 hover:underline dark:text-blue-400"
            >
              {targetUrl}
            </a>
          </div>
        )}
      </div>
    </header>
  );
}
