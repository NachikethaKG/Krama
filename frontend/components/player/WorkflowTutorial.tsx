"use client";

import { FileText } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { compileWorkflow, type TutorialSpec } from "@krama/tutorial-compiler";
import type { Language, Translation, Workflow } from "@krama/contracts-ts";
import type { eventWithTime } from "@rrweb/types";
import { type ApiClient, errorMessage, getApiClient, isApiError } from "@/lib/api";
import { apiBaseUrl, artifactUrl } from "@/lib/artifacts";
import { workflowFreshness } from "@/lib/freshness";
import type { TutorialFreshnessStatus } from "@/types/tutorial";
import { TutorialLanguageSelect } from "./TutorialLanguageSelect";
import { TutorialPlayer } from "./TutorialPlayer";

/** How long to wait for a translation being made (#427): 2 s between asks, 2 minutes in all. */
export const TRANSLATION_POLL_MS = 2000;
const TRANSLATION_TRIES = 60;

/** The workflow with its title and step texts in the translation's language; labels came back exact (#422). */
export function applyTranslation(workflow: Workflow, translation: Translation): Workflow {
  const texts = new Map(translation.steps.map((s) => [s.step_seq, s.text]));
  return {
    ...workflow,
    title: translation.title || workflow.title,
    steps: workflow.steps.map((s) => ({ ...s, instruction_text: texts.get(s.seq) ?? s.instruction_text })),
  };
}

