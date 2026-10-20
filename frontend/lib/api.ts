// Thin API client seam (docs/architecture.md §4). `mock` mode serves contract-valid fixtures, so the UI never
// waits on the backend; `http` mode talks to the real backend (docs/api-contract.md, contracts/openapi.json).
import type {
  ApiError,
  HealthResponse,
  Plan,
  PlannedStep,
  Run,
  RunEvent,
  RunPage,
  Task,
  Workflow,
  WorkflowPage,
} from "@krama/contracts-ts";

import { apiBaseUrl, artifactUrl, normalizeBaseUrl } from "./artifacts";
import {
  blockedWorkflowFixture,
  failedWorkflowFixture,
  giteaBlockedEventsFixture,
  giteaEventsFixture,
  giteaFailedEventsFixture,
  giteaPausedEventsFixture,
  giteaReplanEventsFixture,
  giteaReplanReviewEventsFixture,
  giteaWorkflowFixture,
  mockRunDetails,
  mockRunsList,
  pausedWorkflowFixture,
  replanProposedPlanFixture,
  replanWorkflowFixture,
  restrictedWorkflowFixture,
  toPlannedStep,
  validWorkflowFixture,
  workflowFixtures,
} from "./fixtures";
import type {
  RunDetails,
  RunListItem,
  RunsPage,
  StepEvidenceDetail,
  StepVerificationEvidence,
  VerificationEvidenceMethod,
} from "./types";

export type {
  HealthResponse,
  Plan,
  Run,
  RunDetails,
  RunEvent,
  RunListItem,
  RunsPage,
  StepEvidenceDetail,
  StepVerificationEvidence,
  Task,
  VerificationEvidenceMethod,
  Workflow,
};
export {
  artifactUrl,
  blockedWorkflowFixture,
  failedWorkflowFixture,
  giteaBlockedEventsFixture,
  giteaEventsFixture,
  giteaFailedEventsFixture,
  giteaPausedEventsFixture,
  giteaReplanEventsFixture,
  giteaReplanReviewEventsFixture,
  giteaWorkflowFixture,
  mockRunDetails,
  mockRunsList,
  normalizeBaseUrl,
  pausedWorkflowFixture,
  replanWorkflowFixture,
  restrictedWorkflowFixture,
  validWorkflowFixture,
  workflowFixtures,
};

export type ApiMode = "mock" | "http";
export type ConfirmDecision = "allow" | "deny";

/** `run.completed`, `run.failed` and `run.cancelled` are final: the server closes the stream after them. */
export const FINAL_EVENT_TYPES: ReadonlySet<RunEvent["type"]> = new Set([
  "run.completed",
  "run.failed",
  "run.cancelled",
]);

export function isFinalEvent(event: RunEvent): boolean {
  return FINAL_EVENT_TYPES.has(event.type);
}

export interface StreamOptions {
  signal?: AbortSignal;
  /** Resume after this event seq (sent as `Last-Event-ID`). 0 / undefined replays the whole run. */
  lastEventId?: number;
  /** Mock only: replay speed multiplier. */
  speed?: number;
  /** Called before each reconnect attempt after an unexpected drop. */
  onReconnect?: (attempt: number) => void;
  /** Reconnect attempts in a row without receiving an event before giving up (default 5). */
  maxReconnects?: number;
  /** Base delay between reconnects in ms (default 1000, doubled per attempt, capped at 10 s). */
  reconnectDelayMs?: number;
}

export interface GetRunsOptions {
  limit?: number;
  /** Opaque keyset cursor from a previous page's `nextCursor`. */
  cursor?: string | null;
}

/** An error response from the API, carrying the contract's `ErrorResponse` fields. */
export class ApiRequestError extends Error {
  readonly status: number;
  readonly code?: ApiError["code"];
  readonly details?: Record<string, unknown>;

  constructor(message: string, status: number, error?: Partial<ApiError>) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = error?.code;
    this.details = error?.details as Record<string, unknown> | undefined;
  }
}

export function isApiError(err: unknown, code?: ApiError["code"], status?: number): err is ApiRequestError {
  if (!(err instanceof ApiRequestError)) return false;
  if (code !== undefined && err.code !== code) return false;
  if (status !== undefined && err.status !== status) return false;
  return true;
}

/** A readable message for any thrown value. */
export function errorMessage(err: unknown, fallback = "Something went wrong"): string {
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === "string" && err) return err;
  return fallback;
}

/**
 * API client interface for the Krama frontend (docs/architecture.md §4).
 * Decouples UI components and pages from whether the backend is live or mocked.
 */
