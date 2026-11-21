import Link from "next/link";
import { useTranslations } from "next-intl";
import type { RunDetails } from "@/lib/types";
import { RunStatusBadge } from "./RunStatusBadge";
import { formatDateTime, formatDuration } from "./RunListTable";

export interface RunDetailHeaderProps {
  runDetails: RunDetails;
  className?: string;
}

export function RunDetailHeader({ runDetails, className = "" }: RunDetailHeaderProps) {
  const t = useTranslations("runs");
  const { run, summary, targetUrl } = runDetails;

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Navigation Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-ink-400">
        <Link
          href="/runs"
          data-testid="back-to-runs-link"
          className="inline-flex items-center gap-1 hover:text-white font-medium transition-colors"
        >
          <svg className="size-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          {t("detailHeader.back")}
        </Link>
        {/* The id stays available to tests and screen readers, not as visible jargon (#318) */}
        <span data-testid="run-detail-id" className="sr-only">
          {run.id}
        </span>
      </div>

      {/* Main Title & Status */}
      <div className="kr-run kr-tone-card relative flex flex-col justify-between gap-4 overflow-hidden rounded-3xl p-6 md:flex-row md:items-center">
        <div className="space-y-1 max-w-3xl">
          <div className="flex items-center gap-2.5">
            <h1
              data-testid="run-detail-prompt"
              className="kr-display text-2xl font-extrabold text-white sm:text-3xl"
            >
              {run.prompt ?? t("detailHeader.promptUnavailable")}
            </h1>
            <RunStatusBadge status={run.status} size="md" />
          </div>
          {targetUrl && (
            <p
              data-testid="stat-target-url"
              className="text-xs text-ink-400 truncate"
            >
              {t("detailHeader.website")} <span className="font-mono text-run">{targetUrl.replace(/^https?:\/\//, "").replace(/\/$/, "")}</span>
            </p>
          )}
        </div>

        <div className="text-xs text-ink-400 shrink-0 space-y-2">
          {run.workflowId && (
            <Link
              href={`/tutorials/${run.workflowId}`}
              data-testid="watch-tutorial-link"
              className="kr-btn kr-btn-primary px-4 py-1.5 text-xs"
            >
              &#9654; {t("detailHeader.watchTutorial")}
            </Link>
          )}
          <div>{t("detailHeader.started")} <span className="font-medium text-ink-300">{formatDateTime(run.startedAt || run.createdAt)}</span></div>
          {run.finishedAt && (
            <div>{t("detailHeader.finished")} <span className="font-medium text-ink-300">{formatDateTime(run.finishedAt)}</span></div>
          )}
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="kr-tone-card rounded-2xl p-4" style={{ ["--kr-tone" as string]: "var(--approve)" }}>
          <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.16em] text-ink-400">{t("detailHeader.totalSteps")}</span>
          <span
            data-testid="stat-total-steps"
            className="kr-display text-3xl font-extrabold text-white"
          >
            {summary.totalSteps}
          </span>
        </div>

        <div className="kr-tone-card rounded-2xl p-4" style={{ ["--kr-tone" as string]: "var(--verify)" }}>
          <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.16em] text-ink-400">{t("detailHeader.verifiedSteps")}</span>
          <span
            data-testid="stat-verified-steps"
            className="kr-display text-3xl font-extrabold text-verify [text-shadow:0_0_18px_var(--verify)]"
          >
            {summary.verifiedSteps}
          </span>
        </div>

        <div className="kr-tone-card rounded-2xl p-4" style={{ ["--kr-tone" as string]: "var(--danger)" }}>
          <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.16em] text-ink-400">{t("detailHeader.failedSteps")}</span>
          <span
            data-testid="stat-failed-steps"
            className={`kr-display text-3xl font-extrabold ${
              summary.failedSteps > 0
                ? "text-danger"
                : "text-ink-400"
            }`}
          >
            {summary.failedSteps}
          </span>
        </div>

        <div className="kr-tone-card rounded-2xl p-4" style={{ ["--kr-tone" as string]: "var(--plan)" }}>
          <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.16em] text-ink-400">{t("detailHeader.duration")}</span>
          <span
            data-testid="stat-duration"
            className="font-mono text-3xl font-bold text-plan [text-shadow:0_0_18px_var(--plan)]"
          >
            {formatDuration(summary.durationSeconds ?? run.durationSeconds)}
          </span>
        </div>
      </div>
    </div>
  );
}
