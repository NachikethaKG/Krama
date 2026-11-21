import { Radio } from "lucide-react";
import { useTranslations } from "next-intl";
import type { RunExecutionStatus } from "@/hooks/useRunExecutionStream";

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
  const t = useTranslations("execution");
  // Each run state wears a spectrum tone: running = cyan, paused = amber, failed = coral, done = lime.
  const statusColorMap: Record<RunExecutionStatus, { tone: string; live: boolean }> = {
    idle: { tone: "var(--ink-400)", live: false },
    running: { tone: "var(--run)", live: true },
    paused: { tone: "var(--plan)", live: true },
    failed: { tone: "var(--danger)", live: false },
    completed: { tone: "var(--verify)", live: false },
    cancelled: { tone: "var(--ink-400)", live: false },
    queued: { tone: "var(--approve)", live: true },
  };

  const statusStyle = statusColorMap[runStatus] ?? statusColorMap.idle;

  return (
    <header
      data-testid="execution-header"
      style={{ ["--kr-tone" as string]: statusStyle.tone }}
      className={`kr-tone-card relative overflow-hidden rounded-3xl p-6 ${className}`}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="kr-chip kr-run">
              <Radio aria-hidden="true" className="size-3" />
              {t("header.badge")}
            </span>
            {targetApp && (
              <span className="kr-chip kr-approve">
                {targetApp}
              </span>
            )}
            <span
              data-testid="execution-status-badge"
              data-status={runStatus}
              className="kr-chip uppercase tracking-wider"
            >
              <span className={`kr-dot !size-1.5 ${statusStyle.live ? "kr-dot-live" : ""}`} />
              {t(`header.status.${runStatus}`)}
            </span>
          </div>

          <h1 className="kr-display text-3xl font-extrabold text-white sm:text-4xl">
            {title || t("header.defaultTitle")}
          </h1>
          {prompt && (
            <p className="text-sm font-medium text-ink-300">
              {prompt}
            </p>
          )}
        </div>

        {/* Live Elapsed Timer */}
        <div className="flex flex-row items-center gap-2 rounded-2xl border border-white/10 bg-ink-950/70 px-4 py-2.5 sm:flex-col sm:items-end">
          <span className="text-[11px] font-bold uppercase tracking-[0.2em] text-ink-400">
            {t("header.elapsed")}
          </span>
          <span
            data-testid="elapsed-timer"
            className="font-mono text-xl font-bold text-run [text-shadow:0_0_18px_var(--run)] sm:text-3xl"
          >
            {formatDuration(elapsedSeconds)}
          </span>
        </div>
      </div>

      {/* Progress Bar & Metrics */}
      <div className="mt-6 flex flex-col gap-2.5 border-t border-white/10 pt-4">
        <div className="flex items-center justify-between text-xs font-medium">
          <span className="text-ink-300">
            {t("header.progress", { verified: verifiedCount, total: totalSteps })}
          </span>
          <span data-testid="progress-percent" className="font-mono font-bold text-white">
            {progressPercent}%
          </span>
        </div>

        <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/[0.07]">
          <div
            data-testid="execution-progress-bar"
            aria-valuenow={progressPercent}
            aria-valuemin={0}
            aria-valuemax={100}
            role="progressbar"
            style={{ width: `${progressPercent}%` }}
            className={`h-full rounded-full transition-all duration-500 ease-out ${
              runStatus === "failed" ? "bg-danger shadow-[0_0_14px_var(--danger)]" : "kr-rail"
            }`}
          />
        </div>

        {targetUrl && (
          <div className="mt-1 flex items-center gap-1.5 text-xs text-ink-400">
            <span>{t("header.website")}</span>
            <a
              href={targetUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-run hover:underline"
            >
              {targetUrl}
            </a>
          </div>
        )}
      </div>
    </header>
  );
}