export interface ApiClient {
  health(): Promise<HealthResponse>;
  /** POST /tasks → 202 Task (status `planning`). */
  createTask(prompt: string, targetUrl: string): Promise<Task>;
  /** GET /tasks/{id}. Poll until `planned`, `needs_clarification` or `failed`. */
  getTask(taskId: string): Promise<Task>;
  /** POST /tasks/{id}/clarify → 202 Task (planning again). */
  clarifyTask(taskId: string, answer: string): Promise<Task>;
  getPlan(planId: string): Promise<Plan>;
  /** PATCH /plans/{id}. 409 `conflict` when the revision is stale, `plan_not_editable` when approved/rejected. */
  updatePlan(planId: string, revision: number, steps: PlannedStep[]): Promise<Plan>;
  /** POST /plans/{id}/approve → 201 Run. The returned Run's `id` is the RUN id. */
  approvePlan(planId: string, revision: number): Promise<Run>;
  /** POST /plans/{id}/reject → Plan. */
  rejectPlan(planId: string, reason?: string): Promise<Plan>;
  getRun(runId: string): Promise<Run>;
  /** GET /runs?limit&cursor (newest first, opaque keyset cursor). */
  getRuns(options?: GetRunsOptions): Promise<RunsPage>;
  /** POST /runs/{id}/cancel. 409 `run_not_active` when the run already finished. */
  cancelRun(runId: string): Promise<Run>;
  /** POST /runs/{id}/confirm. 409 `run_not_active` unless the run is paused at exactly `stepSeq`. */
  confirmRun(runId: string, stepSeq: number, decision: ConfirmDecision): Promise<Run>;
  /** GET /runs/{id}/events (SSE). Ends after a final event; reconnects with Last-Event-ID on a drop. */
  streamRunEvents(runId: string, options?: StreamOptions): AsyncIterable<RunEvent>;
  /** GET /workflows/{id}: the verified workflow. */
  getWorkflow(id: string): Promise<Workflow>;
  /** GET /workflows: stored workflows, newest first (the tutorial library). */
  getWorkflows(limit?: number): Promise<WorkflowPage>;
  /** Run + plan + task + workflow, shaped for the run detail / evidence page. */
  getRunDetails(runId: string): Promise<RunDetails>;
}

