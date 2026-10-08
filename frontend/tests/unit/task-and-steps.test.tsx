import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StepList } from "@/components/step-list";
import { TaskHeader } from "@/components/task-header";
import { giteaWorkflowFixture } from "@/lib/fixtures";

describe("TaskHeader", () => {
  it("renders prompt, title, and target URL", () => {
    render(
      <TaskHeader
        title="Create Repository Workflow"
        prompt="Create a demo repo with initialized readme"
        targetUrl="http://localhost:3001"
        targetApp="gitea"
        status="draft"
      />
    );

    expect(screen.getByTestId("task-header")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Create Repository Workflow" })).toBeInTheDocument();
    expect(screen.getByTestId("task-prompt")).toHaveTextContent("Create a demo repo with initialized readme");
    expect(screen.getByTestId("target-url")).toHaveTextContent("http://localhost:3001");
    expect(screen.getByTestId("workflow-status-badge")).toHaveTextContent("draft");
  });

  it("handles missing target URL gracefully", () => {
    render(
      <TaskHeader
        prompt="Perform actions without url"
        targetUrl={null}
      />
    );

    expect(screen.getByTestId("target-url")).toHaveTextContent("No target URL configured");
  });
});

describe("StepList", () => {
  it("renders all workflow steps with instructions and risk badges", () => {
    render(<StepList steps={giteaWorkflowFixture.steps} />);

    expect(screen.getByTestId("step-list")).toBeInTheDocument();
    const items = screen.getAllByTestId("step-item");
    expect(items).toHaveLength(5);

    const firstInstruction = items[0].querySelector('[data-testid="step-instruction"]');
    expect(firstInstruction).toHaveTextContent("Open the + menu at the top right.");

    const badges = screen.getAllByTestId("risk-badge");
    expect(badges).toHaveLength(5);
  });

  it("renders empty state when steps array is empty", () => {
    render(<StepList steps={[]} />);
    expect(screen.getByTestId("step-list-empty")).toBeInTheDocument();
    expect(screen.getByText("No steps proposed in this workflow plan.")).toBeInTheDocument();
  });

  it("allows inline instruction editing when isEditing is true", () => {
    const handleInstructionChange = vi.fn();
    render(
      <StepList
        steps={giteaWorkflowFixture.steps}
        isEditing={true}
        onInstructionChange={handleInstructionChange}
      />
    );

    const firstInput = screen.getByTestId("step-input-1");
    expect(firstInput).toBeInTheDocument();
    expect(firstInput).toHaveValue("Open the + menu at the top right.");

    fireEvent.change(firstInput, { target: { value: "Updated step 1 instruction" } });
    expect(handleInstructionChange).toHaveBeenCalledWith(1, "Updated step 1 instruction");
  });
});
