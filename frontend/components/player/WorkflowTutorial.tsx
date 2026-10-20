"use client";

import { useEffect, useState } from "react";
import { compileWorkflow, type TutorialSpec } from "@krama/tutorial-compiler";
import type { Workflow } from "@krama/contracts-ts";
import type { eventWithTime } from "@rrweb/types";
import { errorMessage, getApiClient, isApiError } from "@/lib/api";
import { apiBaseUrl, artifactUrl } from "@/lib/artifacts";
import { TutorialPlayer } from "./TutorialPlayer";

type Loaded =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; workflow: Workflow; spec: TutorialSpec; recording: eventWithTime[] | null };

/** A recording can drive the stage only if the steps say where in it they happened (workflow_steps.start_ms). */
function hasStepTiming(workflow: Workflow): boolean {
  return workflow.steps.length > 0 && workflow.steps.every((s) => typeof (s.timing?.start_ms ?? s.start_ms) === "number");
}

async function loadRecording(workflow: Workflow): Promise<eventWithTime[] | null> {
  const url = artifactUrl(workflow.recording_path);
  if (!url || !hasStepTiming(workflow)) return null;
  try {
    const response = await fetch(url);
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
export function WorkflowTutorial({ workflowId }: { workflowId: string }) {
  const [loaded, setLoaded] = useState<Loaded>({ state: "loading" });

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
        const message = isApiError(err, "not_found")
          ? "There is no stored workflow with this id."
          : errorMessage(err, "The tutorial could not be loaded.");
        setLoaded({ state: "error", message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [workflowId]);

  if (loaded.state === "loading") {
    return (
      <p role="status" data-testid="workflow-tutorial-loading" className="py-20 text-center text-sm text-zinc-500">
        Loading the tutorial…
      </p>
    );
  }
  if (loaded.state === "error") {
    return (
      <p role="alert" data-testid="workflow-tutorial-error" className="py-20 text-center text-sm text-rose-600">
        {loaded.message}
      </p>
    );
  }
  const guideUrl = `${apiBaseUrl()}/workflows/${encodeURIComponent(loaded.workflow.id)}/guide.md`;
  return (
    <div data-testid="workflow-tutorial" data-real-ui={loaded.recording ? "true" : "false"}>
      <div className="mx-auto mb-3 flex max-w-7xl items-center justify-end px-4">
        <a href={guideUrl} className="text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-400">
          Text guide (Markdown)
        </a>
      </div>
      <TutorialPlayer spec={loaded.spec} recording={loaded.recording} />
    </div>
  );
}
