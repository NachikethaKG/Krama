// Thin API client seam (docs/architecture.md §4). `mock` mode serves fixtures, so the UI never waits on the backend.
import type { HealthResponse } from "@krama/contracts-ts";

export type { HealthResponse };

export type ApiMode = "mock" | "http";

export interface ApiClient {
  health(): Promise<HealthResponse>;
}

export class HttpApiClient implements ApiClient {
  constructor(private readonly baseUrl: string) {}

  async health(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`);
    if (!response.ok) throw new Error(`health check failed: ${response.status}`);
    return (await response.json()) as HealthResponse;
  }
}

export class MockApiClient implements ApiClient {
  async health(): Promise<HealthResponse> {
    return { status: "ok", version: "mock" };
  }
}

export function createApiClient(
  mode: string | undefined = process.env.NEXT_PUBLIC_API_MODE,
  baseUrl: string = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
): ApiClient {
  return mode === "http" ? new HttpApiClient(baseUrl) : new MockApiClient();
}