// ---------------------------------------------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------------------------------------------

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("aborted", "AbortError"));
      return;
    }
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException("aborted", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

function isAbortError(err: unknown): boolean {
  return (
    (err instanceof DOMException && err.name === "AbortError") ||
    (err instanceof Error && err.name === "AbortError")
  );
}

function durationSeconds(startedAt?: string | null, finishedAt?: string | null): number | null {
  if (!startedAt || !finishedAt) return null;
  const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  return Number.isFinite(ms) ? Math.max(0, Math.round(ms / 1000)) : null;
}

export function runToListItem(run: Run, prompt: string | null): RunListItem {
  return {
    id: run.id,
    prompt,
    status: run.status,
    createdAt: run.created_at,
    startedAt: run.started_at,
    finishedAt: run.finished_at,
    durationSeconds: durationSeconds(run.started_at, run.finished_at),
    workflowId: run.workflow_id,
    planId: run.plan_id,
    retryCount: run.retry_count,
  };
}

function evidenceMethod(methods: readonly string[]): VerificationEvidenceMethod {
  if (methods.includes("aria")) return "aria";
  if (methods.includes("network")) return "network";
  if (methods.includes("vision")) return "vision";
  return "url_dom";
}

/** Workflow steps → evidence cards. Screenshot keys are resolved with `resolve` (artifactUrl in http mode). */
export function workflowEvidenceSteps(
  workflow: Workflow,
  resolve: (ref: string | null | undefined) => string | undefined,
): StepEvidenceDetail[] {
  return workflow.steps.map((s, idx) => {
    const result = s.verification?.result;
    const screenshotUrl = resolve(s.screenshot_path ?? s.observed_state?.screenshot_path ?? null) ?? null;
    return {
      id: s.id ?? `step-${s.seq ?? idx + 1}`,
      seq: s.seq ?? idx + 1,
      instructionText: s.instruction_text,
      actionType: s.action?.type ?? "action",
      targetRole: s.target?.role,
      targetName: s.target?.name,
      risk: s.risk ?? "low",
      status: result === "verified" ? "verified" : result === "failed" ? "failed" : "pending",
      evidence: {
        method: evidenceMethod(s.verification?.method ?? []),
        methods: s.verification?.method ?? [],
        confidence: s.verification?.confidence ?? null,
        screenshotUrl,
        observedAt: s.observed_state?.captured_at ?? null,
      },
      screenshotUrl,
      expectedState: s.expected_state,
      observedState: s.observed_state,
      timing:
        s.timing || s.start_ms != null
          ? {
              startMs: s.timing?.start_ms ?? s.start_ms ?? null,
              endMs: s.timing?.end_ms ?? s.end_ms ?? null,
              durationMs:
                (s.timing?.end_ms ?? s.end_ms) != null && (s.timing?.start_ms ?? s.start_ms) != null
                  ? (s.timing?.end_ms ?? s.end_ms ?? 0) - (s.timing?.start_ms ?? s.start_ms ?? 0)
                  : null,
            }
          : undefined,
    };
  });
}

/** Plan steps (no run evidence yet) → pending evidence cards. */
function planEvidenceSteps(plan: Plan): StepEvidenceDetail[] {
  return plan.steps.map((s) => ({
    id: `${plan.id}-${s.seq}`,
    seq: s.seq,
    instructionText: s.instruction_text,
    actionType: s.action?.type ?? "action",
    targetRole: s.target?.role,
    targetName: s.target?.name,
    risk: s.risk,
    status: "pending",
    evidence: { method: "url_dom", methods: [], confidence: null, screenshotUrl: null, observedAt: null },
    screenshotUrl: null,
    expectedState: s.expected_state,
  }));
}

function buildRunDetails(
  run: Run,
  plan: Plan | null,
  task: Task | null,
  workflow: Workflow | null,
  resolve: (ref: string | null | undefined) => string | undefined,
): RunDetails {
  const steps = workflow ? workflowEvidenceSteps(workflow, resolve) : plan ? planEvidenceSteps(plan) : [];
  return {
    run: runToListItem(run, task?.prompt ?? workflow?.task ?? null),
    workflow,
    plan,
    task,
    error: run.error ?? null,
    targetUrl: task?.target_url ?? workflow?.target_url ?? workflow?.target?.base_url ?? undefined,
    targetApp: task?.interpretation?.app ?? workflow?.target_app ?? workflow?.target?.app ?? undefined,
    steps,
    summary: {
      totalSteps: steps.length,
      verifiedSteps: steps.filter((s) => s.status === "verified").length,
      failedSteps: steps.filter((s) => s.status === "failed").length,
      durationSeconds: durationSeconds(run.started_at, run.finished_at),
    },
  };
}

// ---------------------------------------------------------------------------------------------------------------
// SSE parsing
// ---------------------------------------------------------------------------------------------------------------

/**
 * Parses an SSE byte stream into RunEvent objects (docs/api-contract.md: `id: <seq>`, `event: <type>`, JSON `data`).
 * Comment lines (`: ping` keep-alives) are ignored.
 */
export async function* parseEventStream(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<RunEvent, void, unknown> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const parseFrame = (part: string): RunEvent | null => {
    let dataStr = "";
    for (const line of part.split(/\r?\n/)) {
      if (line.startsWith(":")) continue;
      if (line.startsWith("data:")) {
        const dataPart = line.slice(5).replace(/^ /, "");
        dataStr = dataStr ? `${dataStr}\n${dataPart}` : dataPart;
      }
    }
    if (!dataStr) return null;
    try {
      return JSON.parse(dataStr) as RunEvent;
    } catch {
      return null;
    }
  };

  try {
    while (!signal?.aborted) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split(/\r?\n\r?\n/);
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        if (!part.trim()) continue;
        const event = parseFrame(part);
        if (event) yield event;
      }
    }
    if (!signal?.aborted && buffer.trim()) {
      const event = parseFrame(buffer);
      if (event) yield event;
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      // the stream may already be closed
    }
    reader.releaseLock();
  }
}

// ---------------------------------------------------------------------------------------------------------------
// HTTP client
// ---------------------------------------------------------------------------------------------------------------

export class HttpApiClient implements ApiClient {
  private readonly baseUrl: string;
  private readonly promptCache = new Map<string, Promise<string | null>>();

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  private resolveArtifact = (ref: string | null | undefined) => artifactUrl(ref, this.baseUrl);

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
    let response: Response;
    try {
      response = init !== undefined ? await fetch(url, init) : await fetch(url);
    } catch (err) {
      if (isAbortError(err)) throw err;
      throw new Error(`Network request failed for ${url}: ${errorMessage(err, String(err))}`);
    }

    if (!response.ok) {
      let apiError: Partial<ApiError> | undefined;
      let detail = "";
      try {
        const text = await response.text();
        if (text) {
          try {
            const json = JSON.parse(text);
            if (json?.error?.message) {
              apiError = json.error;
              detail = `: ${json.error.message}`;
            } else {
              detail = `: ${text}`;
            }
          } catch {
            detail = `: ${text}`;
          }
        }
      } catch {
        // ignore unreadable bodies
      }
      throw new ApiRequestError(
        `Request to ${path} failed with status ${response.status}${detail}`,
        response.status,
        apiError,
      );
    }

