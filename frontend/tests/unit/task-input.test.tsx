import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Task } from "@krama/contracts-ts";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn(), back: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

import { TaskInput } from "@/components/task-input";
import { MockApiClient } from "@/lib/api";

const baseTask: Task = {
  id: "task-1",
  prompt: "Create a repo",
  target_url: "http://localhost:3001",
  status: "planning",
  created_at: "2026-10-14T00:00:00Z",
};

/** A client whose GET /tasks/{id} walks through the given statuses. */
function scriptedClient(sequence: Partial<Task>[]) {
  const client = new MockApiClient();
  let i = 0;
  client.createTask = vi.fn(async () => ({ ...baseTask }));
  client.getTask = vi.fn(async () => ({ ...baseTask, ...sequence[Math.min(i++, sequence.length - 1)] }));
  client.clarifyTask = vi.fn(async () => ({ ...baseTask, status: "planning" as const }));
  return client;
}

function submit(prompt = "Create a repo") {
  fireEvent.change(screen.getByTestId("task-prompt-input"), { target: { value: prompt } });
  fireEvent.click(screen.getByTestId("submit-task-btn"));
}

describe("TaskInput", () => {
  it("renders prompt input, target URL input, and submit button", () => {
    render(<TaskInput />);

    expect(screen.getByTestId("task-prompt-input")).toBeInTheDocument();
    expect(screen.getByTestId("target-url-input")).toBeInTheDocument();
    expect(screen.getByTestId("submit-task-btn")).toBeInTheDocument();
    expect(screen.getByTestId("submit-task-btn")).toHaveTextContent("Generate Plan");
  });

  it("has submit button disabled when prompt is empty", () => {
    render(<TaskInput />);

    const submitBtn = screen.getByTestId("submit-task-btn");
    expect(submitBtn).toBeDisabled();

    const promptInput = screen.getByTestId("task-prompt-input");
    fireEvent.change(promptInput, { target: { value: "Create repository" } });
    expect(submitBtn).not.toBeDisabled();
  });

  it("submits task and invokes onTaskCreated callback", async () => {
    const onTaskCreated = vi.fn();
    const client = new MockApiClient();
    const createTaskSpy = vi.spyOn(client, "createTask");

    render(<TaskInput client={client} onTaskCreated={onTaskCreated} />);

    const promptInput = screen.getByTestId("task-prompt-input");
    const targetUrlInput = screen.getByTestId("target-url-input");
    const submitBtn = screen.getByTestId("submit-task-btn");

    fireEvent.change(promptInput, { target: { value: "Create a repo in local Gitea" } });
    fireEvent.change(targetUrlInput, { target: { value: "http://localhost:3001" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(createTaskSpy).toHaveBeenCalledWith(
        "Create a repo in local Gitea",
        "http://localhost:3001",
      );
    });

    await waitFor(() => expect(onTaskCreated).toHaveBeenCalled(), { timeout: 3000 });
    expect(onTaskCreated).toHaveBeenCalledWith(
      expect.objectContaining({
        prompt: "Create a repo in local Gitea",
        status: "planned",
      }),
    );
  });

  it("polls while planning, shows a visible planning state, then opens the plan", async () => {
    push.mockClear();
    const client = scriptedClient([{ status: "planning" }, { status: "planning" }, { status: "planned", plan_id: "plan-9" }]);
    render(<TaskInput client={client} pollIntervalMs={5} />);
    submit();

    await waitFor(() => expect(screen.getByTestId("task-planning-status")).toBeInTheDocument());
    await waitFor(() => expect(push).toHaveBeenCalledWith("/workflows/plan-9/approval"));
    expect(client.getTask).toHaveBeenCalledTimes(3);
  });

  it("asks the clarification question and re-plans with the answer", async () => {
    push.mockClear();
    const client = scriptedClient([
      { status: "needs_clarification", clarification_question: "What should the repository be called?" },
      { status: "planned", plan_id: "plan-7" },
    ]);
    render(<TaskInput client={client} pollIntervalMs={5} />);
    submit();

    await waitFor(() =>
      expect(screen.getByTestId("task-clarification-question")).toHaveTextContent("What should the repository be called?"),
    );
    fireEvent.change(screen.getByTestId("task-clarify-input"), { target: { value: "demo-repo" } });
    fireEvent.click(screen.getByTestId("task-clarify-submit"));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/workflows/plan-7/approval"));
    expect(client.clarifyTask).toHaveBeenCalledWith("task-1", "demo-repo");
  });

  it("shows the task's error message when planning failed and never invents a plan id", async () => {
    push.mockClear();
    const client = scriptedClient([
      { status: "failed", error: { code: "llm_unavailable", message: "The planner is unavailable" } },
    ]);
    render(<TaskInput client={client} pollIntervalMs={5} />);
    submit();

    await waitFor(() => expect(screen.getByTestId("task-error-banner")).toHaveTextContent("The planner is unavailable"));
    expect(push).not.toHaveBeenCalled();
  });

  it("gives up with a message after the planning timeout", async () => {
    push.mockClear();
    const client = scriptedClient([{ status: "planning" }]);
    render(<TaskInput client={client} pollIntervalMs={5} planningTimeoutMs={30} />);
    submit();

    await waitFor(() => expect(screen.getByTestId("task-error-banner")).toHaveTextContent(/taking longer/i));
    expect(push).not.toHaveBeenCalled();
  });

  it("displays error banner when task creation fails", async () => {
    class FailingClient extends MockApiClient {
      override async createTask(): Promise<never> {
        throw new Error("Backend service unreachable");
      }
    }

    render(<TaskInput client={new FailingClient()} />);

    const promptInput = screen.getByTestId("task-prompt-input");
    const submitBtn = screen.getByTestId("submit-task-btn");

    fireEvent.change(promptInput, { target: { value: "Trigger failure" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByTestId("task-error-banner")).toBeInTheDocument();
    });

    expect(screen.getByTestId("task-error-banner")).toHaveTextContent("Backend service unreachable");
  });
});
