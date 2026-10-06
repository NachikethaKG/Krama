// Thin API client seam (docs/architecture.md §4). `mock` mode serves fixtures, so the UI never waits on the backend.
import type { HealthResponse, RunEvent, Workflow } from "@krama/contracts-ts";

import {
  giteaEventsFixture,
  giteaWorkflowFixture,
  validWorkflowFixture,
  workflowFixtures,
} from "./fixtures";

export type { HealthResponse, RunEvent, Workflow };
export {
  giteaEventsFixture,
  giteaWorkflowFixture,
  validWorkflowFixture,
  workflowFixtures,
};

export interface StreamOptions {
  speed?: number;
  signal?: AbortSignal;
}

export type ApiMode = "mock" | "http";

/**
 * API client interface for Krama frontend (docs/architecture.md §4).
 * Decouples UI components and pages from whether the backend is live or mocked.
 */
export interface ApiClient {
  /** Checks server/mock health status */
  health(): Promise<HealthResponse>;
  /** Fetches a verified workflow by ID */
  getWorkflow(id: string): Promise<Workflow>;
  /** Streams SSE run events for a workflow execution with timing and cancellation support */
  streamWorkflowEvents(id: string, options?: StreamOptions): AsyncIterable<RunEvent>;
  /** Alias for streamWorkflowEvents using run ID */
  runEvents(runId: string, options?: StreamOptions): AsyncIterable<RunEvent>;
}

export class HttpApiClient implements ApiClient {
  constructor(private readonly baseUrl: string) {}

  async health(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`);
    if (!response.ok) throw new Error(`health check failed: ${response.status}`);
    return (await response.json()) as HealthResponse;
  }

  async getWorkflow(id: string): Promise<Workflow> {
    const response = await fetch(`${this.baseUrl}/workflows/${id}`);
    if (!response.ok) throw new Error(`getWorkflow failed: ${response.status}`);
    return (await response.json()) as Workflow;
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  async *streamWorkflowEvents(_id: string, _options?: StreamOptions): AsyncIterable<RunEvent> {
    // Live SSE streaming over fetch/EventSource will be wired with backend in Phase 1
    yield* [];
  }

  runEvents(runId: string, options?: StreamOptions): AsyncIterable<RunEvent> {
    return this.streamWorkflowEvents(runId, options);
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
  constructor(
    private readonly events: RunEvent[] = giteaEventsFixture,
    private readonly workflows: Record<string, Workflow> = workflowFixtures
  ) {}

  async health(): Promise<HealthResponse> {
    return { status: "ok", version: "mock" };
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
      "",
    ]);
    if (!validIds.has(id) && !this.workflows[id]) {
      throw new Error(`Workflow not found: ${id}`);
    }
    return replayEvents(this.events, options);
  }

  runEvents(runId: string, options?: StreamOptions): AsyncIterable<RunEvent> {
    return this.streamWorkflowEvents(runId, options);
  }
}

export function createApiClient(
  mode: string | undefined = process.env.NEXT_PUBLIC_API_MODE,
  baseUrl: string = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
): ApiClient {
  return mode === "http" ? new HttpApiClient(baseUrl) : new MockApiClient();
}