async function waitForTranslation(
  api: ApiClient,
  workflowId: string,
  language: Language,
  stale: () => boolean,
  pollMs: number,
): Promise<Translation | null> {
  for (let i = 0; i < TRANSLATION_TRIES && !stale(); i++) {
    const translation = await api.getTranslation(workflowId, language);
    if (translation.status !== "translating") return translation;
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  return null;
}

type Translated = { language: Language; spec: TutorialSpec; partly: boolean };

type Loaded =
  | { state: "loading" }
  | { state: "error"; cause: unknown }
  | { state: "ready"; workflow: Workflow; spec: TutorialSpec; recording: eventWithTime[] | null };

/** A recording can drive the stage only if the steps say where in it they happened (workflow_steps.start_ms). */
function hasStepTiming(workflow: Workflow): boolean {
  return workflow.steps.length > 0 && workflow.steps.every((s) => typeof (s.timing?.start_ms ?? s.start_ms) === "number");
}

async function loadRecording(workflow: Workflow): Promise<eventWithTime[] | null> {
  const url = artifactUrl(workflow.recording_path);
  if (!url || !hasStepTiming(workflow)) return null;
  try {
    // The artifact store needs the session cookie (#94); without it every tutorial fell back to the wireframe (#104).
    const response = await fetch(url, { credentials: "include" });
    if (!response.ok) return null;
    const body: unknown = await response.json();
    const events = Array.isArray(body) ? body : (body as { events?: unknown }).events;
    return Array.isArray(events) && events.length > 1 ? (events as eventWithTime[]) : null;
  } catch {
    return null; // the tutorial still works on the wireframe backdrop
  }
}

/**
 * The tutorial of a stored Verified Workflow (#83): GET /workflows/{id}, compiled to a TutorialSpec, played over
 * the run's real rrweb recording when the steps carry their timing.
 */
export function WorkflowTutorial({
  workflowId,
  pollMs = TRANSLATION_POLL_MS,
}: {
  workflowId: string;
  pollMs?: number;
}) {
  const t = useTranslations("player");
  const [loaded, setLoaded] = useState<Loaded>({ state: "loading" });
  // The tutorial's own language (#427), separate from the app's UI language.
  const [language, setLanguage] = useState<Language>("en");
  const [translated, setTranslated] = useState<Translated | null>(null);
  const [translating, setTranslating] = useState(false);
  const [translateFailed, setTranslateFailed] = useState(false);
  const request = useRef(0);

  const chooseLanguage = async (next: Language) => {
    if (loaded.state !== "ready") return;
    const mine = ++request.current;
    setLanguage(next);
    setTranslateFailed(false);
    if (next === "en") {
      setTranslated(null);
      setTranslating(false);
      return;
    }
    setTranslating(true);
    try {
      const stale = () => mine !== request.current;
      const translation = await waitForTranslation(getApiClient(), loaded.workflow.id, next, stale, pollMs);
      if (stale()) return;
      if (translation === null || translation.status !== "ready") throw new Error("not translated");
      const spec = compileWorkflow(applyTranslation(loaded.workflow, translation));
      setTranslated({ language: next, spec, partly: translation.steps.some((s) => s.translated === false) });
    } catch {
      if (mine !== request.current) return;
      setTranslateFailed(true);
      setTranslated(null);
      setLanguage("en");
    } finally {
      if (mine === request.current) setTranslating(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const workflow = await getApiClient().getWorkflow(workflowId);
        const spec = compileWorkflow(workflow);
        const recording = await loadRecording(workflow);
        if (!cancelled) setLoaded({ state: "ready", workflow, spec, recording });
      } catch (err) {
        if (cancelled) return;
        setLoaded({ state: "error", cause: err });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workflowId]);

  if (loaded.state === "loading") {
    return (
      <p role="status" data-testid="workflow-tutorial-loading" className="flex flex-col items-center gap-4 py-24 text-center text-sm text-ink-300">
        <span aria-hidden="true" className="kr-spectrum-border size-14 animate-spin rounded-full bg-ink-900 [animation-duration:2.5s]" />
        {t("workflowTutorial.loading")}
      </p>
    );
  }
  if (loaded.state === "error") {
    return (
      <p role="alert" data-testid="workflow-tutorial-error" className="mx-auto my-16 max-w-lg rounded-3xl border border-danger/40 bg-danger/10 px-6 py-8 text-center text-sm font-semibold text-danger">
        {isApiError(loaded.cause, "not_found")
          ? t("workflowTutorial.notFound")
          : errorMessage(loaded.cause, t("workflowTutorial.loadError"))}
      </p>
    );
  }
  const guideUrl = `${apiBaseUrl()}/workflows/${encodeURIComponent(loaded.workflow.id)}/guide.md`;
  return (
    <div data-testid="workflow-tutorial" data-real-ui={loaded.recording ? "true" : "false"}>
      <div className="mx-auto mb-3 flex max-w-7xl items-center justify-end px-4">
        <a href={guideUrl} className="kr-btn kr-btn-ghost kr-learn px-3.5 py-1.5 text-xs">
          <FileText aria-hidden="true" className="size-3.5" />
          {t("workflowTutorial.readAsText")}
        </a>
      </div>
      {translating || translateFailed || translated?.partly ? (
        <p
          role="status"
          data-testid="tutorial-language-status"
          className="mx-auto mb-3 max-w-7xl px-4 text-xs text-ink-300"
        >
          {translating
            ? t("language.translating")
            : translateFailed
              ? t("language.failed")
              : t("language.partly")}
        </p>
      ) : null}
      <TutorialPlayer
        key={translated?.language ?? "en"}
        spec={translated?.spec ?? loaded.spec}
        recording={loaded.recording}
        workflowId={loaded.workflow.id}
        status={freshness(loaded.workflow)}
        language={translated?.language ?? "en"}
        headerExtra={
          <TutorialLanguageSelect
            value={language}
            onChange={(next) => void chooseLanguage(next)}
            label={t("language.label")}
            disabled={translating}
          />
        }
      />
    </div>
  );
}

/** The stored workflow's status as the player's badge (without it the badge always said "Verified"). */
export function freshness(workflow: Pick<Workflow, "status" | "current_version_source">): TutorialFreshnessStatus {
  return workflowFreshness(workflow);
}
