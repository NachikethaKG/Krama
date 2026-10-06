// Thin API client seam (docs/architecture.md §4). `mock` mode serves fixtures, so the UI never waits on the backend.
import type { HealthResponse, RunEvent, Workflow } from "@krama/contracts-ts";

import { giteaWorkflowFixture, workflowFixtures } from "./fixtures";

export type { HealthResponse, RunEvent, Workflow };

export interface StreamOptions {
  speed?: number;
  signal?: AbortSignal;
}

export type ApiMode = "mock" | "http";

export interface ApiClient {
  health(): Promise<HealthResponse>;
  getWorkflow(id: string): Promise<Workflow>;
  streamWorkflowEvents(id: string, options?: StreamOptions): AsyncIterable<RunEvent>;
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

  async *streamWorkflowEvents(_id: string, _options?: StreamOptions): AsyncIterable<RunEvent> {
    // Live SSE streaming over fetch/EventSource will be wired with backend in Phase 1
    yield* [];
  }

  runEvents(runId: string, options?: StreamOptions): AsyncIterable<RunEvent> {
    return this.streamWorkflowEvents(runId, options);
  }
}

export class MockApiClient implements ApiClient {
  async health(): Promise<HealthResponse> {
    return { status: "ok", version: "mock" };
  }

  async getWorkflow(id: string): Promise<Workflow> {
    const fixture = workflowFixtures[id] ?? (id === "" ? giteaWorkflowFixture : undefined);
    if (!fixture) {
      throw new Error(`Workflow not found: ${id}`);
    }
    return fixture;
  }

  async *streamWorkflowEvents(_id: string, _options?: StreamOptions): AsyncIterable<RunEvent> {
    yield* [];
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
