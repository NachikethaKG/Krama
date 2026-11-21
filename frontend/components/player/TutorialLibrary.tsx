"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { WorkflowSummary } from "@krama/contracts-ts";
import { errorMessage, getApiClient } from "@/lib/api";

/** Each row gets the next spectrum colour. */
const TONES = ["kr-learn", "kr-ask", "kr-run", "kr-plan", "kr-verify", "kr-approve"];

/** Every stored Verified Workflow, each one a tutorial (#83). Real API mode only. */
export function TutorialLibrary() {
  const t = useTranslations("player");
  const [items, setItems] = useState<WorkflowSummary[] | null>(null);
  const [error, setError] = useState<{ cause: unknown } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getApiClient()
      .getWorkflows()
      .then((page) => !cancelled && setItems(page.items))
      .catch((err) => !cancelled && setError({ cause: err }));
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <p role="alert" className="py-20 text-center text-sm font-semibold text-danger">
        {errorMessage(error.cause, t("tutorialLibrary.loadError"))}
      </p>
    );
  }
  if (items === null) {
    return (
      <p role="status" className="flex items-center justify-center gap-2 py-20 text-center text-sm text-ink-400">
        <Loader2 aria-hidden="true" className="size-4 animate-spin text-learn" />
        {t("tutorialLibrary.loading")}
      </p>
    );
  }
  if (items.length === 0) {
    return <p className="py-20 text-center text-sm text-ink-400">{t("tutorialLibrary.empty")}</p>;
  }
  return (
    <ul data-testid="tutorial-library" className="mx-auto grid max-w-5xl gap-4 px-4 sm:grid-cols-2">
      {items.map((w, i) => (
        <li key={w.id} className={`${TONES[i % TONES.length]} kr-rise`} style={{ animationDelay: `${i * 50}ms` }}>
          <Link
            href={`/tutorials/${w.id}`}
            className="kr-tone-card group flex items-center justify-between gap-3 rounded-2xl p-4"
          >
            <span>
              <span className="block text-sm font-bold text-white">{w.title}</span>
              <span className="mt-1 block text-xs text-ink-400">
                {t("tutorialLibrary.meta", { count: w.step_count, app: w.target_app ?? t("tutorialLibrary.siteFallback") })}
                {w.created_at ? ` · ${w.created_at.slice(0, 10)}` : ""}
              </span>
            </span>
            <ArrowUpRight
              aria-hidden="true"
              className="size-5 shrink-0 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
              style={{ color: "var(--kr-tone)" }}
            />
          </Link>
        </li>
      ))}
    </ul>
  );
}
