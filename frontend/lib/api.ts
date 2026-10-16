// Thin API client seam (docs/architecture.md §4). `mock` mode serves fixtures, so the UI never waits on the backend.
import type {
  HealthResponse,
  Plan,
  PlannedStep,
  Run,
  RunEvent,
  Task,
  Workflow,
} from "@krama/contracts-ts";

import {
  blockedWorkflowFixture,
  failedWorkflowFixture,
  giteaBlockedEventsFixture,
  giteaEventsFixture,
  giteaFailedEventsFixture,
  giteaPausedEventsFixture,
  giteaReplanEventsFixture,
  giteaWorkflowFixture,
  mockRunDetails,
  mockRunsList,
  pausedWorkflowFixture,
  replanWorkflowFixture,
  restrictedWorkflowFixture,
  validWorkflowFixture,
  workflowFixtures,
} from "./fixtures";
import type {
  PaginatedRunsResponse,
  RunDetails,
  RunListItem,
  StepEvidenceDetail,
  StepVerificationEvidence,
  VerificationEvidenceMethod,
} from "./types";

export type {
  HealthResponse,
  PaginatedRunsResponse,
  Plan,
  Run,
  RunDetails,
  RunEvent,
  RunListItem,
  StepEvidenceDetail,
  StepVerificationEvidence,
  Task,
  VerificationEvidenceMethod,
  Workflow,
};
export {
  blockedWorkflowFixture,
  failedWorkflowFixture,
  giteaBlockedEventsFixture,
  giteaEventsFixture,
  giteaFailedEventsFixture,
  giteaPausedEventsFixture,
  giteaReplanEventsFixture,
  giteaWorkflowFixture,
  mockRunDetails,
  mockRunsList,
  pausedWorkflowFixture,
  replanWorkflowFixture,
  restrictedWorkflowFixture,
  validWorkflowFixture,
  workflowFixtures,
};

export interface StreamOptions {
  speed?: number;
  signal?: AbortSignal;
}

export type ApiMode = "mock" | "http";

export interface PlanUpdatePayload {
  steps: PlannedStep[];
}

/**
 * API client interface for Krama frontend (docs/architecture.md §4).
 * Decouples UI components and pages from whether the backend is live or mocked.
 */
export interface ApiClient {
  /** Checks server/mock health status */
  health(): Promise<HealthResponse>;
  /** Starts planning in the background for a prompt and target URL */
  createTask(prompt: string, targetUrl: string): Promise<Task>;
  /** Fetches task status by ID */
  getTask(taskId: string): Promise<Task>;
  /** Fetches a plan by ID */
  getPlan(planId: string): Promise<Plan>;
  /** Updates plan steps with revision check via PATCH /plans/{id} */
  updatePlan(planId: string, revision: number, updates: PlanUpdatePayload | PlannedStep[]): Promise<Plan>;
  /** Approves a plan and queues a run */
  approvePlan(planId: string, revision?: number): Promise<Run>;
  /** Fetches run status by ID */
  getRun(runId: string): Promise<Run>;
  /** Cancels an active or paused run */
  cancelRun(runId: string): Promise<Run>;
  /** Answers a paused run (allow or deny) */
  confirmRun(runId: string, stepSeq: number, decision: "allow" | "deny"): Promise<Run>;
  /** Confirms or denies a paused run action per safety baseline */
  confirmRunAction(runId: string, decision: "allow" | "deny", stepSeq?: number): Promise<void>;
  /** Streams SSE run events for a run */
  streamRunEvents(runId: string, options?: StreamOptions | AbortSignal): AsyncIterable<RunEvent>;
  /** Fetches a verified workflow by ID */
  getWorkflow(id: string): Promise<Workflow>;
  /** Streams SSE run events for a workflow execution with timing and cancellation support */
  streamWorkflowEvents(id: string, options?: StreamOptions): AsyncIterable<RunEvent>;
  /** Alias for streamWorkflowEvents using run ID */
  runEvents(runId: string, options?: StreamOptions): AsyncIterable<RunEvent>;
  /** Fetches paginated runs list */
  getRuns(page?: number, limit?: number, cursor?: string): Promise<PaginatedRunsResponse>;
  /** Fetches detailed run execution metadata, workflow steps, and verification evidence */
  getRunDetails(runId: string): Promise<RunDetails>;
}

