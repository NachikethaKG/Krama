"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { Task } from "@krama/contracts-ts";
import { AlertTriangle, CornerDownLeft, Globe, HelpCircle, Loader2, Sparkles, Terminal, Wrench } from "lucide-react";

import { TargetPicker, type TargetType, useTargetSelection } from "@/components/target-picker";
import { type ApiClient, errorMessage, getApiClient } from "@/lib/api";
import { detectSite, type Site, supportedSites } from "@/lib/site-detection";

export interface TaskInputProps {
  client?: ApiClient;
  onTaskCreated?: (task: Task) => void;
  /** How often GET /tasks/{id} is polled while planning (default 1 s). */
  pollIntervalMs?: number;
  /** Give up waiting for a plan after this long (default 3 min; real planning takes 15-60 s). */
  planningTimeoutMs?: number;
  className?: string;
  initialTarget?: TargetType;
  initialTargetUrl?: string;
  /** Show the developer target picker (local Gitea, custom URL). Default: NEXT_PUBLIC_DEV_TARGETS=1. */
  devTargets?: boolean;
  /** Text to start with, e.g. "Plan it fresh" after a failed "Do it for me" run (#402). */
  initialPrompt?: string;
}

/** Example prompts: taskInput.examples.<key> in the "approval" namespace. */
const EXAMPLES = ["privateRepo", "addLabel", "newBranch"] as const;

/** Each example chip wears a different spectrum colour. */
const EXAMPLE_TONES = ["kr-plan", "kr-run", "kr-verify"];

type Phase = "idle" | "submitting" | "planning" | "clarifying";

