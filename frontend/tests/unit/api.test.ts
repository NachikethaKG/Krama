import { afterEach, describe, expect, it, vi } from "vitest";

import { createApiClient, HttpApiClient, MockApiClient } from "@/lib/api";

describe("createApiClient", () => {
  it("defaults to the mock client", () => {
    expect(createApiClient(undefined)).toBeInstanceOf(MockApiClient);
  });

  it("uses the http client in http mode", () => {
    expect(createApiClient("http", "http://api")).toBeInstanceOf(HttpApiClient);
  });
});

describe("HttpApiClient", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns the health payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", version: "0.1.0" }))),
    );

    await expect(new HttpApiClient("http://api").health()).resolves.toEqual({ status: "ok", version: "0.1.0" });
    expect(fetch).toHaveBeenCalledWith("http://api/health");
  });

  it("throws on a non-2xx response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("down", { status: 503 })));

    await expect(new HttpApiClient("http://api").health()).rejects.toThrow("503");
  });
});

describe("MockApiClient", () => {
  it("returns health response", async () => {
    const client = new MockApiClient();
    await expect(client.health()).resolves.toEqual({ status: "ok", version: "mock" });
  });

  describe("workflow fetching", () => {
    it("returns the realistic Gitea workflow fixture by id", async () => {
      const client = new MockApiClient();
      const workflow = await client.getWorkflow("6f1c2a4e-1111-4b8a-9a1b-123456789abc");
      expect(workflow.id).toBe("6f1c2a4e-1111-4b8a-9a1b-123456789abc");
      expect(workflow.title).toBe("Create a repository in local Gitea");
      expect(workflow.steps).toHaveLength(5);
      expect(workflow.status).toBe("verified");
    });

    it("returns default fixture when querying with alias 'mock' or 'default'", async () => {
      const client = new MockApiClient();
      const mockWf = await client.getWorkflow("mock");
      const defaultWf = await client.getWorkflow("default");
      expect(mockWf.id).toBe("6f1c2a4e-1111-4b8a-9a1b-123456789abc");
      expect(defaultWf.id).toBe("6f1c2a4e-1111-4b8a-9a1b-123456789abc");
    });

    it("throws an error when workflow id is not found", async () => {
      const client = new MockApiClient();
      await expect(client.getWorkflow("non-existent-id")).rejects.toThrow("Workflow not found: non-existent-id");
    });
  });

  describe("event stream replay", () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    it("throws an error when streaming events for non-existent workflow/run id", () => {
      const client = new MockApiClient();
      expect(() => client.streamWorkflowEvents("unknown-run-id")).toThrow("Workflow not found: unknown-run-id");
    });

    it("replays all 17 fixture events in chronological sequence with realistic delays", async () => {
      vi.useFakeTimers();
      const client = new MockApiClient();
      const stream = client.streamWorkflowEvents("mock", { speed: 1 });

      const collected: unknown[] = [];
      const playbackPromise = (async () => {
        for await (const event of stream) {
          collected.push(event);
        }
      })();

      await vi.runAllTimersAsync();
      await playbackPromise;

      expect(collected).toHaveLength(17);
      expect((collected[0] as { type: string }).type).toBe("run.started");
      expect((collected[collected.length - 1] as { type: string }).type).toBe("run.completed");

      // Verify sequence ordering
      for (let i = 0; i < collected.length; i++) {
        expect((collected[i] as { seq: number }).seq).toBe(i + 1);
      }
    });

    it("accelerates replay playback when speed multiplier is provided", async () => {
      vi.useFakeTimers();
      const client = new MockApiClient();
      const stream = client.runEvents("mock", { speed: 10 });

      const collected: unknown[] = [];
      const playbackPromise = (async () => {
        for await (const event of stream) {
          collected.push(event);
        }
      })();

      await vi.runAllTimersAsync();
      await playbackPromise;

      expect(collected).toHaveLength(17);
    });

    it("aborts immediately when signal is already aborted before starting", async () => {
      const client = new MockApiClient();
      const controller = new AbortController();
      controller.abort();

      const stream = client.streamWorkflowEvents("mock", { signal: controller.signal });
      await expect(async () => {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        for await (const _ of stream) {
          // should not be reached
        }
      }).rejects.toThrow("aborted");
    });

    it("aborts stream playback mid-way when signal is triggered", async () => {
      vi.useFakeTimers();
      const client = new MockApiClient();
      const controller = new AbortController();
      const stream = client.streamWorkflowEvents("mock", { speed: 1, signal: controller.signal });

      const collected: unknown[] = [];
      const playbackPromise = (async () => {
        for await (const event of stream) {
          collected.push(event);
          if (collected.length === 2) {
            controller.abort();
          }
        }
      })();

      const assertion = expect(playbackPromise).rejects.toThrow("aborted");
      await vi.advanceTimersByTimeAsync(600);
      await assertion;
      expect(collected).toHaveLength(2);
    });

    it("aborts stream playback while sleeping during delay", async () => {
      vi.useFakeTimers();
      const client = new MockApiClient();
      const controller = new AbortController();
      const stream = client.streamWorkflowEvents("mock", { speed: 1, signal: controller.signal });

      const collected: unknown[] = [];
      const playbackPromise = (async () => {
        for await (const event of stream) {
          collected.push(event);
        }
      })();

      const assertion = expect(playbackPromise).rejects.toThrow("aborted");
      await vi.advanceTimersByTimeAsync(250);
      expect(collected).toHaveLength(1);
      controller.abort();
      await vi.advanceTimersByTimeAsync(250);
      await assertion;
      expect(collected).toHaveLength(1);
    });

    it("falls back to 1x speed when invalid or negative NEXT_PUBLIC_MOCK_SPEED is provided", async () => {
      vi.useFakeTimers();
      const originalEnv = process.env.NEXT_PUBLIC_MOCK_SPEED;
      process.env.NEXT_PUBLIC_MOCK_SPEED = "-5";

      try {
        const client = new MockApiClient();
        const stream = client.streamWorkflowEvents("mock");
        const collected: unknown[] = [];
        const playbackPromise = (async () => {
          for await (const event of stream) {
            collected.push(event);
            if (collected.length === 2) break;
          }
        })();

        await vi.advanceTimersByTimeAsync(250);
        expect(collected).toHaveLength(1);
        await vi.advanceTimersByTimeAsync(250);
        await playbackPromise;
        expect(collected).toHaveLength(2);
      } finally {
        process.env.NEXT_PUBLIC_MOCK_SPEED = originalEnv;
      }
    });

    it("handles empty event stream cleanly without errors", async () => {
      const client = new MockApiClient([]);
      const stream = client.streamWorkflowEvents("mock");
      const collected: unknown[] = [];
      for await (const event of stream) {
        collected.push(event);
      }
      expect(collected).toHaveLength(0);
    });
  });
});