/**
 * Parses an SSE byte stream into RunEvent objects according to docs/api-contract.md.
 */
export async function* parseEventStream(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<RunEvent, void, unknown> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (!signal?.aborted) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split(/\r?\n\r?\n/);
      buffer = parts.pop() ?? "";

      for (const part of parts) {
        if (!part.trim()) continue;
        const lines = part.split(/\r?\n/);
        let dataStr = "";

        for (const line of lines) {
          if (line.startsWith(":")) {
            // Keep-alive ping comment, ignore
            continue;
          }
          if (line.startsWith("data:")) {
            const dataPart = line.slice(5).trim();
            dataStr = dataStr ? `${dataStr}\n${dataPart}` : dataPart;
          }
        }

        if (dataStr) {
          try {
            const parsed = JSON.parse(dataStr) as RunEvent;
            yield parsed;
          } catch {
            // Ignore unparseable frames
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export class HttpApiClient implements ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
    let response: Response;
    try {
      response = init !== undefined ? await fetch(url, init) : await fetch(url);
    } catch (err) {
      throw new Error(`Network request failed for ${url}: ${err instanceof Error ? err.message : String(err)}`);
    }

    if (!response.ok) {
      let detail = "";
      try {
        const json = await response.json();
        if (json?.error?.message) {
          detail = `: ${json.error.message}`;
        } else {
          detail = `: ${JSON.stringify(json)}`;
        }
      } catch {
        try {
          const text = await response.text();
          if (text) detail = `: ${text}`;
        } catch {
          // ignore
        }
      }
      throw new Error(`Request to ${path} failed with status ${response.status}${detail}`);
    }

    return (await response.json()) as T;
  }

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("/health");
  }

  async createTask(prompt: string, targetUrl: string): Promise<Task> {
    return this.request<Task>("/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, target_url: targetUrl }),
    });
  }

  async getTask(taskId: string): Promise<Task> {
    return this.request<Task>(`/tasks/${taskId}`);
  }

  async getPlan(planId: string): Promise<Plan> {
    return this.request<Plan>(`/plans/${planId}`);
  }

  async updatePlan(
    planId: string,
    revision: number,
    updates: PlanUpdatePayload | PlannedStep[],
  ): Promise<Plan> {
    const steps = Array.isArray(updates) ? updates : updates.steps;
    return this.request<Plan>(`/plans/${planId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision, steps }),
    });
  }

  async approvePlan(planId: string, revision?: number): Promise<Run> {
    let rev = revision;
    if (rev === undefined) {
      const plan = await this.getPlan(planId);
      rev = plan.revision;
    }
    return this.request<Run>(`/plans/${planId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ revision: rev }),
    });
  }

  async getRun(runId: string): Promise<Run> {
    return this.request<Run>(`/runs/${runId}`);
  }

  async cancelRun(runId: string): Promise<Run> {
    return this.request<Run>(`/runs/${runId}/cancel`, {
      method: "POST",
    });
  }

  async confirmRun(runId: string, stepSeq: number, decision: "allow" | "deny"): Promise<Run> {
    return this.request<Run>(`/runs/${runId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ step_seq: stepSeq, decision }),
    });
  }

  async confirmRunAction(runId: string, decision: "allow" | "deny", stepSeq?: number): Promise<void> {
    await this.confirmRun(runId, stepSeq ?? 1, decision);
  }

  async getWorkflow(id: string): Promise<Workflow> {
    try {
      return await this.request<Workflow>(`/workflows/${id}`);
    } catch (err) {
      // If 404, check if this id is a plan id so the approval screen can render proposed steps
      if (err instanceof Error && err.message.includes("404")) {
        try {
          const plan = await this.getPlan(id);
          return {
            id: plan.id,
            title: plan.expected_result || "Generated Workflow Plan",
            task: plan.expected_result,
            target_url: "http://localhost:3001",
            target_app: "gitea",
            status: plan.status === "proposed" ? "draft" : (plan.status as Workflow["status"]),
            steps: plan.steps.map((s) => ({
              id: `${plan.id}-${s.seq}`,
              seq: s.seq,
              action: s.action,
              target: s.target,
              instruction_text: s.instruction_text,
              risk: s.risk,
              expected_state: s.expected_state,
              observed_state: { url: "" },
              verification: { result: "skipped" as const, method: ["url" as const], confidence: 1 },
            })),
          };
        } catch {
          // Fall through to throw original workflow error
        }
      }
      throw err;
    }
  }

  async *streamRunEvents(
    runId: string,
    options?: StreamOptions | AbortSignal,
  ): AsyncIterable<RunEvent> {
    const signal = options instanceof AbortSignal ? options : options?.signal;
    const url = `${this.baseUrl}/runs/${runId}/events`;
    let response: Response;
    try {
      response = await fetch(url, {
        headers: { Accept: "text/event-stream" },
        signal,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      throw new Error(`SSE connection failed for ${url}: ${err instanceof Error ? err.message : String(err)}`);
    }

    if (!response.ok) {
      let detail = "";
      try {
        const text = await response.text();
        if (text) detail = `: ${text}`;
      } catch {
        // ignore
      }
      throw new Error(`streamRunEvents failed with status ${response.status}${detail}`);
    }

    if (!response.body) {
      throw new Error("No response body received for SSE stream");
    }

    yield* parseEventStream(response.body, signal);
  }

  streamWorkflowEvents(id: string, options?: StreamOptions): AsyncIterable<RunEvent> {
    return this.streamRunEvents(id, options);
  }

  runEvents(runId: string, options?: StreamOptions): AsyncIterable<RunEvent> {
    return this.streamRunEvents(runId, options);
  }

  async getRuns(page: number = 1, limit: number = 5, cursor?: string): Promise<PaginatedRunsResponse> {
    const params = new URLSearchParams();
    if (cursor) {
      params.set("cursor", cursor);
    } else {
      params.set("limit", String(limit));
    }
    const query = params.toString() ? `?${params.toString()}` : "";
    const res = await this.request<{ items: Run[]; next_cursor?: string | null }>(`/runs${query}`);
    const items: RunListItem[] = (res.items || []).map((r) => ({
      id: r.id,
      prompt: r.plan_id ? `Run for plan ${r.plan_id}` : `Run ${r.id}`,
      status: r.status,
      createdAt: r.created_at,
      startedAt: r.started_at,
      finishedAt: r.finished_at,
      durationSeconds:
        r.started_at && r.finished_at
          ? Math.max(0, Math.round((new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) / 1000))
          : null,
      workflowId: r.workflow_id,
      planId: r.plan_id,
      retryCount: r.retry_count,
    }));
    return {
      items,
      total: items.length,
      page,
      pageSize: limit,
      totalPages: Math.ceil(items.length / limit) || 1,
      nextCursor: res.next_cursor,
    };
  }

  async getRunDetails(runId: string): Promise<RunDetails> {
    const run = await this.getRun(runId);
    let workflow: Workflow | null = null;
    if (run.workflow_id) {
      try {
        workflow = await this.getWorkflow(run.workflow_id);
      } catch {
        // workflow may not yet exist
      }
    }
    const steps: StepEvidenceDetail[] =
      workflow?.steps.map((s, idx) => {
        const verified = s.verification?.result === "verified";
        const methods = s.verification?.method || [];
        const method: VerificationEvidenceMethod =
          methods.includes("aria")
            ? "aria"
            : methods.includes("network")
              ? "network"
              : methods.includes("vision")
                ? "vision"
                : "url_dom";
        return {
          id: s.id ?? `step-${s.seq ?? idx + 1}`,
          seq: s.seq ?? idx + 1,
          instructionText: s.instruction_text,
          actionType: s.action?.type ?? "action",
          targetRole: s.target?.role,
          targetName: s.target?.name,
          risk: s.risk ?? "low",
          status: verified ? "verified" : s.verification?.result === "failed" ? "failed" : "pending",
          evidence: {
            method,
            confidence: s.verification?.confidence ?? 0.95,
            screenshotUrl: s.observed_state?.screenshot_path,
            observedAt: s.observed_state?.captured_at || new Date().toISOString(),
          },
          screenshotUrl: s.observed_state?.screenshot_path,
          expectedState: s.expected_state,
          observedState: s.observed_state,
        };
      }) ?? [];

    return {
      run: {
        id: run.id,
        prompt: workflow?.task ?? `Run ${run.id}`,
        status: run.status,
        createdAt: run.created_at,
        startedAt: run.started_at,
        finishedAt: run.finished_at,
        durationSeconds:
          run.started_at && run.finished_at
            ? Math.max(0, Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000))
            : null,
        workflowId: run.workflow_id,
        planId: run.plan_id,
        retryCount: run.retry_count,
      },
      workflow,
      targetUrl: workflow?.target_url || undefined,
      targetApp: workflow?.target_app || undefined,
      steps,
      summary: {
        totalSteps: steps.length,
        verifiedSteps: steps.filter((s) => s.status === "verified").length,
        failedSteps: steps.filter((s) => s.status === "failed").length,
        durationSeconds:
          run.started_at && run.finished_at
            ? Math.max(0, Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000))
            : null,
      },
    };
  }
}

/**
 * Replays an array of RunEvents asynchronously with realistic delays based on their timestamps (`ts`).
 * Supports speed scaling and mid-stream cancellation through AbortSignal.
 */
export async function* replayEvents(
  events: RunEvent[],
  options: StreamOptions = {}
): AsyncGenerator<RunEvent, void, unknown> {
  const { signal } = options;
  const rawSpeed = options.speed ?? Number(process.env.NEXT_PUBLIC_MOCK_SPEED);
  const speed = Number.isFinite(rawSpeed) && rawSpeed > 0 ? rawSpeed : 1;

  if (signal?.aborted) {
    throw new DOMException("aborted", "AbortError");
  }

  let prevTime: number | undefined;

  for (const event of events) {
    if (signal?.aborted) {
      throw new DOMException("aborted", "AbortError");
    }

    const eventTime = Date.parse(event.ts);
    if (prevTime !== undefined && !Number.isNaN(eventTime) && !Number.isNaN(prevTime)) {
      const delayMs = Math.max(0, (eventTime - prevTime) / speed);
      if (delayMs > 0) {
        await new Promise<void>((resolve, reject) => {
          if (signal?.aborted) {
            reject(new DOMException("aborted", "AbortError"));
            return;
          }

          const abortHandler = () => {
            clearTimeout(timer);
            reject(new DOMException("aborted", "AbortError"));
          };

          const timer = setTimeout(() => {
            signal?.removeEventListener("abort", abortHandler);
            resolve();
          }, delayMs);

          signal?.addEventListener("abort", abortHandler, { once: true });
        });
      }
    }
    prevTime = eventTime;

    if (signal?.aborted) {
      throw new DOMException("aborted", "AbortError");
    }

    yield event;
  }
}

export class MockApiClient implements ApiClient {
  private readonly plans: Record<string, Plan> = {};
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
  }

  async health(): Promise<HealthResponse> {
    return { status: "ok", version: "mock" };
  }

  async createTask(prompt: string, targetUrl: string): Promise<Task> {
    return {
      id: "mock-task-id",
      prompt,
      target_url: targetUrl,
      status: "planned",
      plan_id: giteaWorkflowFixture.id,
      created_at: new Date().toISOString(),
    };
  }

  async getTask(taskId: string): Promise<Task> {
    return {
      id: taskId,
      prompt: "Create a repository in local Gitea",
      target_url: "http://localhost:3001",
      status: "planned",
      plan_id: giteaWorkflowFixture.id,
      created_at: new Date().toISOString(),
    };
  }

  async getPlan(planId: string): Promise<Plan> {
    if (this.plans[planId]) {
      return this.plans[planId];
    }

    const plannedSteps = giteaWorkflowFixture.steps.map((s) => ({
      seq: s.seq,
      action: s.action,
      target: s.target,
      instruction_text: s.instruction_text,
      expected_state: s.expected_state,
      risk: s.risk,
    })) as [PlannedStep, ...PlannedStep[]];

    const plan: Plan = {
      id: planId || giteaWorkflowFixture.id,
      task_id: "mock-task-id",
      revision: 1,
      status: "proposed",
      risk: "medium",
      expected_result: "A new repository page is shown",
      steps: plannedSteps,
      created_at: new Date().toISOString(),
    };
    this.plans[plan.id] = plan;
    return plan;
  }

  async updatePlan(
    planId: string,
    revision: number,
    updates: PlanUpdatePayload | PlannedStep[],
  ): Promise<Plan> {
    const currentPlan = await this.getPlan(planId);
    if (revision !== currentPlan.revision) {
      throw new Error(
        `Request to /plans/${planId} failed with status 409: Plan revision ${revision} is stale; the current one is ${currentPlan.revision}`
      );
    }
    const steps = Array.isArray(updates) ? updates : updates.steps;
    if (steps.length === 0) {
      throw new Error("Plan must contain at least 1 step");
    }
    const updatedSteps = steps.map((s, idx) => ({
      ...s,
      seq: idx + 1,
    })) as [PlannedStep, ...PlannedStep[]];

    const updatedPlan: Plan = {
      ...currentPlan,
      revision: currentPlan.revision + 1,
      steps: updatedSteps,
    };
    this.plans[planId] = updatedPlan;
    return updatedPlan;
  }

  async approvePlan(planId: string, revision?: number): Promise<Run> {
    return {
      id: "mock-run-id",
      plan_id: planId,
      plan_revision: revision ?? 1,
      status: "queued",
      retry_count: 0,
      workflow_id: giteaWorkflowFixture.id,
      created_at: new Date().toISOString(),
    };
  }

  async getRun(runId: string): Promise<Run> {
    return {
      id: runId,
      plan_id: giteaWorkflowFixture.id,
      plan_revision: 1,
      status: "running",
      retry_count: 0,
      workflow_id: giteaWorkflowFixture.id,
      created_at: new Date().toISOString(),
    };
  }

  async cancelRun(runId: string): Promise<Run> {
    return {
      id: runId,
      plan_id: giteaWorkflowFixture.id,
      plan_revision: 1,
      status: "cancelled",
      retry_count: 0,
      created_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
    };
  }

  async confirmRun(runId: string, stepSeq: number, decision: "allow" | "deny"): Promise<Run> {
    return {
      id: runId,
      plan_id: giteaWorkflowFixture.id,
      plan_revision: 1,
      status: decision === "allow" ? "running" : "cancelled",
      current_seq: stepSeq,
      retry_count: 0,
      created_at: new Date().toISOString(),
    };
  }

  async confirmRunAction(runId: string, decision: "allow" | "deny", stepSeq?: number): Promise<void> {
    await this.confirmRun(runId, stepSeq ?? 1, decision);
  }

  async getWorkflow(id: string): Promise<Workflow> {
    const fixture = this.workflows[id] ?? (id === "" ? giteaWorkflowFixture : undefined);
    if (!fixture) {
      throw new Error(`Workflow not found: ${id}`);
    }
    return fixture;
  }

  streamWorkflowEvents(id: string, options?: StreamOptions): AsyncIterable<RunEvent> {
    const validIds = new Set([
      giteaWorkflowFixture.id,
      giteaWorkflowFixture.run_id ?? "",
      "gitea",
      "mock",
      "default",
      "paused",
      "failed",
      "replan",
      "blocked",
      "restricted",
      "",
    ]);
    if (!validIds.has(id) && !this.workflows[id]) {
      throw new Error(`Workflow not found: ${id}`);
    }

    if (id === "paused" || id.includes("paused")) {
      return replayEvents(giteaPausedEventsFixture, options);
    }
    if (id === "failed" || id.includes("failed")) {
      return replayEvents(giteaFailedEventsFixture, options);
    }
    if (id === "replan" || id.includes("replan")) {
      return replayEvents(giteaReplanEventsFixture, options);
    }
    if (id === "blocked" || id.includes("blocked") || id === "restricted" || id.includes("restricted")) {
      return replayEvents(giteaBlockedEventsFixture, options);
    }

    return replayEvents(this.events, options);
  }

  runEvents(runId: string, options?: StreamOptions): AsyncIterable<RunEvent> {
    return this.streamWorkflowEvents(runId, options);
  }

  streamRunEvents(runId: string, options?: StreamOptions | AbortSignal): AsyncIterable<RunEvent> {
    const streamOptions = options instanceof AbortSignal ? { signal: options } : options;
    return this.streamWorkflowEvents(runId, streamOptions);
  }

  async getRuns(page: number = 1, limit: number = 5): Promise<PaginatedRunsResponse> {
    const allRuns = this.runsList;
    const total = allRuns.length;
    const totalPages = Math.max(1, Math.ceil(total / limit));
    const currentPage = Math.max(1, Math.min(page, totalPages));
    const startIndex = (currentPage - 1) * limit;
    const items = allRuns.slice(startIndex, startIndex + limit);
    return {
      items,
      total,
      page: currentPage,
      pageSize: limit,
      totalPages,
      nextCursor: currentPage < totalPages ? `cursor-${currentPage + 1}` : null,
    };
  }

  async getRunDetails(runId: string): Promise<RunDetails> {
    const details =
      this.runDetailsMap[runId] ??
      (runId === "default" || runId === "mock" || runId === ""
        ? this.runDetailsMap["default"]
        : undefined);
    if (details) {
      return {
        ...details,
        run: {
          ...details.run,
          id: runId,
        },
      };
    }
    const wf = this.workflows[runId];
    if (wf) {
      const steps: StepEvidenceDetail[] = wf.steps.map((s, idx) => {
        const verified = s.verification?.result === "verified";
        const methods = s.verification?.method || [];
        const method: VerificationEvidenceMethod =
          methods.includes("aria")
            ? "aria"
            : methods.includes("network")
              ? "network"
              : methods.includes("vision")
                ? "vision"
                : "url_dom";
        return {
          id: s.id ?? `step-${s.seq ?? idx + 1}`,
          seq: s.seq ?? idx + 1,
          instructionText: s.instruction_text,
          actionType: s.action?.type ?? "action",
          targetRole: s.target?.role,
          targetName: s.target?.name,
          risk: s.risk ?? "low",
          status: verified ? "verified" : s.verification?.result === "failed" ? "failed" : "pending",
          evidence: {
            method,
            confidence: s.verification?.confidence ?? 0.95,
            screenshotUrl: s.observed_state?.screenshot_path,
            observedAt: s.observed_state?.captured_at || new Date().toISOString(),
          },
          screenshotUrl: s.observed_state?.screenshot_path,
          expectedState: s.expected_state,
          observedState: s.observed_state,
        };
      });
      return {
        run: {
          id: runId,
          prompt: wf.task || `Run ${runId}`,
          status: wf.status === "verified" ? "verified" : (wf.status as RunListItem["status"]),
          createdAt: wf.created_at || new Date().toISOString(),
          workflowId: wf.id,
        },
        workflow: wf,
        targetUrl: wf.target_url || undefined,
        targetApp: wf.target_app || undefined,
        steps,
        summary: {
          totalSteps: steps.length,
          verifiedSteps: steps.filter((s) => s.status === "verified").length,
          failedSteps: steps.filter((s) => s.status === "failed").length,
        },
      };
    }
    throw new Error(`Run details not found: ${runId}`);
  }
}

export function normalizeBaseUrl(url?: string): string {
  const raw = (url || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1").trim();
  const cleaned = raw.replace(/\/+$/, "");
  if (cleaned === "http://localhost:8000" || cleaned === "http://127.0.0.1:8000") {
    return `${cleaned}/api/v1`;
  }
  return cleaned;
}

/**
 * Returns an ApiClient instance based on NEXT_PUBLIC_API_MODE.
 * When NEXT_PUBLIC_API_MODE === "http", returns HttpApiClient; otherwise MockApiClient.
 */
export function getApiClient(): ApiClient {
  return process.env.NEXT_PUBLIC_API_MODE === "http"
    ? new HttpApiClient(normalizeBaseUrl(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"))
    : new MockApiClient();
}

export function createApiClient(
  mode: string | undefined = process.env.NEXT_PUBLIC_API_MODE,
  baseUrl: string = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
): ApiClient {
  return mode === "http" ? new HttpApiClient(baseUrl) : new MockApiClient();
}