    return (await response.json()) as T;
  }

  private json(method: string, body?: unknown): RequestInit {
    return body === undefined
      ? { method }
      : { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  }

  health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health");
  }

  createTask(prompt: string, targetUrl: string): Promise<Task> {
    return this.request<Task>("/tasks", this.json("POST", { prompt, target_url: targetUrl }));
  }

  getTask(taskId: string): Promise<Task> {
    return this.request<Task>(`/tasks/${encodeURIComponent(taskId)}`);
  }

  clarifyTask(taskId: string, answer: string): Promise<Task> {
    return this.request<Task>(`/tasks/${encodeURIComponent(taskId)}/clarify`, this.json("POST", { answer }));
  }

  getPlan(planId: string): Promise<Plan> {
    return this.request<Plan>(`/plans/${encodeURIComponent(planId)}`);
  }

  updatePlan(planId: string, revision: number, steps: PlannedStep[]): Promise<Plan> {
    return this.request<Plan>(`/plans/${encodeURIComponent(planId)}`, this.json("PATCH", { revision, steps }));
  }

  approvePlan(planId: string, revision: number): Promise<Run> {
    return this.request<Run>(`/plans/${encodeURIComponent(planId)}/approve`, this.json("POST", { revision }));
  }

  rejectPlan(planId: string, reason?: string): Promise<Plan> {
    return this.request<Plan>(
      `/plans/${encodeURIComponent(planId)}/reject`,
      this.json("POST", reason ? { reason } : {}),
    );
  }

  getRun(runId: string): Promise<Run> {
    return this.request<Run>(`/runs/${encodeURIComponent(runId)}`);
  }

  cancelRun(runId: string): Promise<Run> {
    return this.request<Run>(`/runs/${encodeURIComponent(runId)}/cancel`, { method: "POST" });
  }

  confirmRun(runId: string, stepSeq: number, decision: ConfirmDecision): Promise<Run> {
    if (!Number.isInteger(stepSeq) || stepSeq < 1) {
      return Promise.reject(new Error("confirmRun needs the step_seq the run is paused at"));
    }
    return this.request<Run>(
      `/runs/${encodeURIComponent(runId)}/confirm`,
      this.json("POST", { step_seq: stepSeq, decision }),
    );
  }

  getWorkflow(id: string): Promise<Workflow> {
    return this.request<Workflow>(`/workflows/${encodeURIComponent(id)}`);
  }

  getWorkflows(limit = 50): Promise<WorkflowPage> {
    return this.request<WorkflowPage>(`/workflows?limit=${limit}`);
  }

  /** Run → plan → task.prompt, cached per plan (the run list shows the real prompt). */
  private promptForPlan(planId: string): Promise<string | null> {
    let cached = this.promptCache.get(planId);
    if (!cached) {
      cached = this.getPlan(planId)
        .then((plan) => this.getTask(plan.task_id))
        .then((task) => task.prompt)
        .catch(() => null);
      this.promptCache.set(planId, cached);
    }
    return cached;
  }

  async getRuns({ limit = 10, cursor }: GetRunsOptions = {}): Promise<RunsPage> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (cursor) params.set("cursor", cursor);
    const page = await this.request<RunPage>(`/runs?${params.toString()}`);
    const items = await Promise.all(
      (page.items ?? []).map(async (run) => runToListItem(run, await this.promptForPlan(run.plan_id))),
    );
    return { items, nextCursor: page.next_cursor ?? null };
  }

  async getRunDetails(runId: string): Promise<RunDetails> {
    const run = await this.getRun(runId);
    const [plan, workflow] = await Promise.all([
      this.getPlan(run.plan_id).catch(() => null),
      run.workflow_id
        ? this.getWorkflow(run.workflow_id).catch((err: unknown) => {
            if (isApiError(err, undefined, 404)) return null;
            throw err;
          })
        : Promise.resolve(null),
    ]);
    const task = plan ? await this.getTask(plan.task_id).catch(() => null) : null;
    return buildRunDetails(run, plan, task, workflow, this.resolveArtifact);
  }

  /**
   * Streams the run's events. On an unexpected drop (the connection ends before a final event, or fails) it
   * reconnects with `Last-Event-ID: <last seq>` so nothing is lost or repeated. It never reconnects after a
   * final event. Events with a seq at or below the last one seen are skipped.
   */
  async *streamRunEvents(runId: string, options: StreamOptions = {}): AsyncIterable<RunEvent> {
    const { signal, onReconnect } = options;
    const maxReconnects = options.maxReconnects ?? 5;
    const baseDelay = options.reconnectDelayMs ?? 1000;
    const url = `${this.baseUrl}/runs/${encodeURIComponent(runId)}/events`;
    let lastSeq = options.lastEventId ?? 0;
    let failures = 0;

    while (!signal?.aborted) {
      let lastError: unknown = null;
      try {
        const headers: Record<string, string> = { Accept: "text/event-stream" };
        if (lastSeq > 0) headers["Last-Event-ID"] = String(lastSeq);
        const response = await fetch(url, { headers, signal, cache: "no-store" });
        if (!response.ok) {
          let detail = "";
          let apiError: Partial<ApiError> | undefined;
          try {
            const text = await response.text();
            try {
              apiError = JSON.parse(text)?.error;
            } catch {
              // not JSON
            }
            detail = apiError?.message ? `: ${apiError.message}` : text ? `: ${text}` : "";
          } catch {
            // ignore
          }
          const err = new ApiRequestError(
            `Live event stream failed with status ${response.status}${detail}`,
            response.status,
            apiError,
          );
          // 4xx (unknown run, bad request) will not fix itself: don't retry.
          if (response.status < 500) throw err;
          lastError = err;
        } else if (!response.body) {
          lastError = new Error("No response body received for the live event stream");
        } else {
          for await (const event of parseEventStream(response.body, signal)) {
            if (typeof event.seq === "number" && event.seq <= lastSeq) continue;
            if (typeof event.seq === "number") lastSeq = event.seq;
            failures = 0;
            yield event;
            if (isFinalEvent(event)) return;
          }
        }
      } catch (err) {
        if (isAbortError(err) || signal?.aborted) return;
        if (err instanceof ApiRequestError && err.status < 500) throw err;
        lastError = err;
      }

      if (signal?.aborted) return;
      failures += 1;
      if (failures > maxReconnects) {
        throw new Error(
          `Lost the live event stream for run ${runId} after ${maxReconnects} reconnect attempts` +
            (lastError ? `: ${errorMessage(lastError)}` : ""),
        );
      }
      onReconnect?.(failures);
      try {
        await sleep(Math.min(10_000, baseDelay * 2 ** (failures - 1)), signal);
      } catch {
        return; // aborted while waiting
      }
    }
  }
}

