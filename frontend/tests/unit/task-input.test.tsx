import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TaskInput } from "@/components/task-input";
import { MockApiClient } from "@/lib/api";

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

    expect(onTaskCreated).toHaveBeenCalledWith(
      expect.objectContaining({
        prompt: "Create a repo in local Gitea",
        status: "planned",
      }),
    );
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
