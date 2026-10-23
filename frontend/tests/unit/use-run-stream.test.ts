import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRunStream } from "@/hooks/useRunStream";

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onerror: ((err: unknown) => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  listeners: Record<string, Array<(ev: { data: string }) => void>> = {};
  readyState = 0;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
    setTimeout(() => {
      this.readyState = 1;
      this.onopen?.();
    }, 0);
  }

  addEventListener(type: string, cb: (ev: { data: string }) => void) {
    this.listeners[type] = this.listeners[type] || [];
    this.listeners[type].push(cb);
  }

  removeEventListener(type: string, cb: (ev: { data: string }) => void) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter((l) => l !== cb);
    }
  }

  emit(type: string, data: unknown) {
    const event = { data: typeof data === "string" ? data : JSON.stringify(data) };
    if (this.listeners[type]) {
      this.listeners[type].forEach((cb) => cb(event));
    }
  }

  close() {
    this.readyState = 2;
  }
}

describe("useRunStream Hook", () => {
  const originalEventSource = globalThis.EventSource;
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    MockEventSource.instances = [];
    // @ts-expect-error mock assignment
    globalThis.EventSource = MockEventSource;
  });

  afterEach(() => {
    globalThis.EventSource = originalEventSource;
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("subscribes to /api/v1/runs/${id}/stream and sets up event listeners", async () => {
    const { result } = renderHook(() =>
      useRunStream({ runId: "run-stream-test", autoConnect: true }),
    );

    expect(MockEventSource.instances.length).toBe(1);
    const es = MockEventSource.instances[0];
    expect(es.url).toContain("/api/v1/runs/run-stream-test/stream");

    // Initially status is idle
    expect(result.current.status).toBe("idle");
    expect(result.current.steps).toEqual([]);
  });

  it("dispatches plan, step_started, screenshot, step_completed, and completed events", async () => {
    const { result } = renderHook(() =>
      useRunStream({ runId: "run-stream-test", autoConnect: true }),
    );

    const es = MockEventSource.instances[0];

    // 1. Emit plan
    act(() => {
      es.emit("plan", {
        steps: [
          { seq: 1, instruction_text: "Navigate to repository" },
          { seq: 2, instruction_text: "Click create issue" },
        ],
        target_url: "https://github.com/org/repo",
      });
    });

    expect(result.current.status).toBe("running");
    expect(result.current.steps.length).toBe(2);
    expect(result.current.targetUrl).toBe("https://github.com/org/repo");
    expect(result.current.steps[0].status).toBe("pending");

    // 2. Emit step_started
    act(() => {
      es.emit("step_started", { step_seq: 1 });
    });

    expect(result.current.currentStepSeq).toBe(1);
    expect(result.current.steps[0].status).toBe("running");

    // 3. Emit screenshot
    act(() => {
      es.emit("screenshot", {
        image_url: "https://example.com/shot1.png",
        step_seq: 1,
        timestamp_ms: 1700000000000,
      });
    });

    expect(result.current.latestScreenshot?.imageUrl).toBe("https://example.com/shot1.png");

    // 4. Emit step_completed
    act(() => {
      es.emit("step_completed", { step_seq: 1, duration_ms: 850 });
    });

    expect(result.current.steps[0].status).toBe("completed");
    expect(result.current.steps[0].durationMs).toBe(850);

    // 5. Emit completed
    act(() => {
      es.emit("completed", { workflow_id: "wf-12345" });
    });

    expect(result.current.status).toBe("completed");
    expect(result.current.workflowId).toBe("wf-12345");
  });

  it("handles paused state and dispatches resume with X-Krama: 1", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "resumed" }),
    });
    globalThis.fetch = mockFetch;

    const { result } = renderHook(() =>
      useRunStream({ runId: "run-paused-test", autoConnect: true }),
    );

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit("paused", {
        reason: "destructive_action",
        message: "Confirmation required to proceed",
        step_seq: 2,
        trigger_context: "delete_repo",
      });
    });

    expect(result.current.status).toBe("paused");
    expect(result.current.pausedState?.reason).toBe("destructive_action");
    expect(result.current.pausedState?.stepSeq).toBe(2);

    // Trigger resume mutation
    await act(async () => {
      await result.current.resume();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/runs/run-paused-test/resume"),
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "X-Krama": "1",
        }),
      }),
    );
  });

  it("handles failed state with expected and observed diff data", () => {
    const { result } = renderHook(() =>
      useRunStream({ runId: "run-fail-test", autoConnect: true }),
    );

    const es = MockEventSource.instances[0];

    act(() => {
      es.emit("failed", {
        error: "Selector button#submit not visible",
        step_seq: 3,
        expected: { visible: true },
        observed: { visible: false },
      });
    });

    expect(result.current.status).toBe("failed");
    expect(result.current.failedState?.error).toBe("Selector button#submit not visible");
    expect(result.current.failedState?.stepSeq).toBe(3);
    expect(result.current.failedState?.expected).toEqual({ visible: true });
    expect(result.current.failedState?.observed).toEqual({ visible: false });
  });

  it("cleans up EventSource when unmounted", () => {
    const { unmount } = renderHook(() =>
      useRunStream({ runId: "run-cleanup-test", autoConnect: true }),
    );

    const es = MockEventSource.instances[0];
    expect(es.readyState).toBe(0);

    unmount();
    expect(es.readyState).toBe(2); // CLOSED
  });
});
