// Thin API client seam (docs/architecture.md §4). `mock` mode serves contract-valid fixtures, so the UI never
// waits on the backend; `http` mode talks to the real backend (docs/api-contract.md, contracts/openapi.json).
import type {
  ApiError,
  Export,
  ExportErrorCode,
  ExportPreset,
  ExportStatus,
  HealthResponse,
  LoginRequest,
  MetricsSummary,
  Plan,
  PlannedStep,
  ReviewActionResult,
  ReviewCount,
  ReviewItem,
  ReviewItemList,
  Run,
  RunEvent,
  RunPage,
  ShareLink,
  ShareLinkCreated,
  ShareLinkList,
  Task,
  TaskMetrics,
  User,
  Workflow,
  WorkflowPage,
  WorkflowStatus,
  WorkflowInput,
  WorkflowInputList,
  WorkflowVersionList,
  HandBackDone,
  Language,
  Translation,
  TakeoverInput,
} from "@krama/contracts-ts";
import { compileWorkflow, type TutorialSpec } from "@krama/tutorial-compiler";

import { apiBaseUrl, artifactUrl, normalizeBaseUrl } from "./artifacts";
import { parseStepDiffs } from "@/components/versions/version-utils";
import { workflowFreshness } from "./freshness";
import {
  blockedWorkflowFixture,
  demoUserFixture,
  failedWorkflowFixture,
  giteaBlockedEventsFixture,
  giteaEventsFixture,
  giteaFailedEventsFixture,
  giteaPausedEventsFixture,
  giteaReplanEventsFixture,
  giteaReplanReviewEventsFixture,
  giteaTutorialSpecFixture,
  giteaVersionsFixture,
  giteaWorkflowFixture,
  giteaWorkflowInputsFixture,
  mockAllFreshnessTutorialSummaries,
  mockMetricsSummary,
  mockReviewQueueItems,
  mockRunDetails,
  mockRunsList,
  mockTutorialSummaries,
  mockWorkflowVersions,
  pausedWorkflowFixture,
  replanProposedPlanFixture,
  replanWorkflowFixture,
  restrictedWorkflowFixture,
  toPlannedStep,
  tutorialSpecFixtures,
  validWorkflowFixture,
  workflowFixtures,
} from "./fixtures";
import type {
  RunDetails,
  RunListItem,
  RunsPage,
  SessionStatus,
  ManualLoginResponse,
  StepEvidenceDetail,
  StepVerificationEvidence,
  TargetPlatform,
  TutorialStatus,
  TutorialSummary,
  VerificationEvidenceMethod,
} from "./types";
import type {
  ReviewActionResponse,
  ReviewQueueCountResponse,
  ReviewQueueItem,
} from "@/types/review";