// ---------------------------------------------------------------------------------------------------------------
// Mock client
// ---------------------------------------------------------------------------------------------------------------

/**
 * Replays an array of RunEvents with delays based on their timestamps (`ts`).
 * Supports speed scaling and mid-stream cancellation through AbortSignal.
 */
export async function* replayEvents(
  events: RunEvent[],
  options: StreamOptions = {},
): AsyncGenerator<RunEvent, void, unknown> {
  const { signal } = options;
  const rawSpeed = options.speed ?? Number(process.env.NEXT_PUBLIC_MOCK_SPEED);
  const speed = Number.isFinite(rawSpeed) && rawSpeed > 0 ? rawSpeed : 1;

  if (signal?.aborted) throw new DOMException("aborted", "AbortError");

  let prevTime: number | undefined;
  for (const event of events) {
    const eventTime = Date.parse(event.ts);
    if (prevTime !== undefined && !Number.isNaN(eventTime) && !Number.isNaN(prevTime)) {
      const delayMs = Math.max(0, (eventTime - prevTime) / speed);
      if (delayMs > 0) await sleep(delayMs, signal);
    }
    prevTime = eventTime;
    if (signal?.aborted) throw new DOMException("aborted", "AbortError");
    yield event;
  }
}

type MockScenario = "success" | "paused" | "failed" | "replan" | "replan-review" | "blocked";

const SCENARIO_EVENTS: Record<MockScenario, RunEvent[]> = {
  success: giteaEventsFixture,
  paused: giteaPausedEventsFixture,
  failed: giteaFailedEventsFixture,
  replan: giteaReplanEventsFixture,
  "replan-review": giteaReplanReviewEventsFixture,
  blocked: giteaBlockedEventsFixture,
};

/** The mock run ids the UI and e2e tests use. Each id picks one scripted scenario. */
const SCENARIO_BY_RUN_ID: Record<string, MockScenario> = {
  default: "success",
  mock: "success",
  gitea: "success",
  "mock-run-id": "success",
  [giteaWorkflowFixture.run_id ?? "gitea-run"]: "success",
  [giteaWorkflowFixture.id]: "success",
  paused: "paused",
  failed: "failed",
  replan: "replan",
  "replan-review": "replan-review",
  blocked: "blocked",
  restricted: "blocked",
};

/** Mock fixtures store screenshots under contracts/fixtures/screenshots/; the app serves copies from public/. */
function mockAsset(ref: string | null | undefined): string | undefined {
  if (!ref) return undefined;
  const m = /(?:^|\/)screenshots\/([^/]+)$/.exec(ref);
  return m ? `/screenshots/${m[1]}` : ref;
}

interface MockRunState {
  status: Run["status"];
  pausedAt: number | null;
  pauseReason: string | null;
  /** An answer that arrived after run.paused was emitted but before the stream started waiting. */
  pendingAnswer: ConfirmDecision | "cancel" | null;
  currentSeq: number | null;
  /** Resolved by confirmRun / cancelRun while the stream waits on a pause. */
  waiter: ((answer: ConfirmDecision | "cancel") => void) | null;
  /** Set by cancelRun while events are still being replayed. */
  cancelRequested: boolean;
  interrupt: AbortController;
  /** The plan the run continues with after a replan_review allow. */
  pendingPlanId: string | null;
}

function nowTs(): string {
  return new Date().toISOString();
}

function mockError(status: number, code: ApiError["code"], message: string): ApiRequestError {
  return new ApiRequestError(`Request failed with status ${status}: ${message}`, status, { code, message });
}

