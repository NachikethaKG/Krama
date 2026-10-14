"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Task } from "@krama/contracts-ts";

import { type ApiClient, getApiClient } from "@/lib/api";

export interface TaskInputProps {
  client?: ApiClient;
  onTaskCreated?: (task: Task) => void;
  className?: string;
}

export function TaskInput({ client, onTaskCreated, className = "" }: TaskInputProps) {
  const router = useRouter();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [prompt, setPrompt] = useState("");
  const [targetUrl, setTargetUrl] = useState("http://localhost:3001");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const task = await apiClient.createTask(prompt.trim(), targetUrl.trim());

      let planId = task.plan_id;
      // If task is in planning state without plan_id, poll briefly
      if (!planId && task.status === "planning" && typeof apiClient.getTask === "function") {
        for (let i = 0; i < 20; i++) {
          await new Promise((resolve) => setTimeout(resolve, 300));
          const updated = await apiClient.getTask(task.id);
          if (updated.plan_id) {
            planId = updated.plan_id;
            break;
          }
          if (updated.status === "failed") {
            throw new Error(updated.error?.message || "Task planning failed");
          }
        }
      }

      const finalPlanId = planId || "default";
      if (onTaskCreated) {
        onTaskCreated(task);
      }
      router.push(`/workflows/${finalPlanId}/approval`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create task");
    } finally {
      setIsSubmitting(false);
    }
  };

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
            disabled={isSubmitting}
            required
            className="w-full rounded-lg border border-zinc-300 px-3.5 py-2.5 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="target-url-input"
            className="text-xs font-semibold uppercase tracking-wider text-zinc-600 dark:text-zinc-400"
          >
            Target System URL
          </label>
          <input
            id="target-url-input"
            data-testid="target-url-input"
            type="url"
            name="target_url"
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            placeholder="http://localhost:3001"
            disabled={isSubmitting}
            required
            className="w-full rounded-lg border border-zinc-300 px-3.5 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </div>

        {error && (
          <div
            role="alert"
            data-testid="task-error-banner"
            className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300"
          >
            {error}
          </div>
        )}

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            data-testid="submit-task-btn"
            disabled={isSubmitting || !prompt.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-xs transition-colors hover:bg-indigo-700 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-indigo-600 dark:hover:bg-indigo-500"
          >
            {isSubmitting ? (
              <>
                <svg
                  aria-hidden="true"
                  className="size-4 animate-spin text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"
                  />
                </svg>
                <span>Generating Plan…</span>
              </>
            ) : (
              <span>Generate Plan</span>
            )}
          </button>
        </div>
      </form>
    </section>
  );
}
