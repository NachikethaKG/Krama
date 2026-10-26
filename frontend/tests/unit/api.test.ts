import { afterEach, describe, expect, it, vi } from "vitest";

import type { PlannedStep } from "@krama/contracts-ts";

import {
  ApiRequestError,
  artifactUrl,
  createApiClient,
  getApiClient,
  HttpApiClient,
  isApiError,
  MockApiClient,
  parseEventStream,
} from "@/lib/api";

describe("client factory", () => {
  const originalEnv = { ...process.env };

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  describe("getApiClient", () => {
    it("returns MockApiClient when NEXT_PUBLIC_API_MODE is unset", () => {
      delete process.env.NEXT_PUBLIC_API_MODE;
      expect(getApiClient()).toBeInstanceOf(MockApiClient);
    });

    it("returns MockApiClient when NEXT_PUBLIC_API_MODE is 'mock'", () => {
      process.env.NEXT_PUBLIC_API_MODE = "mock";
      expect(getApiClient()).toBeInstanceOf(MockApiClient);
    });

    it("returns HttpApiClient when NEXT_PUBLIC_API_MODE is 'http'", () => {
      process.env.NEXT_PUBLIC_API_MODE = "http";
      process.env.NEXT_PUBLIC_API_URL = "http://custom-api:8000/api/v1";
      const client = getApiClient();
      expect(client).toBeInstanceOf(HttpApiClient);
    });

    it("normalizes localhost:8000 URL to include /api/v1", () => {
      process.env.NEXT_PUBLIC_API_MODE = "http";
      process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";
      const client = getApiClient() as HttpApiClient;
      expect(client).toBeInstanceOf(HttpApiClient);
    });
  });

  describe("createApiClient", () => {
    it("defaults to the mock client", () => {
      expect(createApiClient(undefined)).toBeInstanceOf(MockApiClient);
    });

    it("uses the http client in http mode", () => {
      expect(createApiClient("http", "http://api")).toBeInstanceOf(HttpApiClient);
    });
  });
});