export class MockApiClient implements ApiClient {
  private readonly plans: Record<string, Plan> = {};
  private readonly tasks = new Map<string, Pick<Task, "prompt" | "target_url">>();
  private readonly runs = new Map<string, MockRunState>();
  private readonly runsList: RunListItem[];
  private readonly runDetailsMap: Record<string, RunDetails>;

  constructor(
    private readonly events: RunEvent[] = giteaEventsFixture,
    private readonly workflows: Record<string, Workflow> = workflowFixtures,
    runsList: RunListItem[] = mockRunsList,
    runDetailsMap: Record<string, RunDetails> = mockRunDetails,
  ) {
    this.runsList = runsList;
    this.runDetailsMap = runDetailsMap;
    this.plans[replanProposedPlanFixture.id] = replanProposedPlanFixture;
  }

  async health(): Promise<HealthResponse> {
    return { status: "ok", version: "mock" };
  }

  async createTask(prompt: string, targetUrl: string): Promise<Task> {
    this.tasks.set("mock-task-id", { prompt, target_url: targetUrl });
    return {
      id: "mock-task-id",
      prompt,
      target_url: targetUrl,
      status: "planning",
      plan_id: null,
      created_at: nowTs(),
    };
  }

  async getTask(taskId: string): Promise<Task> {
    const created = this.tasks.get(taskId);
    return {
      id: taskId,
      prompt: created?.prompt ?? "Create a repository in local Gitea",
      target_url: created?.target_url ?? "http://localhost:3001",
      status: "planned",
      interpretation: { app: "gitea", goal: "create_repository" },
      plan_id: "default",
      created_at: nowTs(),
    };
  }

  async clarifyTask(taskId: string, answer: string): Promise<Task> {
    void answer;
    return { ...(await this.getTask(taskId)), status: "planning", plan_id: null };
  }

  async getPlan(planId: string): Promise<Plan> {
    if (this.plans[planId]) return this.plans[planId];
    const workflow = this.workflows[planId];
    if (!workflow) throw mockError(404, "not_found", `Plan not found: ${planId}`);
    const steps = workflow.steps.map(toPlannedStep) as [PlannedStep, ...PlannedStep[]];
    const plan: Plan = {
      id: planId,
      task_id: "mock-task-id",
      revision: 1,
      status: "proposed",
      risk: steps.some((s) => s.risk === "high") ? "high" : steps.some((s) => s.risk === "medium") ? "medium" : "low",
      expected_result: "A new repository page is shown",
      steps,
      created_at: nowTs(),
    };
    this.plans[planId] = plan;
    return plan;
  }

  async updatePlan(planId: string, revision: number, steps: PlannedStep[]): Promise<Plan> {
    const current = await this.getPlan(planId);
    if (current.status !== "proposed") {
      throw mockError(409, "plan_not_editable", `Plan is already ${current.status}`);
    }
    if (revision !== current.revision) {
      throw mockError(409, "conflict", `Plan revision ${revision} is stale; the current one is ${current.revision}`);
    }
    if (steps.length === 0) throw mockError(422, "validation_error", "Plan must contain at least 1 step");
    const updated: Plan = {
      ...current,
      revision: current.revision + 1,
      steps: steps.map((s, idx) => ({ ...s, seq: idx + 1 })) as [PlannedStep, ...PlannedStep[]],
    };
    this.plans[planId] = updated;
    return updated;
  }

  async approvePlan(planId: string, revision: number): Promise<Run> {
    const current = await this.getPlan(planId);
    if (current.status !== "proposed") {
      throw mockError(409, "plan_not_editable", `Plan is already ${current.status}`);
    }
    if (revision !== current.revision) {
      throw mockError(409, "conflict", `Plan revision ${revision} is stale; the current one is ${current.revision}`);
    }
    this.plans[planId] = { ...current, status: "approved", approved_at: nowTs() };
    return this.runFor("mock-run-id", planId, revision);
  }

  async rejectPlan(planId: string, reason?: string): Promise<Plan> {
    void reason;
    const current = await this.getPlan(planId);
    if (current.status !== "proposed") {
      throw mockError(409, "plan_not_editable", `Plan is already ${current.status}`);
    }
    const rejected: Plan = { ...current, status: "rejected" };
    this.plans[planId] = rejected;
    return rejected;
  }

  private scenario(runId: string): MockScenario {
    const scenario = SCENARIO_BY_RUN_ID[runId];
    if (!scenario) throw mockError(404, "not_found", `Run not found: ${runId}`);
    return scenario;
  }

  private planIdFor(runId: string): string {
    const scenario = this.scenario(runId);
    return scenario === "success" ? "default" : runId === "restricted" ? "restricted" : scenario;
  }

