"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Task } from "@krama/contracts-ts";

import { ManualLoginGuide } from "@/components/session";
import { TargetPicker, type TargetType, useTargetSelection } from "@/components/target-picker";
import { type ApiClient, errorMessage, getApiClient } from "@/lib/api";

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
}

type Phase = "idle" | "submitting" | "planning" | "clarifying";

export function TaskInput({
  client,
  onTaskCreated,
  pollIntervalMs = 1000,
  planningTimeoutMs = 180_000,
  className = "",
  initialTarget,
  initialTargetUrl,
}: TaskInputProps) {
  const router = useRouter();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [prompt, setPrompt] = useState("");
  const targetSelection = useTargetSelection({
    initialTarget,
    initialCustomUrl: initialTargetUrl,
  });
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
    if (!prompt.trim() || !targetSelection.isValid || phase !== "idle") return;
    void run(() => apiClient.createTask(prompt.trim(), targetSelection.targetUrl.trim()));
  };

  const handleClarify = (e: React.FormEvent) => {
    e.preventDefault();
    if (!task || !answer.trim()) return;
    void run(() => apiClient.clarifyTask(task.id, answer.trim()));
  };

  const busy = phase === "submitting" || phase === "planning";

  return (
    <section
      aria-label="Create Task"
      data-testid="task-input-section"
      className={`rounded-xl border border-zinc-200 bg-white p-6 shadow-xs dark:border-zinc-800 dark:bg-zinc-900 ${className}`}
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="task-prompt-input"
            className="text-xs font-semibold uppercase tracking-wider text-zinc-600 dark:text-zinc-400"
          >
            Task Prompt
          </label>
          <textarea
            id="task-prompt-input"
            data-testid="task-prompt-input"
            name="prompt"
            rows={3}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Create a repository in local Gitea"
            disabled={phase !== "idle"}
            required
            className="w-full rounded-lg border border-zinc-300 px-3.5 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </div>

        <TargetPicker
          value={targetSelection.targetType}
          customUrl={targetSelection.customUrl}
          onChange={(config) => {
            targetSelection.selectTarget(config.type);
            if (config.type === "custom") {
              targetSelection.setCustomUrl(config.url);
            }
          }}
          disabled={phase !== "idle"}
        />

        {targetSelection.targetType === "github" && (
          <ManualLoginGuide
            target="github"
            client={apiClient}
            pollIntervalMs={pollIntervalMs}
          />
        )}

        {/* Backwards-compatible input for existing tests and form submit */}
        <input
          type="text"
          id="target-url-input"
          data-testid="target-url-input"
          name="target_url"
          className="hidden"
          value={targetSelection.targetUrl}
          onChange={(e) => {
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
            Planning… {elapsed > 0 ? `${elapsed} s` : ""} The agent is reading the page and writing a plan; this
            usually takes 15–60 seconds.
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
              disabled={phase !== "idle" || !prompt.trim() || !targetSelection.isValid}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-xs transition-colors hover:bg-indigo-700 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-indigo-600 dark:hover:bg-indigo-500"
            >
              {busy ? (
                <>
                  <svg aria-hidden="true" className="size-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Generating Plan…</span>
                </>
              ) : (
                <span>Generate Plan</span>
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
            {task.clarification_question || "The agent needs more detail to plan this task."}
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
