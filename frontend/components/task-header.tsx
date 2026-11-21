import { ExternalLink, Globe, ListChecks, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";

export interface TaskHeaderProps {
  prompt: string;
  targetUrl?: string | null;
  title?: string | null;
  targetApp?: string | null;
  status?: string | null;
  className?: string;
}

// The plan status wears the stage it belongs to: proposed = plan amber, approved = approve violet, rejected = coral.
const STATUS_TONE: Record<string, string> = {
  proposed: "kr-plan",
  draft: "kr-plan",
  approved: "kr-approve",
  executing: "kr-run",
  rejected: "kr-danger",
  cancelled: "kr-danger",
};

export function TaskHeader({ prompt, targetUrl, title, targetApp, status, className = "" }: TaskHeaderProps) {
  const t = useTranslations("approval");
  return (
    <header
      data-testid="task-header"
      className={`kr-plan kr-tone-card relative overflow-hidden rounded-[2rem] p-6 sm:p-8 ${className}`}
    >
      {/* amber -> violet glow: the plan is waiting for approval */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-20 -top-24 size-72 rounded-full opacity-40 blur-3xl"
        style={{ background: "radial-gradient(circle, var(--approve), transparent 70%)" }}
      />
      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="kr-chip kr-plan">
              <ListChecks aria-hidden="true" className="size-3.5" />
              {t("taskHeader.workflowPlan")}
            </span>
            {targetApp && (
              <span className="kr-chip kr-run">
                <Globe aria-hidden="true" className="size-3.5" />
                {targetApp}
              </span>
            )}
            {status && (
              <span
                data-testid="workflow-status-badge"
                className={`kr-chip ${STATUS_TONE[status] ?? "kr-approve"} uppercase tracking-widest`}
              >
                {status}
              </span>
            )}
          </div>
          <h1 className="kr-display text-3xl font-extrabold leading-tight text-white sm:text-4xl">
            {title || t("taskHeader.defaultTitle")}
          </h1>
        </div>
      </div>

      <div className="relative mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5 rounded-2xl border border-white/10 bg-ink-950/50 p-4">
          <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-ask">
            <Sparkles aria-hidden="true" className="size-3.5" />
            {t("taskHeader.taskPrompt")}
          </span>
          <p data-testid="task-prompt" className="text-sm font-medium text-white">
            {prompt}
          </p>
        </div>

        <div className="flex flex-col gap-1.5 rounded-2xl border border-white/10 bg-ink-950/50 p-4">
          <span className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-run">
            <Globe aria-hidden="true" className="size-3.5" />
            {t("taskHeader.targetUrl")}
          </span>
          {targetUrl ? (
            <a
              data-testid="target-url"
              href={targetUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 font-mono text-sm text-run hover:text-white hover:underline"
            >
              <span>{targetUrl}</span>
              <ExternalLink aria-hidden="true" className="size-3.5" />
            </a>
          ) : (
            <span data-testid="target-url" className="text-sm italic text-ink-400">
              {t("taskHeader.noTargetUrl")}
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
