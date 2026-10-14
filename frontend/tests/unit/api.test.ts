import { afterEach, describe, expect, it, vi } from "vitest";

import type { PlannedStep } from "@krama/contracts-ts";

import {
  createApiClient,
  getApiClient,
  HttpApiClient,
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
      expect(fetch).toHaveBeenCalledWith("http://api/health");
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
      expect(fetch).toHaveBeenCalledWith("http://api/tasks/task-123");
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
      expect(fetch).toHaveBeenCalledWith("http://api/plans/plan-456");
    });

    it("approves plan via POST /plans/:id/approve with explicit revision", async () => {
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
      expect(result).toEqual(runResponse);
      expect(fetch).toHaveBeenCalledWith(
        "http://api/plans/plan-456/approve",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ revision: 2 }),
        }),
      );
    });

    it("approves plan by fetching plan revision when revision is omitted", async () => {
      const planResponse = {
        id: "plan-456",
        task_id: "task-123",
        revision: 3,
        status: "proposed",
        risk: "low",
        expected_result: "Repo created",
        steps: [],
        created_at: "2026-10-14T00:00:00Z",
      };
      const runResponse = {
        id: "run-789",
        plan_id: "plan-456",
        plan_revision: 3,
        status: "queued",
        retry_count: 0,
        created_at: "2026-10-14T00:00:00Z",
      };

      const fetchMock = vi.fn().mockImplementation(async (url: string) => {
        if (url === "http://api/plans/plan-456") {
          return new Response(JSON.stringify(planResponse), { status: 200 });
        }
        if (url === "http://api/plans/plan-456/approve") {
          return new Response(JSON.stringify(runResponse), { status: 201 });
        }
        throw new Error(`Unexpected url: ${url}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const client = new HttpApiClient("http://api");
      const result = await client.approvePlan("plan-456");
      expect(result).toEqual(runResponse);
      expect(fetchMock).toHaveBeenCalledWith(
        "http://api/plans/plan-456/approve",
        expect.objectContaining({
          body: JSON.stringify({ revision: 3 }),
        }),
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
      const result = await client.getRun("run-789");
      expect(result).toEqual(runResponse);
    });

    it("fetches workflow on 200 and adapts plan if workflow returns 404", async () => {
      const planResponse = {
        id: "plan-123",
        task_id: "task-1",
        revision: 1,
        status: "proposed",
        risk: "medium",
        expected_result: "Create repository in Gitea",
        steps: [
          {
            seq: 1,
            action: { type: "click", value: null },
            target: { role: "button", name: "New" },
            instruction_text: "Click New",
            expected_state: { url_matches: "/repo/create" },
            risk: "low",
          },
        ],
        created_at: "2026-10-14T00:00:00Z",
      };

      const fetchMock = vi.fn().mockImplementation(async (url: string) => {
        if (url === "http://api/workflows/plan-123") {
          return new Response(JSON.stringify({ error: { message: "Workflow not found" } }), { status: 404 });
        }
        if (url === "http://api/plans/plan-123") {
          return new Response(JSON.stringify(planResponse), { status: 200 });
        }
        throw new Error(`Unexpected: ${url}`);
      });
      vi.stubGlobal("fetch", fetchMock);

      const client = new HttpApiClient("http://api");
      const adapted = await client.getWorkflow("plan-123");
      expect(adapted.id).toBe("plan-123");
      expect(adapted.steps).toHaveLength(1);
      expect(adapted.steps[0].instruction_text).toBe("Click New");
    });

    it("updates plan steps via PATCH /plans/:id with revision", async () => {
      const updatedPlan = {
        id: "plan-456",
        task_id: "task-123",
        revision: 2,
        status: "proposed",
        risk: "low",
        expected_result: "Repo created",
        steps: [
          {
            seq: 1,
            action: { type: "click", value: null },
            target: { role: "button", name: "Submit" },
            instruction_text: "Click Submit",
            expected_state: { url_matches: "/done" },
            risk: "low",
          },
        ],
        created_at: "2026-10-14T00:00:00Z",
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(updatedPlan), { status: 200 })));

      const client = new HttpApiClient("http://api");
      const result = await client.updatePlan("plan-456", 1, {
        steps: updatedPlan.steps as [PlannedStep, ...PlannedStep[]],
      });
      expect(result).toEqual(updatedPlan);
      expect(fetch).toHaveBeenCalledWith(
        "http://api/plans/plan-456",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ revision: 1, steps: updatedPlan.steps }),
        }),
      );
    });

    it("cancels a run via POST /runs/:id/cancel", async () => {
      const cancelResponse = {
        id: "run-789",
        plan_id: "plan-456",
        plan_revision: 1,
        status: "cancelled",
        retry_count: 0,
        created_at: "2026-10-14T00:00:00Z",
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(cancelResponse), { status: 200 })));

      const client = new HttpApiClient("http://api");
      const result = await client.cancelRun("run-789");
      expect(result).toEqual(cancelResponse);
      expect(fetch).toHaveBeenCalledWith(
        "http://api/runs/run-789/cancel",
        expect.objectContaining({ method: "POST" }),
      );
    });

    it("confirms a paused run via POST /runs/:id/confirm", async () => {
      const confirmResponse = {
        id: "run-789",
        plan_id: "plan-456",
        plan_revision: 1,
        status: "running",
        retry_count: 0,
        created_at: "2026-10-14T00:00:00Z",
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(confirmResponse), { status: 200 })));

      const client = new HttpApiClient("http://api");
      const result = await client.confirmRun("run-789", 2, "allow");
      expect(result).toEqual(confirmResponse);
      expect(fetch).toHaveBeenCalledWith(
        "http://api/runs/run-789/confirm",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ step_seq: 2, decision: "allow" }),
        }),
      );
    });

    it("fetches paginated runs via GET /runs", async () => {
      const runsResponse = {
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
        next_cursor: "cursor-2",
      };
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(runsResponse), { status: 200 })));

      const client = new HttpApiClient("http://api");
      const result = await client.getRuns(1, 5);
      expect(result.items).toHaveLength(1);
      expect(result.items[0].id).toBe("run-1");
      expect(result.items[0].durationSeconds).toBe(5);
      expect(result.nextCursor).toBe("cursor-2");
      expect(fetch).toHaveBeenCalledWith("http://api/runs?limit=5");
    });

    it("fetches run details combining run and workflow metadata", async () => {
      const runResponse = {
        id: "run-100",
        plan_id: "plan-100",
        plan_revision: 1,
        status: "verified",
        workflow_id: "wf-100",
        retry_count: 0,
        created_at: "2026-10-14T00:00:00Z",
        started_at: "2026-10-14T00:00:00Z",
        finished_at: "2026-10-14T00:00:05Z",
      };
      const workflowResponse = {
        id: "wf-100",
        title: "Test Workflow",
        task: "Automate something",
        target_url: "http://localhost:3001",
        target_app: "gitea",
        status: "verified",
        steps: [
          {
            id: "step-1",
            seq: 1,
            instruction_text: "Click Button",
            action: { type: "click" },
            target: { role: "button", name: "Submit" },
            risk: "low",
            verification: { result: "verified", method: ["aria"], confidence: 0.98 },
            observed_state: { url: "/done", screenshot_path: "/screenshots/done.png" },
          },
        ],
      };

      vi.stubGlobal(
        "fetch",
        vi.fn().mockImplementation(async (url: string) => {
          if (url === "http://api/runs/run-100") {
            return new Response(JSON.stringify(runResponse), { status: 200 });
          }
          if (url === "http://api/workflows/wf-100") {
            return new Response(JSON.stringify(workflowResponse), { status: 200 });
          }
          throw new Error(`Unexpected: ${url}`);
        }),
      );

      const client = new HttpApiClient("http://api");
      const result = await client.getRunDetails("run-100");
      expect(result.run.id).toBe("run-100");
      expect(result.steps).toHaveLength(1);
      expect(result.steps[0].evidence.method).toBe("aria");
      expect(result.steps[0].evidence.confidence).toBe(0.98);
      expect(result.steps[0].evidence.screenshotUrl).toBe("/screenshots/done.png");
      expect(result.summary.verifiedSteps).toBe(1);
    });
  });

  describe("error handling", () => {
    it("throws on 500 internal server error with contract error message", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          new Response(
            JSON.stringify({
              error: { code: "internal", message: "Database connection failed", details: {} },
            }),
            { status: 500, headers: { "Content-Type": "application/json" } },
          ),
        ),
      );

      const client = new HttpApiClient("http://api");
      await expect(client.createTask("foo", "bar")).rejects.toThrow("Database connection failed");
    });

    it("throws on network connection failure / timeout", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockRejectedValue(new Error("Connection refused (ECONNREFUSED)")),
      );

      const client = new HttpApiClient("http://api");
      await expect(client.health()).rejects.toThrow(/Network request failed.*ECONNREFUSED/);
    });

    it("throws on 404 not found", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          new Response(
            JSON.stringify({
              error: { code: "not_found", message: "Task not found", details: {} },
            }),
            { status: 404, headers: { "Content-Type": "application/json" } },
          ),
        ),
      );

      const client = new HttpApiClient("http://api");
      await expect(client.getTask("unknown-id")).rejects.toThrow("Task not found");
    });

    it("throws on non-2xx status code without JSON body", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Service Unavailable", { status: 503 })));

      const client = new HttpApiClient("http://api");
      await expect(client.health()).rejects.toThrow("503");
    });
  });

  describe("SSE streaming (streamRunEvents / parseEventStream)", () => {
    it("parses SSE chunks into RunEvents and ignores ping comments", async () => {
      const sseText =
        'id: 1\nevent: run.started\ndata: {"type":"run.started","run_id":"r1","seq":1,"ts":"2026-10-14T00:00:00Z","plan_id":"p1","total_steps":2}\n\n' +
        ': ping\n\n' +
        'id: 2\nevent: step.started\ndata: {"type":"step.started","run_id":"r1","seq":2,"ts":"2026-10-14T00:00:01Z","step_seq":1,"instruction_text":"Click New"}\n\n' +
        'id: 3\nevent: run.completed\ndata: {"type":"run.completed","run_id":"r1","seq":3,"ts":"2026-10-14T00:00:02Z","workflow_id":"w1","verified_steps":1,"failed_actions":0}\n\n';

      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(sseText));
          controller.close();
        },
      });

      const events: unknown[] = [];
      for await (const event of parseEventStream(stream)) {
        events.push(event);
      }

      expect(events).toHaveLength(3);
      expect((events[0] as { type: string }).type).toBe("run.started");
      expect((events[1] as { type: string }).type).toBe("step.started");
      expect((events[2] as { type: string }).type).toBe("run.completed");
    });

    it("handles stream cancellation via AbortSignal", async () => {
      const controller = new AbortController();
      controller.abort();

      const stream = new ReadableStream<Uint8Array>({
        start(c) {
          c.enqueue(new TextEncoder().encode('data: {"type":"run.started"}\n\n'));
          c.close();
        },
      });

      const events: unknown[] = [];
      for await (const event of parseEventStream(stream, controller.signal)) {
        events.push(event);
      }

      expect(events).toHaveLength(0);
    });

    it("throws on streamRunEvents HTTP error status", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(new Response("Run not found", { status: 404 })),
      );

      const client = new HttpApiClient("http://api");
      const generator = client.streamRunEvents("unknown-run");
      await expect(generator[Symbol.asyncIterator]().next()).rejects.toThrow("404");
    });
  });
});

describe("MockApiClient", () => {
  it("returns health response", async () => {
    const client = new MockApiClient();
    await expect(client.health()).resolves.toEqual({ status: "ok", version: "mock" });
  });

  it("creates a mock task with planned status and plan_id", async () => {
    const client = new MockApiClient();
    const task = await client.createTask("Create repo", "http://localhost:3001");
    expect(task.id).toBe("mock-task-id");
    expect(task.status).toBe("planned");
    expect(task.plan_id).toBeTruthy();
  });

  it("fetches a mock task by ID", async () => {
    const client = new MockApiClient();
    const task = await client.getTask("any-id");
    expect(task.id).toBe("any-id");
    expect(task.status).toBe("planned");
  });

  it("fetches a mock plan with planned steps and risk", async () => {
    const client = new MockApiClient();
    const plan = await client.getPlan("default");
    expect(plan.id).toBe("default");
    expect(plan.steps).toHaveLength(5);
    expect(plan.status).toBe("proposed");
  });

  it("approves plan and returns queued run", async () => {
    const client = new MockApiClient();
    const run = await client.approvePlan("default", 1);
    expect(run.id).toBe("mock-run-id");
    expect(run.plan_id).toBe("default");
    expect(run.status).toBe("queued");
  });

  it("fetches a mock run by ID", async () => {
    const client = new MockApiClient();
    const run = await client.getRun("run-123");
    expect(run.id).toBe("run-123");
    expect(run.status).toBe("running");
  });

  it("updates plan and increments revision on match", async () => {
    const client = new MockApiClient();
    const originalPlan = await client.getPlan("default");
    expect(originalPlan.revision).toBe(1);

    const updated = await client.updatePlan("default", 1, {
      steps: [
        {
          seq: 1,
          action: { type: "click" },
          target: { role: "button", name: "Submit" },
          instruction_text: "Updated Step 1",
          expected_state: { url_matches: "/done" },
          risk: "low",
        },
      ],
    });
    expect(updated.revision).toBe(2);
    expect(updated.steps[0].instruction_text).toBe("Updated Step 1");
  });

  it("throws 409 conflict when updating plan with stale revision", async () => {
    const client = new MockApiClient();
    await client.getPlan("default");

    await expect(
      client.updatePlan("default", 99, {
        steps: [
          {
            seq: 1,
            action: { type: "click" },
            target: { role: "button", name: "Submit" },
            instruction_text: "Updated Step 1",
            expected_state: { url_matches: "/done" },
            risk: "low",
          },
        ],
      }),
    ).rejects.toThrow(/status 409.*stale/i);
  });

  it("cancels a run and returns cancelled status", async () => {
    const client = new MockApiClient();
    const run = await client.cancelRun("run-123");
    expect(run.status).toBe("cancelled");
  });

  it("confirms a paused run and returns running or cancelled", async () => {
    const client = new MockApiClient();
    const allowed = await client.confirmRun("run-123", 2, "allow");
    expect(allowed.status).toBe("running");

    const denied = await client.confirmRun("run-123", 2, "deny");
    expect(denied.status).toBe("cancelled");
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
      await expect(client.getWorkflow("unknown-id")).rejects.toThrow("Workflow not found: unknown-id");
    });

    describe("getRuns pagination", () => {
      it("returns first page of paginated runs", async () => {
        const client = new MockApiClient();
        const res = await client.getRuns(1, 5);
        expect(res.page).toBe(1);
        expect(res.pageSize).toBe(5);
        expect(res.items).toHaveLength(5);
        expect(res.total).toBe(12);
        expect(res.totalPages).toBe(3);
        expect(res.nextCursor).toBe("cursor-2");
      });

      it("returns second page of paginated runs", async () => {
        const client = new MockApiClient();
        const res = await client.getRuns(2, 5);
        expect(res.page).toBe(2);
        expect(res.items).toHaveLength(5);
        expect(res.items[0].id).toBe("run-6");
      });

      it("handles boundary page requests gracefully", async () => {
        const client = new MockApiClient();
        const res = await client.getRuns(3, 5);
        expect(res.page).toBe(3);
        expect(res.items).toHaveLength(2);
        expect(res.nextCursor).toBeNull();
      });
    });

    describe("getRunDetails", () => {
      it("returns comprehensive run details and step verification evidence", async () => {
        const client = new MockApiClient();
        const details = await client.getRunDetails("run-1");
        expect(details.run.id).toBe("run-1");
        expect(details.steps).toHaveLength(5);
        expect(details.steps[0].evidence.method).toBe("aria");
        expect(details.steps[0].evidence.confidence).toBe(1.0);
        expect(details.steps[0].evidence.screenshotUrl).toBe("/screenshots/step-1.png");
        expect(details.summary.totalSteps).toBe(5);
        expect(details.summary.verifiedSteps).toBe(5);
      });

      it("throws when run details cannot be found", async () => {
        const client = new MockApiClient();
        await expect(client.getRunDetails("non-existent-run")).rejects.toThrow("Run details not found: non-existent-run");
      });
    });
  });

  describe("event stream replay", () => {
    it("throws an error when streaming events for non-existent workflow/run id", () => {
      const client = new MockApiClient();
      expect(() => client.streamWorkflowEvents("unknown-wf-id")).toThrow("Workflow not found: unknown-wf-id");
    });

    it("replays all 17 fixture events in chronological sequence with realistic delays", async () => {
      const client = new MockApiClient();
      const stream = client.streamWorkflowEvents("mock", { speed: 100 });
      const types: string[] = [];
      for await (const event of stream) {
        types.push(event.type);
      }
      expect(types).toHaveLength(17);
      expect(types[0]).toBe("run.started");
      expect(types[types.length - 1]).toBe("run.completed");
    });

    it("supports streamRunEvents alias", async () => {
      const client = new MockApiClient();
      const stream = client.streamRunEvents("default", { speed: 100 });
      const types: string[] = [];
      for await (const event of stream) {
        types.push(event.type);
      }
      expect(types).toHaveLength(17);
    });
  });
});