export function TaskInput({
  client,
  onTaskCreated,
  pollIntervalMs = 1000,
  planningTimeoutMs = 180_000,
  className = "",
  initialTarget,
  initialTargetUrl,
  devTargets = process.env.NEXT_PUBLIC_DEV_TARGETS === "1",
  initialPrompt = "",
}: TaskInputProps) {
  const t = useTranslations("approval");
  const router = useRouter();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [prompt, setPrompt] = useState(initialPrompt);
  const targetSelection = useTargetSelection({
    initialTarget,
    initialCustomUrl: initialTargetUrl,
  });
  // Users never pick a target: the site comes from the prompt, or from one question when the prompt names none
  // (#318). The developer picker (Gitea, custom URL) overrides it when it's switched on.
  const sites = supportedSites(devTargets);
  const detection = detectSite(prompt, sites);
  const [chosenSite, setChosenSite] = useState<Site | null>(null);
  const [useDevTarget, setUseDevTarget] = useState(Boolean(initialTarget || initialTargetUrl));
  const site: Site | null =
    detection.kind === "found" ? detection.site : detection.kind === "unsupported" ? null : chosenSite;
  const targetUrl = useDevTarget ? targetSelection.targetUrl.trim() : (site?.url ?? "");
  const canSubmit = useDevTarget ? targetSelection.isValid : site !== null;
  const [phase, setPhase] = useState<Phase>("idle");
  const [task, setTask] = useState<Task | null>(null);
  const [answer, setAnswer] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (phase !== "planning") return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  /** Polls GET /tasks/{id} until planned / needs_clarification / failed, or the timeout. */
  const waitForPlan = async (current: Task) => {
    setElapsed(0);
    setPhase("planning");
    const deadline = Date.now() + planningTimeoutMs;
    let latest = current;
    while (latest.status === "planning") {
      if (Date.now() > deadline) {
        throw new Error(t("taskInput.planningTimeout", { seconds: Math.round(planningTimeoutMs / 1000) }));
      }
      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
      if (!aliveRef.current) return;
      latest = await apiClient.getTask(current.id);
      if (!aliveRef.current) return;
      setTask(latest);
    }

    if (latest.status === "needs_clarification") {
      setTask(latest);
      setAnswer("");
      setPhase("clarifying");
      return;
    }
    if (latest.status === "failed") {
      throw new Error(latest.error?.message || t("taskInput.planningFailed"));
    }
    if (!latest.plan_id) {
      throw new Error(t("taskInput.noPlanId"));
    }
    onTaskCreated?.(latest);
    router.push(`/workflows/${latest.plan_id}/approval`);
  };

  const run = async (step: () => Promise<Task>) => {
    setError(null);
    setPhase("submitting");
    try {
      const created = await step();
      if (!aliveRef.current) return;
      setTask(created);
      await waitForPlan(created);
    } catch (err) {
      if (!aliveRef.current) return;
      setError(errorMessage(err, t("taskInput.createFailed")));
      setPhase("idle");
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || !canSubmit || phase !== "idle") return;
    void run(() => apiClient.createTask(prompt.trim(), targetUrl));
  };

  const handleClarify = (e: React.FormEvent) => {
    e.preventDefault();
    if (!task || !answer.trim()) return;
    void run(() => apiClient.clarifyTask(task.id, answer.trim()));
  };

  const busy = phase === "submitting" || phase === "planning";

  return (
    <section
      aria-label={t("taskInput.sectionAria")}
      data-testid="task-input-section"
      className={`kr-spectrum-border kr-ask rounded-[2rem] bg-ink-900/85 p-5 backdrop-blur-xl sm:p-7 ${className}`}
    >
      {/* console title bar */}
      <div aria-hidden="true" className="mb-5 flex items-center gap-2">
        <span className="size-3 rounded-full bg-danger shadow-[0_0_10px_var(--danger)]" />
        <span className="size-3 rounded-full bg-plan shadow-[0_0_10px_var(--plan)]" />
        <span className="size-3 rounded-full bg-verify shadow-[0_0_10px_var(--verify)]" />
        <span className="ml-3 flex items-center gap-1.5 font-mono text-xs text-ink-400">
          <Terminal className="size-3.5 text-ask" />
          {t("taskInput.consoleTitle")}
        </span>
        <span className="kr-chip ml-auto !py-0.5 !text-[10px]">
          <span className="kr-dot kr-dot-live !size-1.5" />
          {busy ? t("taskInput.statusPlanning") : t("taskInput.statusReady")}
        </span>
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-3">
          <label
            htmlFor="task-prompt-input"
            className="kr-display flex items-center gap-2 text-2xl font-extrabold text-white sm:text-3xl"
          >
            {t("taskInput.label")}
          </label>
          <textarea
            id="task-prompt-input"
            data-testid="task-prompt-input"
            name="prompt"
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={t("taskInput.placeholder")}
            disabled={phase !== "idle"}
            required
            className="kr-input w-full resize-none !rounded-2xl px-5 py-4 text-lg leading-relaxed sm:text-xl"
          />
          {!prompt && phase === "idle" && (
            <div className="flex flex-wrap gap-2" data-testid="example-prompts">
              {EXAMPLES.map((key, i) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setPrompt(t(`taskInput.examples.${key}`))}
                  className={`${EXAMPLE_TONES[i % EXAMPLE_TONES.length]} kr-chip kr-rise cursor-pointer !px-3.5 !py-1.5 !text-xs transition-all hover:shadow-[0_0_20px_-4px_var(--kr-tone)]`}
                  style={{ animationDelay: `${150 + i * 90}ms` }}
                >
                  <Sparkles aria-hidden="true" className="size-3" />
                  {t(`taskInput.examples.${key}`)}
                </button>
              ))}
            </div>
          )}
        </div>

        {!useDevTarget && prompt.trim() && (
          <SiteLine detection={detection} site={site} sites={sites} onChoose={setChosenSite} />
        )}

        {devTargets && (
          <details
            data-testid="dev-target-options"
            open={useDevTarget}
            onToggle={(e) => setUseDevTarget((e.target as HTMLDetailsElement).open)}
            className="rounded-2xl border border-dashed border-white/15 bg-white/[0.02] px-4 py-3 text-sm"
          >
            <summary className="cursor-pointer text-ink-400 hover:text-white">
              <Wrench aria-hidden="true" className="mr-1.5 inline size-3.5 text-plan" />
              {t("taskInput.devOptions")}
            </summary>
            <div className="mt-3">
              <TargetPicker
                value={targetSelection.targetType}
                customUrl={targetSelection.customUrl}
                onChange={(config) => {
                  targetSelection.selectTarget(config.type);
                  if (config.type === "custom") targetSelection.setCustomUrl(config.url);
                }}
                disabled={phase !== "idle"}
              />
            </div>
          </details>
        )}

        {/* The URL that will be sent; tests and scripts may set it directly (as a developer target) */}
        <input
          type="text"
          id="target-url-input"
          data-testid="target-url-input"
          name="target_url"
          className="hidden"
          value={targetUrl}
          onChange={(e) => {
            setUseDevTarget(true);
            targetSelection.selectTarget("custom");
            targetSelection.setCustomUrl(e.target.value);
          }}
        />

        {phase === "planning" && (
          <div
            role="status"
            data-testid="task-planning-status"
            className="kr-run kr-tone-card relative overflow-hidden rounded-2xl px-4 py-3 pb-4 text-sm text-ink-300"
          >
            <span aria-hidden="true" className="kr-rail absolute inset-x-0 bottom-0 !h-1 !rounded-none" />
            <Loader2 aria-hidden="true" className="mr-2 inline size-4 animate-spin text-run" />
            {t("taskInput.planningStatus", {
              elapsed: elapsed > 0 ? t("taskInput.elapsedSeconds", { seconds: elapsed }) : "",
              site: site?.name ?? t("taskInput.theSite"),
            })}
          </div>
        )}

        {error && (
          <div
            role="alert"
            data-testid="task-error-banner"
            className="kr-danger kr-tone-card flex items-start gap-2 rounded-2xl px-4 py-3 text-sm text-danger"
          >
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            {error}
          </div>
        )}

        {phase !== "clarifying" && (
          <div className="flex items-center justify-between gap-3 pt-1">
            <span aria-hidden="true" className="hidden items-center gap-1.5 font-mono text-xs text-ink-400 sm:flex">
              <CornerDownLeft className="size-3.5" /> {t("taskInput.flow")}
            </span>
            <button
              type="submit"
              data-testid="submit-task-btn"
              disabled={phase !== "idle" || !prompt.trim() || !canSubmit}
              className="kr-btn kr-btn-primary ml-auto px-6 py-3 text-sm"
            >
              {busy ? (
                <>
                  <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                  <span>{t("taskInput.planningButton")}</span>
                </>
              ) : (
                <>
                  <Sparkles aria-hidden="true" className="size-4" />
                  <span>{t("taskInput.submit")}</span>
                </>
              )}
            </button>
          </div>
        )}
      </form>

      {phase === "clarifying" && task && (
        <form onSubmit={handleClarify} data-testid="task-clarify-form" className="mt-4 flex flex-col gap-3">
          <p
            data-testid="task-clarification-question"
            className="kr-plan kr-tone-card rounded-2xl px-4 py-3 text-sm text-plan"
          >
            <HelpCircle aria-hidden="true" className="mr-2 inline size-4" />
            {task.clarification_question || t("taskInput.clarifyDefault")}
          </p>
          <label htmlFor="task-clarify-input" className="sr-only">
            {t("taskInput.answerLabel")}
          </label>
          <input
            id="task-clarify-input"
            data-testid="task-clarify-input"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder={t("taskInput.answerLabel")}
            required
            className="kr-input kr-plan w-full px-4 py-2.5 text-sm"
          />
          <div className="flex justify-end">
            <button
              type="submit"
              data-testid="task-clarify-submit"
              disabled={!answer.trim()}
              className="kr-btn kr-btn-tone kr-plan px-5 py-2.5 text-sm"
            >
              {t("taskInput.sendAnswer")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

/** Under the prompt: the website Krama will use, one question when the prompt names none, or why it can't. */
function SiteLine({
  detection,
  site,
  sites,
  onChoose,
}: {
  detection: ReturnType<typeof detectSite>;
  site: Site | null;
  sites: Site[];
  onChoose: (site: Site) => void;
}) {
  const t = useTranslations("approval");
  if (detection.kind === "unsupported") {
    return (
      <p data-testid="site-unsupported" className="kr-plan kr-tone-card rounded-xl px-3 py-2 text-sm text-plan">
        {t("taskInput.siteUnsupported", { name: detection.name, sites: sites.map((s) => s.name).join(", ") })}
      </p>
    );
  }
  if (detection.kind === "found") {
    return (
      <p data-testid="detected-site" className="flex items-center gap-2 text-sm text-ink-300">
        <Globe aria-hidden="true" className="size-4 text-verify" />
        {t("taskInput.website")} <span className="kr-chip kr-verify">{detection.site.name}</span>
      </p>
    );
  }
  const options = detection.kind === "several" ? detection.sites : sites;
  return (
    <div
      data-testid="site-question"
      className="flex flex-wrap items-center gap-2 text-sm text-ink-300"
    >
      <span>{t("taskInput.whichSite")}</span>
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          data-testid={`site-option-${option.id}`}
          aria-pressed={site?.id === option.id}
          onClick={() => onChoose(option)}
          className={`rounded-full border px-3.5 py-1 text-xs font-bold transition-all ${
            site?.id === option.id
              ? "border-approve bg-approve text-oncolor shadow-[0_0_18px_-4px_var(--approve)]"
              : "border-white/15 text-ink-300 hover:border-approve hover:text-white"
          }`}
        >
          {option.name}
        </button>
      ))}
    </div>
  );
}
