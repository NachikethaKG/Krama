"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { WorkflowSummary } from "@krama/contracts-ts";
import { errorMessage, getApiClient } from "@/lib/api";

/** Every stored Verified Workflow, each one a tutorial (#83). Real API mode only. */
export function TutorialLibrary() {
  const [items, setItems] = useState<WorkflowSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getApiClient()
      .getWorkflows()
      .then((page) => !cancelled && setItems(page.items))
      .catch((err) => !cancelled && setError(errorMessage(err, "The tutorials could not be loaded.")));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <p role="alert" className="py-20 text-center text-sm text-rose-600">
        {error}
      </p>
    );
  }
  if (items === null) {
    return (
      <p role="status" className="py-20 text-center text-sm text-zinc-500">
        Loading tutorials…
      </p>
    );
  }
  if (items.length === 0) {
    return <p className="py-20 text-center text-sm text-zinc-500">No verified workflows yet.</p>;
  }
  return (
    <ul data-testid="tutorial-library" className="mx-auto grid max-w-5xl gap-3 px-4 sm:grid-cols-2">
      {items.map((w) => (
        <li key={w.id}>
          <Link
            href={`/tutorials/${w.id}`}
            className="block rounded-lg border border-zinc-200 bg-white p-4 hover:border-indigo-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500 dark:border-zinc-800 dark:bg-zinc-950"
          >
            <span className="block text-sm font-semibold text-zinc-900 dark:text-zinc-100">{w.title}</span>
            <span className="mt-1 block text-xs text-zinc-500">
              {w.step_count} steps · {w.target_app ?? "site"}
              {w.created_at ? ` · ${w.created_at.slice(0, 10)}` : ""}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