export type {
  Export,
  ExportErrorCode,
  ExportPreset,
  ExportStatus,
  HealthResponse,
  LoginRequest,
  MetricsSummary,
  Plan,
  ReviewActionResponse,
  ReviewQueueCountResponse,
  ReviewQueueItem,
  Run,
  RunDetails,
  RunEvent,
  RunListItem,
  RunsPage,
  SessionStatus,
  ManualLoginResponse,
  StepEvidenceDetail,
  StepVerificationEvidence,
  TargetPlatform,
  Task,
  TaskMetrics,
  TutorialStatus,
  TutorialSummary,
  User,
  VerificationEvidenceMethod,
  Workflow,
};
export {
  artifactUrl,
  blockedWorkflowFixture,
  demoUserFixture,
  failedWorkflowFixture,
  giteaBlockedEventsFixture,
  giteaEventsFixture,
  giteaFailedEventsFixture,
  giteaPausedEventsFixture,
  giteaReplanEventsFixture,
  giteaReplanReviewEventsFixture,
  giteaWorkflowFixture,
  mockMetricsSummary,
  mockReviewQueueItems,
  mockRunDetails,
  mockRunsList,
  mockTutorialSummaries,
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
  /** The server's own `error.message`, without the request path (for showing next to a form field). */
  readonly apiMessage?: string;

  constructor(message: string, status: number, error?: Partial<ApiError>) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = error?.code;
    this.details = error?.details as Record<string, unknown> | undefined;
    this.apiMessage = error?.message;
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
/** Text message from WS /runs/{id}/screen (contracts/schemas/takeover.schema.json `TakeoverServerMessage`; the
 * TypeScript generator only emits types the root schema reaches, so it is written out here). */
export interface TakeoverServerMessage {
  type: "ready" | "blocked" | "ended";
  width?: number;
  height?: number;
  message?: string;
  reason?: "handed_back" | "idle" | "closed" | "cancelled";
}

/** The live page during a takeover (ADR 0008): frames as image URLs, server notices, and input back. */
export interface ScreenConnection {
  onFrame(listener: (url: string) => void): void;
  onMessage(listener: (message: TakeoverServerMessage) => void): void;
  onClose(listener: (code: number) => void): void;
  send(input: TakeoverInput): void;
  close(): void;
}

/** A WebSocket to WS /runs/{id}/screen. Frames arrive as JPEG blobs; each becomes an object URL (the last one
 * is revoked when the next arrives, so memory stays flat). Frames are never stored. */
export class WebSocketScreen implements ScreenConnection {
  private readonly socket: WebSocket;
  private lastUrl: string | null = null;

  constructor(url: string) {
    this.socket = new WebSocket(url);
    this.socket.binaryType = "blob";
  }

  onFrame(listener: (url: string) => void): void {
    this.socket.addEventListener("message", (event: MessageEvent) => {
      if (typeof event.data === "string") return;
      const next = URL.createObjectURL(event.data as Blob);
      if (this.lastUrl) URL.revokeObjectURL(this.lastUrl);
      this.lastUrl = next;
      listener(next);
    });
  }

  onMessage(listener: (message: TakeoverServerMessage) => void): void {
    this.socket.addEventListener("message", (event: MessageEvent) => {
      if (typeof event.data !== "string") return;
      try {
        listener(JSON.parse(event.data) as TakeoverServerMessage);
      } catch {
        // not a contract message: ignore
      }
    });
  }

  onClose(listener: (code: number) => void): void {
    this.socket.addEventListener("close", (event: CloseEvent) => listener(event.code));
  }

  send(input: TakeoverInput): void {
    if (this.socket.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify(input));
  }

  close(): void {
    if (this.lastUrl) URL.revokeObjectURL(this.lastUrl);
    this.lastUrl = null;
    this.socket.close();
  }
}

/** Mock mode: one fixture screenshot as the page, input is recorded (tests and the e2e mock flow). */
export class MockScreen implements ScreenConnection {
  readonly sent: TakeoverInput[] = [];
  private frameListeners: ((url: string) => void)[] = [];
  private messageListeners: ((message: TakeoverServerMessage) => void)[] = [];
  private closeListeners: ((code: number) => void)[] = [];

  constructor(private readonly frameUrl = "/screenshots/step-3.png") {
    setTimeout(() => {
      this.messageListeners.forEach((l) => l({ type: "ready", width: 1280, height: 800 }));
      this.frameListeners.forEach((l) => l(this.frameUrl));
    }, 0);
  }

  onFrame(listener: (url: string) => void): void {
    this.frameListeners.push(listener);
  }

  onMessage(listener: (message: TakeoverServerMessage) => void): void {
    this.messageListeners.push(listener);
  }

  onClose(listener: (code: number) => void): void {
    this.closeListeners.push(listener);
  }

  send(input: TakeoverInput): void {
    this.sent.push(input);
  }

  close(): void {
    this.closeListeners.forEach((l) => l(1000));
  }
}

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
  getWorkflows(limit?: number, status?: WorkflowStatus | "all"): Promise<WorkflowPage>;
  /** GET /workflows/{id}/versions: every version of the workflow, newest first, with step diffs against its parent. */
  getWorkflowVersions(workflowId: string): Promise<WorkflowVersionList>;
  /** POST /workflows/{workflowId}/shares with X-Krama: 1. Creates a public read-only share link. */
  createShareLink(workflowId: string): Promise<ShareLinkCreated>;
  /** GET /workflows/{workflowId}/shares: list share links for this workflow. */
  listShareLinks(workflowId: string): Promise<ShareLinkList>;
  /** DELETE /workflows/{workflowId}/shares/{shareId} with X-Krama: 1. Revokes the share link. */
  revokeShareLink(workflowId: string, shareId: string): Promise<ShareLink>;
  /** GET /tutorials (or stored workflows mapped to tutorial summaries). */
  getTutorials(options?: { limit?: number; status?: "all" | TutorialStatus }): Promise<TutorialSummary[]>;
  /** GET /workflows?q= (#135): the user's tutorials matching `query`, best first, with a snippet each. */
  searchTutorials(query: string, options?: { status?: "all" | TutorialStatus; limit?: number }): Promise<TutorialSummary[]>;
  /** Run + plan + task + workflow, shaped for the run detail / evidence page. */
  getRunDetails(runId: string): Promise<RunDetails>;
  /** POST /api/v1/sessions/manual-login?target={target} */
  launchManualLogin(target: string): Promise<ManualLoginResponse>;
  /** POST /api/v1/sessions/status?target={target} */
  getSessionStatus(target: string): Promise<SessionStatus>;
  /** POST /auth/login (or /api/v1/auth/login) with X-Krama: 1. */
  login(request: LoginRequest): Promise<User>;
  /** POST /auth/logout (or /api/v1/auth/logout) with X-Krama: 1. */
  logout(): Promise<void>;
  /** GET /auth/me (or /api/v1/auth/me) with X-Krama: 1. Throws 401 when unauthenticated. */
  getMe(): Promise<User>;
  /** GET /api/v1/shares/{token} (or /shared/{token}). Public, read-only. Throws 404 when not found or revoked. */
  getSharedTutorial(token: string): Promise<TutorialSpec>;
  /** GET /metrics/summary (or /api/v1/metrics/summary): technical benchmark metrics summary. */
  getMetricsSummary(): Promise<MetricsSummary>;
  /** GET /api/v1/reviews: owner review queue items. */
  getReviewQueue(): Promise<ReviewQueueItem[]>;
  /** GET /api/v1/reviews/count: count of pending review items. */
  getReviewQueueCount(): Promise<ReviewQueueCountResponse>;
  /** POST /api/v1/reviews/{id}/accept with X-Krama: 1. */
  acceptReview(id: string): Promise<ReviewActionResponse>;
  /** POST /api/v1/reviews/{id}/reject with X-Krama: 1. */
  rejectReview(id: string): Promise<ReviewActionResponse>;
  /** POST /api/v1/workflows/{workflowId}/regenerate with X-Krama: 1. */
  regenerateWorkflow(workflowId: string): Promise<{ id: string; run_id?: string; status: string }>;
  /** POST /api/v1/workflows/{workflowId}/retry-ai-fix with X-Krama: 1. */
  retryAiFix(workflowId: string): Promise<{ success: boolean; status?: string }>;
  /** POST /api/v1/workflows/{workflowId}/reverify with X-Krama: 1: check the workflow again now. */
  reverifyWorkflow(workflowId: string): Promise<Run>;
  /**
   * GET /workflows/{id}/inputs: the values the owner chooses before "Do it for me" runs the workflow (#129).
   * 409 `conflict` with `details.reason` `not_verified`, `pending_review` or `secret_not_stored`.
   */
  getWorkflowInputs(workflowId: string): Promise<WorkflowInputList>;
  /**
   * POST /workflows/{id}/run → 202 Run (`kind: "do_it"`). 409 as above plus `stale_revision`; 422
   * `validation_error` with `details.reason = "input_unsafe"` and `details.key` for a bad value.
   */
  runWorkflow(workflowId: string, revision: number, inputs: Record<string, string>): Promise<Run>;
  /** POST /sites/{site}/sign-in → 202 Run (kind sign_in): sign in by hand in a takeover (ADR 0007). */
  startSignIn(site: string): Promise<Run>;
  /** POST /runs/{id}/takeover: take control of the paused run's live page (ADR 0008). 409 when none is possible. */
  startTakeover(runId: string): Promise<Run>;
  /** POST /runs/{id}/handback: end the takeover and say what was done (barrier | step | rest). */
  handBack(runId: string, stepSeq: number, done: HandBackDone): Promise<Run>;
  /** WS /runs/{id}/screen: the live page's frames, and the owner's input back. */
  openScreen(runId: string): ScreenConnection;
  /** POST /workflows/{workflowId}/exports with preset ("landscape" | "portrait"). */
  createExport(workflowId: string, preset: ExportPreset, language?: Language): Promise<Export>;
  /** GET /workflows/{id}/translations/{language} (#422): 202 while it is being made; poll until ready. */
  getTranslation(workflowId: string, language: Language): Promise<Translation>;
  /** GET /exports/{exportId}. */
  getExport(exportId: string): Promise<Export>;
  /** URL for downloading exported MP4. */
  getExportDownloadUrl(exportId: string): string;
  /** URL for downloading exported WebVTT captions. */
  getExportCaptionsUrl(exportId: string): string;
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
      // credentials: the session is an HTTP-only cookie set by the API on another port (#94). X-Krama: the API's
      // CSRF check refuses every POST/PUT/DELETE without it (#104: creating a task failed with 403).
      const headers = new Headers(init?.headers);
      headers.set("X-Krama", "1");
      response = await fetch(url, { credentials: "include", ...init, headers });
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

  getWorkflows(limit = 50, status?: WorkflowStatus | "all"): Promise<WorkflowPage> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (status && status !== "all") params.set("status", status);
    return this.request<WorkflowPage>(`/workflows?${params.toString()}`);
  }

  getWorkflowVersions(workflowId: string): Promise<WorkflowVersionList> {
    return this.request<WorkflowVersionList>(`/workflows/${encodeURIComponent(workflowId)}/versions`);
  }

  async createShareLink(workflowId: string): Promise<ShareLinkCreated> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/workflows/${encodeURIComponent(workflowId)}/shares`
      : `/api/v1/workflows/${encodeURIComponent(workflowId)}/shares`;
    return this.request<ShareLinkCreated>(path, {
      method: "POST",
      credentials: "include",
      headers: {
        "X-Krama": "1",
      },
    });
  }

  async listShareLinks(workflowId: string): Promise<ShareLinkList> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/workflows/${encodeURIComponent(workflowId)}/shares`
      : `/api/v1/workflows/${encodeURIComponent(workflowId)}/shares`;
    return this.request<ShareLinkList>(path, {
      credentials: "include",
    });
  }

  async revokeShareLink(workflowId: string, shareId: string): Promise<ShareLink> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/workflows/${encodeURIComponent(workflowId)}/shares/${encodeURIComponent(shareId)}`
      : `/api/v1/workflows/${encodeURIComponent(workflowId)}/shares/${encodeURIComponent(shareId)}`;
    return this.request<ShareLink>(path, {
      method: "DELETE",
      credentials: "include",
      headers: {
        "X-Krama": "1",
      },
    });
  }

  async searchTutorials(
    query: string,
    options?: { status?: "all" | TutorialStatus; limit?: number },
  ): Promise<TutorialSummary[]> {
    const params = new URLSearchParams({ q: query, limit: String(options?.limit ?? 30) });
    if (options?.status === "verified" || options?.status === "outdated") params.set("status", options.status);
    const page = await this.request<WorkflowPage>(`/workflows?${params.toString()}`);
    return page.items.map((w) => ({
      ...summaryOf(w),
      snippet: w.match?.snippet ?? undefined,
      matchStep: w.match?.step_seq ?? null,
    }));
  }

  async getTutorials(options?: { limit?: number; status?: "all" | TutorialStatus }): Promise<TutorialSummary[]> {
    // The API has no /tutorials endpoint (docs/api-contract.md): a tutorial is a stored workflow.
    const workflowStatus: WorkflowStatus | "all" =
      options?.status === "verified" || options?.status === "outdated"
        ? options.status
        : "all";
    const workflowsPage = await this.getWorkflows(options?.limit ?? 100, workflowStatus);
    return workflowsPage.items.map(summaryOf);
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

  launchManualLogin(target: string): Promise<ManualLoginResponse> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/sessions/manual-login?target=${encodeURIComponent(target)}`
      : `/api/v1/sessions/manual-login?target=${encodeURIComponent(target)}`;
    return this.request<ManualLoginResponse>(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Krama": "1",
      },
    });
  }

  getSessionStatus(target: string): Promise<SessionStatus> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/sessions/status?target=${encodeURIComponent(target)}`
      : `/api/v1/sessions/status?target=${encodeURIComponent(target)}`;
    return this.request<SessionStatus>(path, {
      headers: {
        "X-Krama": "1",
      },
    });
  }

  login(request: LoginRequest): Promise<User> {
    const path = this.baseUrl.endsWith("/api/v1") ? "/auth/login" : "/api/v1/auth/login";
    return this.request<User>(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Krama": "1",
      },
      body: JSON.stringify(request),
    });
  }

  logout(): Promise<void> {
    const path = this.baseUrl.endsWith("/api/v1") ? "/auth/logout" : "/api/v1/auth/logout";
    return this.request<void>(path, {
      method: "POST",
      headers: {
        "X-Krama": "1",
      },
    });
  }

  getMe(): Promise<User> {
    const path = this.baseUrl.endsWith("/api/v1") ? "/auth/me" : "/api/v1/auth/me";
    return this.request<User>(path, {
      headers: {
        "X-Krama": "1",
      },
    });
  }

  async getSharedTutorial(token: string): Promise<TutorialSpec> {
    // GET /shared/{token} returns a Workflow (contracts/schemas/share.schema.json, docs/api-contract.md).
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/shared/${encodeURIComponent(token)}`
      : `/api/v1/shared/${encodeURIComponent(token)}`;
    const data = await this.request<TutorialSpec | Workflow>(path);
    if ("scenes" in data && "viewport" in data) {
      return data as TutorialSpec;
    }
    return compileWorkflow(data as Workflow);
  }

  async getMetricsSummary(): Promise<MetricsSummary> {
    const path = this.baseUrl.endsWith("/api/v1") ? "/metrics/summary" : "/api/v1/metrics/summary";
    return this.request<MetricsSummary>(path);
  }

  async getReviewQueue(): Promise<ReviewQueueItem[]> {
    // Errors propagate: the real client never shows mock items (#377).
    const path = this.baseUrl.endsWith("/api/v1") ? "/reviews" : "/api/v1/reviews";
    const data = await this.request<ReviewItemList>(path);
    return data.items.map(toReviewQueueItem);
  }

  async getReviewQueueCount(): Promise<ReviewQueueCountResponse> {
    const path = this.baseUrl.endsWith("/api/v1") ? "/reviews/count" : "/api/v1/reviews/count";
    const data = await this.request<ReviewCount>(path);
    return { count: data.count };
  }

  async acceptReview(id: string): Promise<ReviewActionResponse> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/reviews/${encodeURIComponent(id)}/accept`
      : `/api/v1/reviews/${encodeURIComponent(id)}/accept`;
    const result = await this.request<ReviewActionResult>(path, {
      method: "POST",
      headers: { "X-Krama": "1", "Content-Type": "application/json" },
    });
    return { success: true, message: result.message, workflow_id: result.workflow_id };
  }

  async rejectReview(id: string): Promise<ReviewActionResponse> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/reviews/${encodeURIComponent(id)}/reject`
      : `/api/v1/reviews/${encodeURIComponent(id)}/reject`;
    const result = await this.request<ReviewActionResult>(path, {
      method: "POST",
      headers: { "X-Krama": "1", "Content-Type": "application/json" },
    });
    return { success: true, message: result.message, workflow_id: result.workflow_id };
  }

  async regenerateWorkflow(workflowId: string): Promise<{ id: string; run_id?: string; status: string }> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/workflows/${encodeURIComponent(workflowId)}/regenerate`
      : `/api/v1/workflows/${encodeURIComponent(workflowId)}/regenerate`;
    return this.request<{ id: string; run_id?: string; status: string }>(path, {
      method: "POST",
      headers: { "X-Krama": "1", "Content-Type": "application/json" },
    });
  }

  async retryAiFix(workflowId: string): Promise<{ success: boolean; status?: string }> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/workflows/${encodeURIComponent(workflowId)}/retry-ai-fix`
      : `/api/v1/workflows/${encodeURIComponent(workflowId)}/retry-ai-fix`;
    // 202 Run (a reverify run that may ask Gemini to heal); 429 rate_limited when today's budget is used up.
    const run = await this.request<Run>(path, {
      method: "POST",
      headers: { "X-Krama": "1", "Content-Type": "application/json" },
    });
    return { success: true, status: run.status };
  }

  async reverifyWorkflow(workflowId: string): Promise<Run> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/workflows/${encodeURIComponent(workflowId)}/reverify`
      : `/api/v1/workflows/${encodeURIComponent(workflowId)}/reverify`;
    return this.request<Run>(path, {
      method: "POST",
      headers: { "X-Krama": "1", "Content-Type": "application/json" },
    });
  }

  startTakeover(runId: string): Promise<Run> {
    return this.request<Run>(`/runs/${encodeURIComponent(runId)}/takeover`, this.json("POST"));
  }

  startSignIn(site: string): Promise<Run> {
    return this.request<Run>(`/sites/${encodeURIComponent(site)}/sign-in`, this.json("POST"));
  }

  handBack(runId: string, stepSeq: number, done: HandBackDone): Promise<Run> {
    return this.request<Run>(
      `/runs/${encodeURIComponent(runId)}/handback`,
      this.json("POST", { step_seq: stepSeq, done }),
    );
  }

  openScreen(runId: string): ScreenConnection {
    const base = this.baseUrl.replace(/^http/, "ws");
    return new WebSocketScreen(`${base}/runs/${encodeURIComponent(runId)}/screen`);
  }

  getWorkflowInputs(workflowId: string): Promise<WorkflowInputList> {
    return this.request<WorkflowInputList>(`/workflows/${encodeURIComponent(workflowId)}/inputs`);
  }

  runWorkflow(workflowId: string, revision: number, inputs: Record<string, string>): Promise<Run> {
    return this.request<Run>(
      `/workflows/${encodeURIComponent(workflowId)}/run`,
      this.json("POST", { revision, inputs }),
    );
  }

  getTranslation(workflowId: string, language: Language): Promise<Translation> {
    return this.request<Translation>(
      `/workflows/${encodeURIComponent(workflowId)}/translations/${encodeURIComponent(language)}`,
    );
  }

  async createExport(workflowId: string, preset: ExportPreset, language: Language = "en"): Promise<Export> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/workflows/${encodeURIComponent(workflowId)}/exports`
      : `/api/v1/workflows/${encodeURIComponent(workflowId)}/exports`;
    return this.request<Export>(path, {
      method: "POST",
      headers: { "X-Krama": "1", "Content-Type": "application/json" },
      body: JSON.stringify(language === "en" ? { preset } : { preset, language }),
    });
  }

  async getExport(exportId: string): Promise<Export> {
    const path = this.baseUrl.endsWith("/api/v1")
      ? `/exports/${encodeURIComponent(exportId)}`
      : `/api/v1/exports/${encodeURIComponent(exportId)}`;
    return this.request<Export>(path, {
      headers: { "X-Krama": "1" },
    });
  }

  getExportDownloadUrl(exportId: string): string {
    const base = this.baseUrl.endsWith("/api/v1") ? this.baseUrl : `${this.baseUrl}/api/v1`;
    return `${base}/exports/${encodeURIComponent(exportId)}/download`;
  }

  getExportCaptionsUrl(exportId: string): string {
    const base = this.baseUrl.endsWith("/api/v1") ? this.baseUrl : `${this.baseUrl}/api/v1`;
    return `${base}/exports/${encodeURIComponent(exportId)}/captions.vtt`;
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
        const response = await fetch(url, { headers, signal, cache: "no-store", credentials: "include" });
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

function mockError(
  status: number,
  code: ApiError["code"],
  message: string,
  details?: Record<string, unknown>,
): ApiRequestError {
  return new ApiRequestError(`Request failed with status ${status}: ${message}`, status, { code, message, details });
}

/** `text` with each of `words` wrapped in <mark></mark> (mock search). */
function markWords(text: string, words: string[]): string {
  if (!words.length) return text;
  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  return text.replace(new RegExp(`(${escaped.join("|")})`, "gi"), "<mark>$1</mark>");
}

/** A stored workflow as a library card. */
function summaryOf(w: WorkflowPage["items"][number]): TutorialSummary {
  return {
    id: w.id,
    title: w.title,
    description: undefined,
    taskPrompt: w.title,
    target: (w.target_app === "github" ? "github" : w.target_app === "custom" ? "custom" : "gitea") as TargetPlatform,
    status: workflowFreshness(w) as TutorialStatus,
    stepCount: w.step_count,
    durationMs: w.step_count * 18000,
    createdAt: w.created_at ?? new Date().toISOString(),
  };
}

/** Why a "Do it for me" value can't be used (the server's input_unsafe rules), or null when it can. */
export function inputProblem(input: WorkflowInput, value: string | undefined): string | null {
  if (value === undefined || value === "") return `${input.label} is missing`;
  if (value !== value.trim() || /[\r\n]/.test(value)) {
    return `${input.label} must be one line without leading or trailing spaces`;
  }
  if (value.length < input.min_length) return `${input.label} needs at least ${input.min_length} characters`;
  if (input.pattern && !new RegExp(input.pattern).test(value)) {
    return `${input.label} may only use the same kind of characters as the example`;
  }
  return null;
}

/** Mock-mode inputs for a fixture workflow: its non-sensitive single-line fills. */
function mockInputs(workflow: Workflow): WorkflowInput[] {
  const seen = new Set<string>();
  const inputs: WorkflowInput[] = [];
  for (const step of workflow.steps) {
    const value = step.action.value;
    if (step.action.type !== "fill" || step.sensitive || !value || /\n/.test(value) || seen.has(value)) continue;
    seen.add(value);
    const label = (step.target.name ?? "").replace(/\s*\*$/, "").trim() || `Value for step ${step.seq}`;
    inputs.push({
      key: label.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || `step_${step.seq}_value`,
      label: label[0].toUpperCase() + label.slice(1).toLowerCase(),
      example: value,
      kind: "text",
      pattern: /\s/.test(value) ? null : "^[A-Za-z0-9._-]+$",
      min_length: Math.min(3, value.length),
      steps: [step.seq],
    });
  }
  return inputs;
}

export class MockApiClient implements ApiClient {
  private readonly plans: Record<string, Plan> = {};
  private readonly tasks = new Map<string, Pick<Task, "prompt" | "target_url">>();
  private readonly runs = new Map<string, MockRunState>();
  private readonly runsList: RunListItem[];
  private readonly runDetailsMap: Record<string, RunDetails>;
  private readonly sessionStatuses = new Map<string, SessionStatus>();
  private readonly manualLoginPending = new Set<string>();
  private readonly mockReviewQueue: ReviewQueueItem[] = mockReviewQueueItems.map((item) => ({ ...item }));
  private static readonly globalShares = new Map<string, ShareLink[]>();
  mockAutoActivateSession = true;

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

  async getWorkflows(limit = 50, status?: WorkflowStatus | "all"): Promise<WorkflowPage> {
    const seen = new Set<string>();
    const unique = Object.values(this.workflows).filter((w) => {
      if (seen.has(w.id)) return false;
      seen.add(w.id);
      return true;
    });
    const items = unique
      .filter((w) => (status === "all" ? true : status ? w.status === status : w.status === "verified"))
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

  async getWorkflowVersions(workflowId: string): Promise<WorkflowVersionList> {
    if (workflowId === "error-workflow" || workflowId === "error-versions") {
      throw mockError(500, "internal", "Failed to retrieve workflow versions: Database unreachable");
    }
    if (workflowId === "baseline-only" || workflowId === "baseline-workflow") {
      return {
        items: [
          {
            id: "ver-baseline-1",
            workflow_id: workflowId,
            revision: 1,
            source: "initial",
            status: "current",
            step_count: 5,
            change_summary: null,
            created_at: "2026-10-06T12:00:00.000Z",
          },
        ],
      };
    }
    if (mockWorkflowVersions[workflowId]) {
      return mockWorkflowVersions[workflowId];
    }
    return giteaVersionsFixture;
  }

  async searchTutorials(
    query: string,
    options?: { status?: "all" | TutorialStatus; limit?: number },
  ): Promise<TutorialSummary[]> {
    // Mock mode: every word must appear in the title or prompt; the matched words are marked like the server does.
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    const list = await this.getTutorials({ status: options?.status ?? "all" });
    return list
      .filter((t) => words.every((w) => `${t.title} ${t.taskPrompt ?? ""} ${t.description ?? ""} ${t.target}`.toLowerCase().includes(w)))
      .slice(0, options?.limit ?? 30)
      .map((t) => {
        const marked = markWords(t.title, words);
        return { ...t, snippet: marked.includes("<mark>") ? marked : undefined, matchStep: null };
      });
  }

  async getTutorials(options?: { limit?: number; status?: "all" | TutorialStatus }): Promise<TutorialSummary[]> {
    const source = process.env.VITEST === "true" ? mockTutorialSummaries : mockAllFreshnessTutorialSummaries;
    let list = [...source];
    if (options?.status && options.status !== "all") {
      list = list.filter((t) => t.status === options.status);
    }
    if (options?.limit) {
      list = list.slice(0, options.limit);
    }
    return list;
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
    if (runId.includes("stream") || runId === "test-run-stream" || runId.startsWith("stream-")) {
      const def = this.runDetailsMap["default"] ?? mockRunDetails;
      return {
        ...def,
        run: {
          ...def.run,
          id: runId,
          status: "running",
        },
      };
    }
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

  async launchManualLogin(target: string): Promise<ManualLoginResponse> {
    this.sessionStatuses.set(target, {
      target,
      active: false,
      message: "Waiting for you to complete sign-in in the open browser...",
    });
    this.manualLoginPending.add(target);
    return {
      target,
      status: "launched",
      message: "Manual login browser launched",
    };
  }

  async getSessionStatus(target: string): Promise<SessionStatus> {
    const existing = this.sessionStatuses.get(target);
    if (!existing) {
      return {
        target,
        active: false,
        message: "No active session",
      };
    }
    if (this.manualLoginPending.has(target) && this.mockAutoActivateSession) {
      this.manualLoginPending.delete(target);
      const activeStatus: SessionStatus = {
        target,
        active: true,
        expires_at: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
        message: "Session Active (Encrypted Storage State Saved)",
      };
      this.sessionStatuses.set(target, activeStatus);
      return activeStatus;
    }
    return existing;
  }

  setMockSessionStatus(target: string, status: Partial<SessionStatus>): void {
    this.manualLoginPending.delete(target);
    this.sessionStatuses.set(target, {
      target,
      active: status.active ?? false,
      expires_at: status.expires_at ?? null,
      message: status.message,
    });
  }

  mockCurrentUser: User | null = demoUserFixture;

  async login(request: LoginRequest): Promise<User> {
    const email = request.email.trim().toLowerCase();
    if (email === "demo@krama.dev" && request.password.length > 0) {
      this.mockCurrentUser = demoUserFixture;
      if (typeof document !== "undefined") {
        document.cookie = "krama_session=demo-mock-token; path=/; max-age=86400; SameSite=Lax";
      }
      return demoUserFixture;
    }
    throw mockError(401, "unauthorized", "Invalid email or password");
  }

  async logout(): Promise<void> {
    this.mockCurrentUser = null;
    if (typeof document !== "undefined") {
      document.cookie = "krama_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    }
  }

  async getMe(): Promise<User> {
    if (typeof document !== "undefined") {
      const hasCookie = document.cookie.split(";").some((c) => c.trim().startsWith("krama_session="));
      if (!hasCookie && !this.mockCurrentUser) {
        throw mockError(401, "unauthorized", "Not signed in");
      }
    } else if (!this.mockCurrentUser) {
      throw mockError(401, "unauthorized", "Not signed in");
    }
    return this.mockCurrentUser ?? demoUserFixture;
  }

  async getSharedTutorial(token: string): Promise<TutorialSpec> {
    if (token === "revoked-token" || token === "invalid-token" || token === "404") {
      throw mockError(404, "not_found", "This tutorial link is invalid or has been revoked by the creator.");
    }
    if (tutorialSpecFixtures[token]) {
      return tutorialSpecFixtures[token];
    }
    if (workflowFixtures[token]) {
      try {
        return compileWorkflow(workflowFixtures[token]);
      } catch {
        return giteaTutorialSpecFixture;
      }
    }
    return giteaTutorialSpecFixture;
  }

  async getMetricsSummary(): Promise<MetricsSummary> {
    return mockMetricsSummary;
  }

  async getReviewQueue(): Promise<ReviewQueueItem[]> {
    return [...this.mockReviewQueue];
  }

  async getReviewQueueCount(): Promise<ReviewQueueCountResponse> {
    return { count: this.mockReviewQueue.length };
  }

  async acceptReview(id: string): Promise<ReviewActionResponse> {
    const idx = this.mockReviewQueue.findIndex((item) => item.id === id);
    if (idx !== -1) {
      this.mockReviewQueue.splice(idx, 1);
    }
    return { success: true, message: "Healed version is now live" };
  }

  async rejectReview(id: string): Promise<ReviewActionResponse> {
    const idx = this.mockReviewQueue.findIndex((item) => item.id === id);
    if (idx !== -1) {
      this.mockReviewQueue.splice(idx, 1);
    }
    return { success: true, message: "Pending heal rejected" };
  }

  async regenerateWorkflow(workflowId: string): Promise<{ id: string; run_id?: string; status: string }> {
    return { id: `run-regenerated-${workflowId}`, run_id: `run-regenerated-${workflowId}`, status: "planning" };
  }

  async retryAiFix(workflowId: string): Promise<{ success: boolean; status?: string }> {
    if (workflowId === "quota-exhausted" || workflowId.includes("quota")) {
      throw mockError(429, "rate_limited", "Daily AI fix quota reached (5/day). Please regenerate the workflow or retry tomorrow.");
    }
    return { success: true, status: "checking" };
  }

  async startSignIn(site: string): Promise<Run> {
    return {
      id: `run-sign-in-${site}`,
      plan_id: `plan-sign-in-${site}`,
      plan_revision: 1,
      kind: "sign_in",
      status: "queued",
      retry_count: 0,
      created_at: nowTs(),
    };
  }

  async startTakeover(runId: string): Promise<Run> {
    const run = await this.getRun(runId);
    return { ...run, status: "paused", takeover: { step_seq: run.current_seq ?? 1, started_at: nowTs() } };
  }

  async handBack(runId: string, stepSeq: number, done: HandBackDone): Promise<Run> {
    void done;
    const run = await this.getRun(runId);
    return { ...run, status: "running", current_seq: stepSeq, takeover: null };
  }

  openScreen(runId: string): ScreenConnection {
    void runId;
    return new MockScreen();
  }

  async getWorkflowInputs(workflowId: string): Promise<WorkflowInputList> {
    const workflow = this.workflows[workflowId];
    if (!workflow) throw mockError(404, "not_found", "Workflow not found");
    if (workflow.status !== "verified") {
      throw mockError(409, "conflict", "Only a verified workflow can run for you", { reason: "not_verified" });
    }
    if (workflowId === giteaWorkflowInputsFixture.workflow_id) return structuredClone(giteaWorkflowInputsFixture);
    return { workflow_id: workflowId, revision: workflow.revision ?? 1, inputs: mockInputs(workflow), account: "demo" };
  }

  async runWorkflow(workflowId: string, revision: number, inputs: Record<string, string>): Promise<Run> {
    const list = await this.getWorkflowInputs(workflowId);
    if (revision !== list.revision) {
      throw mockError(409, "conflict", "A newer version of this workflow exists", { reason: "stale_revision" });
    }
    for (const input of list.inputs) {
      const problem = inputProblem(input, inputs[input.key]);
      if (problem) {
        throw mockError(422, "validation_error", problem, { reason: "input_unsafe", key: input.key });
      }
    }
    return {
      id: `run-do-it-${workflowId}`,
      plan_id: `plan-do-it-${workflowId}`,
      plan_revision: 1,
      kind: "do_it",
      source_workflow_id: workflowId,
      status: "queued",
      retry_count: 0,
      created_at: nowTs(),
    };
  }

  async reverifyWorkflow(workflowId: string): Promise<Run> {
    const now = nowTs();
    return {
      id: `run-reverify-${workflowId}`,
      plan_id: `plan-reverify-${workflowId}`,
      plan_revision: 1,
      kind: "reverify",
      source_workflow_id: workflowId,
      status: "queued",
      retry_count: 0,
      created_at: now,
    };
  }

  async createShareLink(workflowId: string): Promise<ShareLinkCreated> {
    const token = `mock-token-${Math.random().toString(36).substring(2, 10)}`;
    const id = `share-${Math.random().toString(36).substring(2, 10)}`;
    const link: ShareLink = {
      id,
      workflow_id: workflowId,
      created_at: nowTs(),
      expires_at: null,
      revoked_at: null,
      last_used_at: null,
    };
    const list = MockApiClient.globalShares.get(workflowId) ?? [];
    list.unshift(link);
    MockApiClient.globalShares.set(workflowId, list);
    const origin = typeof window !== "undefined" ? window.location.origin : "http://localhost:3000";
    return {
      link,
      url: `${origin}/share/${token}`,
    };
  }

  async listShareLinks(workflowId: string): Promise<ShareLinkList> {
    const items = MockApiClient.globalShares.get(workflowId) ?? [];
    return { items: [...items] };
  }

  async revokeShareLink(workflowId: string, shareId: string): Promise<ShareLink> {
    const list = MockApiClient.globalShares.get(workflowId) ?? [];
    const link = list.find((item) => item.id === shareId);
    if (!link) {
      throw mockError(404, "not_found", "Share link not found");
    }
    if (!link.revoked_at) {
      link.revoked_at = nowTs();
    }
    return { ...link };
  }

  private static readonly globalExports = new Map<string, Export>();

  async getTranslation(workflowId: string, language: Language): Promise<Translation> {
    // Mock mode: the steps tagged with the language, labels untouched; ready at once.
    const workflow = await this.getWorkflow(workflowId);
    return {
      workflow_id: workflow.id,
      revision: workflow.revision ?? 1,
      language,
      status: "ready",
      title: language === "en" ? workflow.title : `[${language}] ${workflow.title}`,
      steps: workflow.steps.map((s) => ({
        step_seq: s.seq,
        text: language === "en" ? s.instruction_text : `[${language}] ${s.instruction_text}`,
        translated: true,
      })),
    };
  }

  async createExport(workflowId: string, preset: ExportPreset, language: Language = "en"): Promise<Export> {
    const id = `mock-export-${Math.random().toString(36).substring(2, 10)}`;
    const mockExport: Export = {
      id,
      workflow_id: workflowId,
      revision: 1,
      title: "Exported Tutorial",
      preset,
      voice: "en_US-ljspeech-medium",
      language,
      status: "queued",
      progress: 0,
      created_at: nowTs(),
      download_url: `/api/v1/exports/${id}/download`,
      captions_url: `/api/v1/exports/${id}/captions.vtt`,
    };
    MockApiClient.globalExports.set(id, mockExport);
    return { ...mockExport };
  }

  async getExport(exportId: string): Promise<Export> {
    const existing = MockApiClient.globalExports.get(exportId);
    if (!existing) {
      throw mockError(404, "not_found", "Export not found");
    }
    if (existing.status === "queued") {
      existing.status = "rendering";
      existing.progress = 30;
    } else if (existing.status === "rendering") {
      existing.progress = Math.min(100, existing.progress + 40);
      if (existing.progress >= 100) {
        existing.status = "ready";
        existing.duration_ms = 12000;
        existing.size_bytes = 2450000;
        existing.finished_at = nowTs();
      }
    }
    return { ...existing };
  }

  getExportDownloadUrl(exportId: string): string {
    return `/api/v1/exports/${exportId}/download`;
  }

  getExportCaptionsUrl(exportId: string): string {
    return `/api/v1/exports/${exportId}/captions.vtt`;
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

/** Contract `ReviewItem` (snake_case, review.schema.json) -> the review UI's `ReviewQueueItem`. */
export function toReviewQueueItem(item: ReviewItem): ReviewQueueItem {
  const platform = item.target_app === "gitea" || item.target_app === "github" ? item.target_app : "custom";
  return {
    id: item.id,
    workflowId: item.workflow_id,
    workflowTitle: item.workflow_title,
    targetPlatform: platform,
    category: item.category,
    reason: item.reason,
    failedStepIndex: item.step_seq ?? undefined,
    createdAt: item.since,
    pendingVersion: item.pending_revision ? `v${item.pending_revision}` : undefined,
    currentVersion: item.current_revision ? `v${item.current_revision}` : undefined,
    stepDiffs: item.step_diff ? parseStepDiffs(item.step_diff) : undefined,
    canRetryAiFix: item.actions.includes("retry_ai_fix"),
  };
}