  private state(runId: string): MockRunState {
    let state = this.runs.get(runId);
    if (!state) {
      state = {
        status: "queued",
        pausedAt: null,
        pauseReason: null,
        pendingAnswer: null,
        currentSeq: null,
        waiter: null,
        cancelRequested: false,
        interrupt: new AbortController(),
        pendingPlanId: null,
      };
      this.runs.set(runId, state);
    }
    return state;
  }

  private runFor(runId: string, planId: string, revision = 1): Run {
    const state = this.runs.get(runId);
    return {
      id: runId,
      plan_id: planId,
      plan_revision: revision,
      status: state?.status ?? "queued",
      current_seq: state?.currentSeq ?? null,
      retry_count: 0,
      workflow_id: state?.status === "verified" ? giteaWorkflowFixture.id : null,
      created_at: "2026-10-06T12:00:00.000Z",
      started_at: state && state.status !== "queued" ? "2026-10-06T12:00:00.000Z" : null,
      finished_at: null,
    };
  }

  async getRun(runId: string): Promise<Run> {
    return this.runFor(runId, this.planIdFor(runId));
  }

  async cancelRun(runId: string): Promise<Run> {
    this.scenario(runId);
    const state = this.state(runId);
    if (state.status === "verified" || state.status === "failed" || state.status === "cancelled") {
      throw mockError(409, "run_not_active", `Run already ${state.status}`);
    }
    if (state.waiter) {
      state.waiter("cancel");
    } else if (state.status === "paused") {
      state.pendingAnswer = "cancel";
    } else {
      state.cancelRequested = true;
      state.interrupt.abort();
    }
    state.status = "cancelled";
    return this.runFor(runId, this.planIdFor(runId));
  }

  async confirmRun(runId: string, stepSeq: number, decision: ConfirmDecision): Promise<Run> {
    this.scenario(runId);
    const state = this.state(runId);
    if (state.status !== "paused" || state.pausedAt !== stepSeq || state.pendingAnswer) {
      throw mockError(409, "run_not_active", `Run is ${state.status}, not paused at step ${stepSeq}`);
    }
    if (state.waiter) state.waiter(decision);
    else state.pendingAnswer = decision;
    state.status = decision === "allow" ? "running" : "cancelled";
    return this.runFor(runId, this.planIdFor(runId));
  }

  async getWorkflow(id: string): Promise<Workflow> {
    const fixture = this.workflows[id];
    if (!fixture) throw mockError(404, "not_found", `Workflow not found: ${id}`);
    return fixture;
  }

  async getWorkflows(limit = 50): Promise<WorkflowPage> {
    const items = Object.values(this.workflows)
      .filter((w) => w.status === "verified")
      .slice(0, limit)
      .map((w) => ({
        id: w.id,
        title: w.title,
        status: w.status,
        target_app: w.target_app ?? null,
        step_count: w.steps.length,
        confidence: w.confidence ?? null,
        created_at: w.created_at ?? null,
      }));
    return { items, next_cursor: null };
  }

