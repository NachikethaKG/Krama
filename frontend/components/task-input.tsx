"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Task } from "@krama/contracts-ts";

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
}

const EXAMPLES = [
  "Show me how to create a private GitHub repository",
  "How do I add a label to a GitHub repository?",
  "Create a new branch on GitHub",
];

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
}: TaskInputProps) {
  const router = useRouter();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [prompt, setPrompt] = useState("");
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
        throw new Error(
          `Planning is taking longer than ${Math.round(planningTimeoutMs / 1000)} s. Try again in a moment.`,
        );
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
      throw new Error(latest.error?.message || "Planning failed");
    }
    if (!latest.plan_id) {
      throw new Error("The task is planned but has no plan id");
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
      setError(errorMessage(err, "Failed to create the task"));
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
      aria-label="New tutorial"
      data-testid="task-input-section"
      className={`rounded-xl border border-zinc-200 bg-white p-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900 ${className}`}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label htmlFor="task-prompt-input" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            What do you want to learn?
          </label>
          <textarea
            id="task-prompt-input"
            data-testid="task-prompt-input"
            name="prompt"
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Show me how to create a private GitHub repository"
            disabled={phase !== "idle"}
            required
            className="w-full rounded-lg border border-zinc-300 px-3.5 py-2.5 text-base text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          {!prompt && phase === "idle" && (
            <div className="flex flex-wrap gap-2" data-testid="example-prompts">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setPrompt(example)}
                  className="rounded-full border border-zinc-200 px-3 py-1 text-xs text-zinc-600 hover:border-indigo-300 hover:text-indigo-700 dark:border-zinc-700 dark:text-zinc-400"
                >
                  {example}
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
            className="rounded-lg border border-dashed border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
          >
            <summary className="cursor-pointer text-zinc-500">Developer options: choose the target site</summary>
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
            className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900 dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-200"
          >
            Planning the steps… {elapsed > 0 ? `${elapsed} s` : ""} Krama is opening {site?.name ?? "the site"} and
            working out each step. This usually takes 15–60 seconds.
          </div>
        )}

        {error && (
          <div
            role="alert"
            data-testid="task-error-banner"
            className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300"
          >
            {error}
          </div>
        )}

        {phase !== "clarifying" && (
          <div className="flex justify-end pt-2">
            <button
              type="submit"
              data-testid="submit-task-btn"
              disabled={phase !== "idle" || !prompt.trim() || !canSubmit}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-xs transition-colors hover:bg-indigo-700 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-indigo-600 dark:hover:bg-indigo-500"
            >
              {busy ? (
                <>
                  <svg aria-hidden="true" className="size-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Planning…</span>
                </>
              ) : (
                <span>Plan the steps</span>
              )}
            </button>
          </div>
        )}
      </form>

      {phase === "clarifying" && task && (
        <form onSubmit={handleClarify} data-testid="task-clarify-form" className="mt-4 flex flex-col gap-3">
          <p
            data-testid="task-clarification-question"
            className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-200"
          >
            {task.clarification_question || "Krama needs a little more detail to plan this."}
          </p>
          <label htmlFor="task-clarify-input" className="sr-only">
            Your answer
          </label>
          <input
            id="task-clarify-input"
            data-testid="task-clarify-input"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Your answer"
            required
            className="w-full rounded-lg border border-zinc-300 px-3.5 py-2 text-sm text-zinc-900 focus:border-indigo-500 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <div className="flex justify-end">
            <button
              type="submit"
              data-testid="task-clarify-submit"
              disabled={!answer.trim()}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Send answer
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
  if (detection.kind === "unsupported") {
    return (
      <p data-testid="site-unsupported" className="text-sm text-amber-700 dark:text-amber-400">
        Krama can&apos;t do tasks on {detection.name} yet. It works on {sites.map((s) => s.name).join(", ")}.
      </p>
    );
  }
  if (detection.kind === "found") {
    return (
      <p data-testid="detected-site" className="text-sm text-zinc-600 dark:text-zinc-400">
        Website: <span className="font-medium text-zinc-900 dark:text-zinc-100">{detection.site.name}</span>
      </p>
    );
  }
  const options = detection.kind === "several" ? detection.sites : sites;
  return (
    <div
      data-testid="site-question"
      className="flex flex-wrap items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400"
    >
      <span>Which website is this for?</span>
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          data-testid={`site-option-${option.id}`}
          aria-pressed={site?.id === option.id}
          onClick={() => onChoose(option)}
          className={`rounded-full border px-3 py-1 text-xs font-medium ${
            site?.id === option.id
              ? "border-indigo-500 bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300"
              : "border-zinc-300 text-zinc-700 hover:border-indigo-300 dark:border-zinc-700 dark:text-zinc-300"
          }`}
        >
          {option.name}
        </button>
      ))}
    </div>
  );
}