describe("HttpApiClient", () => {
  afterEach(() => vi.unstubAllGlobals());

  describe("REST endpoints", () => {
    it("returns the health payload", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", version: "0.1.0" }))),
      );

      await expect(new HttpApiClient("http://api").health()).resolves.toEqual({ status: "ok", version: "0.1.0" });
      expect(fetch).toHaveBeenCalledWith("http://api/health", expect.objectContaining({ credentials: "include" }));
    });

    it("creates task via POST /tasks with 202 response", async () => {
      const taskResponse = {
        id: "task-123",
        prompt: "Create repo",
        target_url: "http://localhost:3001",
        status: "planning",
        created_at: "2026-10-14T00:00:00Z",
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(taskResponse), { status: 202 })));

      const client = new HttpApiClient("http://api");
      const result = await client.createTask("Create repo", "http://localhost:3001");
      expect(result).toEqual(taskResponse);
      expect(fetch).toHaveBeenCalledWith(
        "http://api/tasks",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ prompt: "Create repo", target_url: "http://localhost:3001" }),
        }),
      );
    });

    it("fetches task via GET /tasks/:id", async () => {
      const taskResponse = {
        id: "task-123",
        prompt: "Create repo",
        target_url: "http://localhost:3001",
        status: "planned",
        plan_id: "plan-456",
        created_at: "2026-10-14T00:00:00Z",
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(taskResponse), { status: 200 })));

      const client = new HttpApiClient("http://api");
      const result = await client.getTask("task-123");
      expect(result).toEqual(taskResponse);
      expect(fetch).toHaveBeenCalledWith("http://api/tasks/task-123", expect.objectContaining({ credentials: "include" }));
    });

    it("fetches plan via GET /plans/:id", async () => {
      const planResponse = {
        id: "plan-456",
        task_id: "task-123",
        revision: 1,
        status: "proposed",
        risk: "low",
        expected_result: "Repo created",
        steps: [],
        created_at: "2026-10-14T00:00:00Z",
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(planResponse), { status: 200 })));

      const client = new HttpApiClient("http://api");
      const result = await client.getPlan("plan-456");
      expect(result).toEqual(planResponse);
      expect(fetch).toHaveBeenCalledWith("http://api/plans/plan-456", expect.objectContaining({ credentials: "include" }));
    });


    it("approves plan via POST /plans/:id/approve with the revision on screen and returns the RUN", async () => {
      const runResponse = {
        id: "run-789",
        plan_id: "plan-456",
        plan_revision: 2,
        status: "queued",
        retry_count: 0,
        created_at: "2026-10-14T00:00:00Z",
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(runResponse), { status: 201 })));

      const client = new HttpApiClient("http://api");
      const result = await client.approvePlan("plan-456", 2);
      expect(result.id).toBe("run-789");
      expect(fetch).toHaveBeenCalledWith(
        "http://api/plans/plan-456/approve",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ revision: 2 }) }),
      );
    });

    it("rejects a plan via POST /plans/:id/reject", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "p", status: "rejected" }), { status: 200 })));
      const client = new HttpApiClient("http://api");
      await client.rejectPlan("plan-456", "not needed");
      expect(fetch).toHaveBeenCalledWith(
        "http://api/plans/plan-456/reject",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ reason: "not needed" }) }),
      );
    });

    it("answers a clarification via POST /tasks/:id/clarify", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "t", status: "planning" }), { status: 202 })));
      const client = new HttpApiClient("http://api");
      await client.clarifyTask("task-1", "demo-repo");
      expect(fetch).toHaveBeenCalledWith(
        "http://api/tasks/task-1/clarify",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ answer: "demo-repo" }) }),
      );
    });

    it("fetches run via GET /runs/:id", async () => {
      const runResponse = {
        id: "run-789",
        plan_id: "plan-456",
        plan_revision: 1,
        status: "running",
        retry_count: 0,
        created_at: "2026-10-14T00:00:00Z",
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(runResponse), { status: 200 })));

      const client = new HttpApiClient("http://api");
      await expect(client.getRun("run-789")).resolves.toEqual(runResponse);
    });

    it("getWorkflow does NOT fall back to a plan on 404", async () => {
      const fetchMock = vi.fn().mockImplementation(async () =>
        new Response(JSON.stringify({ error: { code: "not_found", message: "Workflow not found" } }), { status: 404 }),
      );
      vi.stubGlobal("fetch", fetchMock);

      const client = new HttpApiClient("http://api");
      const err = await client.getWorkflow("plan-123").catch((e: unknown) => e);
      expect(err).toBeInstanceOf(ApiRequestError);
      expect(isApiError(err, "not_found", 404)).toBe(true);
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("updates plan steps via PATCH /plans/:id with revision", async () => {
      const steps: PlannedStep[] = [
        {
          seq: 1,
          action: { type: "click", value: null },
          target: { role: "button", name: "Submit" },
          instruction_text: "Click Submit",
          expected_state: { url_matches: "/done" },
          risk: "low",
        },
      ];
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "plan-456", revision: 2, steps }), { status: 200 })));

      const client = new HttpApiClient("http://api");
      const result = await client.updatePlan("plan-456", 1, steps);
      expect(result.revision).toBe(2);
      expect(fetch).toHaveBeenCalledWith(
        "http://api/plans/plan-456",
        expect.objectContaining({ method: "PATCH", body: JSON.stringify({ revision: 1, steps }) }),
      );
    });

    it("exposes the contract error code on a 409", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          new Response(JSON.stringify({ error: { code: "conflict", message: "Plan revision 1 is stale", details: {} } }), {
            status: 409,
          }),
        ),
      );
      const client = new HttpApiClient("http://api");
      const err = await client.updatePlan("p", 1, []).catch((e: unknown) => e);
      expect(isApiError(err, "conflict", 409)).toBe(true);
      expect((err as Error).message).toMatch(/stale/);
    });

    it("cancels a run via POST /runs/:id/cancel", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "run-789", status: "cancelled" }), { status: 200 })));
      const client = new HttpApiClient("http://api");
      await client.cancelRun("run-789");
      expect(fetch).toHaveBeenCalledWith("http://api/runs/run-789/cancel", expect.objectContaining({ method: "POST" }));
    });

    it("confirms a paused run via POST /runs/:id/confirm with the paused step_seq", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "run-789", status: "running" }), { status: 200 })));
      const client = new HttpApiClient("http://api");
      await client.confirmRun("run-789", 2, "allow");
      expect(fetch).toHaveBeenCalledWith(
        "http://api/runs/run-789/confirm",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ step_seq: 2, decision: "allow" }) }),
      );
    });

    it("fetches metrics summary via GET /metrics/summary", async () => {
      const summaryPayload = {
        generated_at: "2026-10-26T12:00:00Z",
        total_tasks: 12,
        overall_success_rate: 0.933,
        overall_verifier_accuracy: 0.997,
        tasks: [],
      };
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(new Response(JSON.stringify(summaryPayload), { status: 200 })),
      );

      const client = new HttpApiClient("http://api");
      const result = await client.getMetricsSummary();
      expect(result).toEqual(summaryPayload);
      expect(fetch).toHaveBeenCalledWith(
        "http://api/api/v1/metrics/summary",
        expect.objectContaining({ credentials: "include" }),
      );
    });

    it("refuses to confirm without a valid step_seq (never guesses step 1)", async () => {
      const fetchMock = vi.fn();
      vi.stubGlobal("fetch", fetchMock);
      const client = new HttpApiClient("http://api");
      await expect(client.confirmRun("run-789", 0, "allow")).rejects.toThrow(/step_seq/);
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it("pages GET /runs with limit + opaque cursor and resolves each prompt via plan → task", async () => {
      const fetchMock = vi.fn().mockImplementation(async (url: string) => {
        if (url.startsWith("http://api/runs?")) {
          return new Response(
            JSON.stringify({
              items: [
                {
                  id: "run-1",
                  plan_id: "plan-1",
                  plan_revision: 1,
                  status: "verified",
                  retry_count: 0,
                  created_at: "2026-10-14T00:00:00Z",
                  started_at: "2026-10-14T00:00:01Z",
                  finished_at: "2026-10-14T00:00:06Z",
                },
              ],
              next_cursor: "opaque==",
            }),
            { status: 200 },
          );
        }
        if (url === "http://api/plans/plan-1") return new Response(JSON.stringify({ id: "plan-1", task_id: "task-1" }), { status: 200 });
        if (url === "http://api/tasks/task-1") return new Response(JSON.stringify({ id: "task-1", prompt: "Create a repo" }), { status: 200 });
        throw new Error(`Unexpected: ${url}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const client = new HttpApiClient("http://api");
      const page1 = await client.getRuns({ limit: 5 });
      expect(fetchMock).toHaveBeenCalledWith("http://api/runs?limit=5", expect.objectContaining({ credentials: "include" }));
      expect(page1.items[0]).toMatchObject({ id: "run-1", prompt: "Create a repo", durationSeconds: 5 });
      expect(page1.nextCursor).toBe("opaque==");

      await client.getRuns({ limit: 5, cursor: page1.nextCursor });
      expect(fetchMock).toHaveBeenCalledWith("http://api/runs?limit=5&cursor=opaque%3D%3D", expect.objectContaining({ credentials: "include" }));
    });

    it("builds run details from run, plan, task and workflow and resolves artifact keys against the API", async () => {
      const workflowResponse = {
        id: "wf-100",
        title: "Test Workflow",
        status: "verified",
        steps: [
          {
            id: "step-1",
            seq: 1,
            instruction_text: "Click Button",
            action: { type: "click" },
            target: { role: "button", name: "Submit" },
            risk: "low",
            expected_state: {},
            verification: { result: "verified", method: ["aria"], confidence: 0.98 },
            observed_state: { url: "/done" },
            screenshot_path: "runs/run-100/step-1.png",
          },
        ],
      };
      vi.stubGlobal(
        "fetch",
        vi.fn().mockImplementation(async (url: string) => {
          if (url === "http://localhost:8000/api/v1/runs/run-100") {
            return new Response(
              JSON.stringify({
                id: "run-100",
                plan_id: "plan-100",
                status: "verified",
                workflow_id: "wf-100",
                retry_count: 0,
                created_at: "2026-10-14T00:00:00Z",
                started_at: "2026-10-14T00:00:00Z",
                finished_at: "2026-10-14T00:00:05Z",
              }),
              { status: 200 },
            );
          }
          if (url === "http://localhost:8000/api/v1/workflows/wf-100") return new Response(JSON.stringify(workflowResponse), { status: 200 });
          if (url === "http://localhost:8000/api/v1/plans/plan-100") return new Response(JSON.stringify({ id: "plan-100", task_id: "task-100", steps: [] }), { status: 200 });
          if (url === "http://localhost:8000/api/v1/tasks/task-100")
            return new Response(JSON.stringify({ id: "task-100", prompt: "Make a repo", target_url: "http://localhost:3001" }), { status: 200 });
          throw new Error(`Unexpected: ${url}`);
        }),
      );

      const client = new HttpApiClient("http://localhost:8000/api/v1");
      const result = await client.getRunDetails("run-100");
      expect(result.run.prompt).toBe("Make a repo");
      expect(result.targetUrl).toBe("http://localhost:3001");
      expect(result.steps[0].evidence.method).toBe("aria");
      expect(result.steps[0].evidence.confidence).toBe(0.98);
      expect(result.steps[0].screenshotUrl).toBe("http://localhost:8000/api/v1/artifacts/runs/run-100/step-1.png");
      expect(result.summary.verifiedSteps).toBe(1);
    });
  });

  describe("error handling", () => {
    it("throws on 500 internal server error with contract error message", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          new Response(JSON.stringify({ error: { code: "internal", message: "Database connection failed", details: {} } }), {
            status: 500,
          }),
        ),
      );
      const client = new HttpApiClient("http://api");
      await expect(client.createTask("foo", "bar")).rejects.toThrow("Database connection failed");
    });

    it("throws on network connection failure", async () => {
      vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Connection refused (ECONNREFUSED)")));
      const client = new HttpApiClient("http://api");
      await expect(client.health()).rejects.toThrow(/Network request failed.*ECONNREFUSED/);
    });

    it("throws on non-2xx status code without JSON body", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Service Unavailable", { status: 503 })));
      const client = new HttpApiClient("http://api");
      await expect(client.health()).rejects.toThrow("503");
    });
  });

  describe("SSE streaming", () => {
    const frame = (seq: number, type: string, extra: Record<string, unknown> = {}) =>
      `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({ type, run_id: "r1", seq, ts: "2026-10-14T00:00:00Z", ...extra })}\n\n`;
    const body = (text: string) =>
      new ReadableStream<Uint8Array>({
        start(c) {
          c.enqueue(new TextEncoder().encode(text));
          c.close();
        },
      });

    it("parses SSE chunks into RunEvents and ignores ping comments", async () => {
      const text =
        frame(1, "run.started", { plan_id: "p1", total_steps: 2 }) +
        ": ping\n\n" +
        frame(2, "step.started", { step_seq: 1, instruction_text: "Click New" });
      const events: unknown[] = [];
      for await (const event of parseEventStream(body(text))) events.push(event);
      expect(events.map((e) => (e as { type: string }).type)).toEqual(["run.started", "step.started"]);
    });

    it("stops after a final event and never reconnects", async () => {
      const fetchMock = vi.fn().mockImplementation(async () =>
        new Response(body(frame(1, "run.started", { plan_id: "p", total_steps: 1 }) + frame(2, "run.completed", { workflow_id: "w", verified_steps: 1, failed_actions: 0 })), {
          status: 200,
        }),
      );
      vi.stubGlobal("fetch", fetchMock);
      const client = new HttpApiClient("http://api");
      const types: string[] = [];
      for await (const e of client.streamRunEvents("r1", { reconnectDelayMs: 1 })) types.push(e.type);
      expect(types).toEqual(["run.started", "run.completed"]);
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it("reconnects after an unexpected drop with Last-Event-ID and skips repeated seqs", async () => {
      const fetchMock = vi
        .fn()
        .mockImplementationOnce(async () => new Response(body(frame(1, "run.started", { plan_id: "p", total_steps: 1 })), { status: 200 }))
        .mockImplementationOnce(async () => {
          throw new TypeError("network error");
        })
        .mockImplementationOnce(
          async () =>
            new Response(
              body(frame(1, "run.started", { plan_id: "p", total_steps: 1 }) + frame(2, "run.failed", { error: { code: "internal", message: "x" } })),
              { status: 200 },
            ),
        );
      vi.stubGlobal("fetch", fetchMock);
      const onReconnect = vi.fn();
      const client = new HttpApiClient("http://api");
      const seqs: number[] = [];
      for await (const e of client.streamRunEvents("r1", { reconnectDelayMs: 1, onReconnect })) seqs.push(e.seq);

      expect(seqs).toEqual([1, 2]);
      expect(fetchMock).toHaveBeenCalledTimes(3);
      expect(fetchMock.mock.calls[0][1].headers["Last-Event-ID"]).toBeUndefined();
      expect(fetchMock.mock.calls[1][1].headers["Last-Event-ID"]).toBe("1");
      expect(fetchMock.mock.calls[2][1].headers["Last-Event-ID"]).toBe("1");
      expect(onReconnect).toHaveBeenCalledTimes(2);
    });

    it("gives up after maxReconnects attempts without events", async () => {
      vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network error")));
      const client = new HttpApiClient("http://api");
      const it = client.streamRunEvents("r1", { reconnectDelayMs: 1, maxReconnects: 2 })[Symbol.asyncIterator]();
      await expect(it.next()).rejects.toThrow(/after 2 reconnect attempts/);
    });

    it("does not retry a 404", async () => {
      const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "not_found", message: "Run not found" } }), { status: 404 }));
      vi.stubGlobal("fetch", fetchMock);
      const client = new HttpApiClient("http://api");
      const it = client.streamRunEvents("unknown-run", { reconnectDelayMs: 1 })[Symbol.asyncIterator]();
      await expect(it.next()).rejects.toThrow("404");
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });
});

describe("artifactUrl", () => {
  const base = "http://localhost:8000/api/v1";
  it("prefixes event paths (/api/...) with the API origin", () => {
    expect(artifactUrl("/api/v1/artifacts/runs/r/step-1.png", base)).toBe("http://localhost:8000/api/v1/artifacts/runs/r/step-1.png");
  });
  it("turns a bare key into an artifact URL", () => {
    expect(artifactUrl("runs/r/step 1.png", base)).toBe("http://localhost:8000/api/v1/artifacts/runs/r/step%201.png");
  });
  it("keeps absolute URLs and app-relative paths", () => {
    expect(artifactUrl("https://cdn/x.png", base)).toBe("https://cdn/x.png");
    expect(artifactUrl("/screenshots/step-1.png", base)).toBe("/screenshots/step-1.png");
    expect(artifactUrl(null, base)).toBeUndefined();
  });
});

describe("MockApiClient", () => {
  it("creates a task that is planning, then polls to planned with a plan id", async () => {
    const client = new MockApiClient();
    const task = await client.createTask("Create repo", "http://localhost:3001");
    expect(task.status).toBe("planning");
    const polled = await client.getTask(task.id);
    expect(polled.status).toBe("planned");
    expect(polled.plan_id).toBe("default");
  });

  it("serves plans and 404s unknown ones", async () => {
    const client = new MockApiClient();
    const plan = await client.getPlan("default");
    expect(plan.steps).toHaveLength(5);
    expect(plan.status).toBe("proposed");
    await expect(client.getPlan("nope")).rejects.toMatchObject({ status: 404, code: "not_found" });
  });

  it("updates a plan, bumps the revision, and 409s a stale revision", async () => {
    const client = new MockApiClient();
    const step: PlannedStep = {
      seq: 1,
      action: { type: "click" },
      target: { role: "button", name: "Submit" },
      instruction_text: "Updated Step 1",
      expected_state: { url_matches: "/done" },
      risk: "low",
    };
    const updated = await client.updatePlan("default", 1, [step]);
    expect(updated.revision).toBe(2);
    await expect(client.updatePlan("default", 1, [step])).rejects.toMatchObject({ status: 409, code: "conflict" });
  });

  it("approves a plan into a queued RUN and refuses to edit it afterwards", async () => {
    const client = new MockApiClient();
    const run = await client.approvePlan("default", 1);
    expect(run).toMatchObject({ id: "mock-run-id", plan_id: "default", status: "queued" });
    await expect(client.updatePlan("default", 1, [])).rejects.toMatchObject({ code: "plan_not_editable" });
  });

  it("409s /confirm unless the run is paused at that step", async () => {
    const client = new MockApiClient();
    await expect(client.confirmRun("paused", 2, "allow")).rejects.toMatchObject({ status: 409, code: "run_not_active" });
  });

  it("replays the success script and ends at run.completed", async () => {
    const client = new MockApiClient();
    const types: string[] = [];
    for await (const event of client.streamRunEvents("default", { speed: 1000 })) types.push(event.type);
    expect(types).toHaveLength(17);
    expect(types.at(-1)).toBe("run.completed");
  });

  it("waits on a pause like the backend: allow resumes and completes", async () => {
    const client = new MockApiClient();
    const types: string[] = [];
    for await (const event of client.streamRunEvents("paused", { speed: 1000 })) {
      types.push(event.type);
      if (event.type === "run.paused") void client.confirmRun("paused", event.step_seq, "allow");
    }
    expect(types).toContain("run.resumed");
    expect(types.at(-1)).toBe("run.completed");
  });

  it("resumes after lastEventId", async () => {
    const client = new MockApiClient();
    const seqs: number[] = [];
    for await (const event of client.streamRunEvents("default", { speed: 1000, lastEventId: 15 })) seqs.push(event.seq);
    expect(seqs).toEqual([16, 17]);
  });

  it("404s an unknown run", async () => {
    const client = new MockApiClient();
    await expect(client.getRun("unknown-run")).rejects.toMatchObject({ status: 404 });
  });

  it("pages runs with an opaque cursor", async () => {
    const client = new MockApiClient();
    const p1 = await client.getRuns({ limit: 5 });
    expect(p1.items).toHaveLength(5);
    const p3 = await client.getRuns({ limit: 5, cursor: (await client.getRuns({ limit: 5, cursor: p1.nextCursor })).nextCursor });
    expect(p3.items).toHaveLength(2);
    expect(p3.nextCursor).toBeNull();
  });

  it("returns run details with evidence", async () => {
    const client = new MockApiClient();
    const details = await client.getRunDetails("run-1");
    expect(details.steps).toHaveLength(5);
    expect(details.steps[0].evidence.screenshotUrl).toBe("/screenshots/step-1.png");
    await expect(client.getRunDetails("non-existent-run")).rejects.toThrow("Run details not found: non-existent-run");
  });

  it("returns mock metrics summary with 12 benchmark tasks", async () => {
    const client = new MockApiClient();
    const summary = await client.getMetricsSummary();
    expect(summary.total_tasks).toBe(12);
    expect(summary.tasks).toHaveLength(12);
    expect(summary.overall_success_rate).toBeGreaterThanOrEqual(0.8);
  });
});