  async *streamRunEvents(runId: string, options: StreamOptions = {}): AsyncIterable<RunEvent> {
    const scenario = this.scenario(runId);
    const state = this.state(runId);
    const { signal } = options;
    const script = scenario === "success" ? this.events : SCENARIO_EVENTS[scenario];
    const after = options.lastEventId ?? 0;
    let lastSeq = after;
    const realRunId = script[0]?.run_id ?? runId;
    state.interrupt = new AbortController();

    const track = (event: RunEvent) => {
      lastSeq = event.seq;
      if (event.type === "run.started") state.status = "running";
      if (event.type === "step.started") state.currentSeq = event.step_seq;
      if (event.type === "run.paused") {
        state.status = "paused";
        state.pausedAt = event.step_seq;
        state.pauseReason = event.reason;
        state.pendingPlanId = event.plan_id ?? null;
      }
      if (event.type === "run.resumed") {
        state.status = "running";
        state.pausedAt = null;
      }
      if (event.type === "run.completed") state.status = "verified";
      if (event.type === "run.failed") state.status = "failed";
      if (event.type === "run.cancelled") state.status = "cancelled";
    };
    const next = <T extends RunEvent["type"]>(
      type: T,
      extra: Omit<Extract<RunEvent, { type: T }>, "type" | "run_id" | "seq" | "ts">,
    ): RunEvent => ({ type, run_id: realRunId, seq: lastSeq + 1, ts: nowTs(), ...extra }) as unknown as RunEvent;
    const cancelledEvent = (reason: "user" | "confirmation_denied") =>
      next("run.cancelled", { reason, step_seq: state.currentSeq });

    const combined = new AbortController();
    const abortCombined = () => combined.abort();
    signal?.addEventListener("abort", abortCombined, { once: true });
    state.interrupt.signal.addEventListener("abort", abortCombined, { once: true });

    try {
      try {
        for await (const event of replayEvents(
          script.filter((e) => e.seq > after),
          { speed: options.speed, signal: combined.signal },
        )) {
          track(event);
          yield event;
          if (isFinalEvent(event)) return;
        }
      } catch (err) {
        if (!isAbortError(err)) throw err;
        if (signal?.aborted) return;
        // cancelRun interrupted the replay
      }
      if (signal?.aborted) return;

      if (state.cancelRequested) {
        const ev = cancelledEvent("user");
        track(ev);
        yield ev;
        return;
      }

      // The script ended on a pause: wait for /confirm or /cancel, like the real backend.
      while (state.pausedAt !== null) {
        const pausedAt = state.pausedAt;
        const pending = state.pendingAnswer;
        state.pendingAnswer = null;
        const answer = pending ?? await new Promise<ConfirmDecision | "cancel" | "aborted">((resolve) => {
          state.waiter = resolve;
          signal?.addEventListener("abort", () => resolve("aborted"), { once: true });
        });
        state.waiter = null;
        if (answer === "aborted") return;
        if (answer !== "allow") {
          const ev = cancelledEvent(answer === "deny" ? "confirmation_denied" : "user");
          track(ev);
          yield ev;
          return;
        }
        const resumed = next("run.resumed", { step_seq: pausedAt, decision: "allow" });
        track(resumed);
        yield resumed;

        const planId = state.pendingPlanId ?? this.planIdFor(runId);
        const plan = await this.getPlan(planId).catch(() => null);
        const remaining = (plan?.steps ?? []).filter((s) => s.seq >= pausedAt);
        for (const step of remaining) {
          await sleep(Math.max(20, 300 / (options.speed ?? 1)), signal).catch(() => undefined);
          if (signal?.aborted) return;
          if (state.cancelRequested) {
            const ev = cancelledEvent("user");
            track(ev);
            yield ev;
            return;
          }
          // Mirrors the backend: a pause before the action (policy) continues with that action; a retry or a
          // replanned step starts over; an accepted unclear step is done.
          const reason = state.pauseReason;
          if (step.seq === pausedAt && reason === "verification_unclear") continue;
          const preAction = reason !== "recovery_exhausted" && reason !== "replan_review";
          if (step.seq !== pausedAt || !preAction) {
            const started = next("step.started", { step_seq: step.seq, instruction_text: step.instruction_text });
            track(started);
            yield started;
          }
          const done = next("step.action_done", {
            step_seq: step.seq,
            screenshot_url: `/screenshots/step-${Math.min(step.seq, 5)}.png`,
            bbox: null,
          });
          track(done);
          yield done;
          const verified = next("step.verified", { step_seq: step.seq, method: ["dom"], confidence: 1 });
          track(verified);
          yield verified;
        }
        const total = plan?.steps.length ?? remaining.length;
        const completed = next("run.completed", {
          workflow_id: giteaWorkflowFixture.id,
          verified_steps: total,
          failed_actions: 0,
        });
        track(completed);
        yield completed;
        return;
      }
    } finally {
      signal?.removeEventListener("abort", abortCombined);
    }
  }

  async getRuns({ limit = 10, cursor }: GetRunsOptions = {}): Promise<RunsPage> {
    // The mock cursor is an offset; the real one is an opaque keyset cursor. The UI treats both as opaque.
    const offset = cursor?.startsWith("offset:") ? Number(cursor.slice("offset:".length)) || 0 : 0;
    const items = this.runsList.slice(offset, offset + limit);
    const end = offset + items.length;
    return { items, nextCursor: end < this.runsList.length ? `offset:${end}` : null };
  }

  async getRunDetails(runId: string): Promise<RunDetails> {
    const details =
      this.runDetailsMap[runId] ??
      (runId === "default" || runId === "mock" || runId === "" ? this.runDetailsMap["default"] : undefined);
    if (details) {
      return { ...details, run: { ...details.run, id: runId } };
    }
    const scenario = SCENARIO_BY_RUN_ID[runId];
    if (scenario) {
      const run = await this.getRun(runId);
      const plan = await this.getPlan(run.plan_id).catch(() => null);
      const task = await this.getTask("mock-task-id");
      const workflow = scenario === "success" ? giteaWorkflowFixture : null;
      return buildRunDetails(run, plan, task, workflow, mockAsset);
    }
    throw mockError(404, "not_found", `Run details not found: ${runId}`);
  }
}

/**
 * Returns an ApiClient based on NEXT_PUBLIC_API_MODE: `http` → HttpApiClient (NEXT_PUBLIC_API_URL), else mock.
 */
export function getApiClient(): ApiClient {
  return process.env.NEXT_PUBLIC_API_MODE === "http" ? new HttpApiClient(apiBaseUrl()) : new MockApiClient();
}

export function createApiClient(
  mode: string | undefined = process.env.NEXT_PUBLIC_API_MODE,
  baseUrl: string = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
): ApiClient {
  return mode === "http" ? new HttpApiClient(normalizeBaseUrl(baseUrl)) : new MockApiClient();
}
