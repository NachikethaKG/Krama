import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn(), back: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

import { ApprovalScreen } from "@/components/approval-screen";
import { ApiRequestError, MockApiClient } from "@/lib/api";
import { giteaWorkflowFixture } from "@/lib/fixtures";

async function renderLoaded(client = new MockApiClient()) {
  render(<ApprovalScreen planId="default" client={client} />);
  await waitFor(() => expect(screen.getByTestId("approval-screen")).toBeInTheDocument());
  return client;
}

describe("ApprovalScreen", () => {
  it("renders the task (prompt, target) from Plan → Task and the plan's steps", async () => {
    await renderLoaded();
    expect(screen.getByTestId("task-prompt")).toHaveTextContent(/Create a repository.*in local Gitea/i);
    expect(screen.getByTestId("target-url")).toHaveTextContent("http://localhost:3001");
    expect(screen.getAllByTestId("step-item")).toHaveLength(5);
    expect(screen.getByTestId("workflow-status-badge")).toHaveTextContent("proposed");
  });

  it("approves the revision on screen and navigates to the RUN's live view", async () => {
    push.mockClear();
    const client = new MockApiClient();
    const approve = vi.spyOn(client, "approvePlan");
    await renderLoaded(client);

    fireEvent.click(screen.getByTestId("approve-btn"));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/runs/mock-run-id/live"));
    expect(approve).toHaveBeenCalledWith("default", 1);
    expect(screen.getByTestId("workflow-status-badge")).toHaveTextContent("approved");
  });

  it("rejects through POST /plans/{id}/reject", async () => {
    const client = new MockApiClient();
    const reject = vi.spyOn(client, "rejectPlan");
    await renderLoaded(client);

    fireEvent.click(screen.getByTestId("reject-btn"));

    await waitFor(() => expect(screen.getByTestId("approval-rejected-banner")).toBeInTheDocument());
    expect(reject).toHaveBeenCalledWith("default");
    expect(screen.getByTestId("workflow-status-badge")).toHaveTextContent("rejected");
  });

  it("saves edits with PATCH (revision bump) before approving", async () => {
    const client = new MockApiClient();
    const update = vi.spyOn(client, "updatePlan");
    const approve = vi.spyOn(client, "approvePlan");
    await renderLoaded(client);

    const editBtn = screen.getByTestId("edit-btn");
    fireEvent.click(editBtn);
    expect(screen.getByTestId("approve-btn")).toBeDisabled();
    fireEvent.change(screen.getByTestId("step-input-1"), { target: { value: "New edited instruction text" } });
    fireEvent.click(editBtn);

    await waitFor(() => expect(editBtn).toHaveTextContent("Edit steps"));
    expect(update).toHaveBeenCalledWith("default", 1, expect.any(Array));
    expect(screen.getByText("New edited instruction text")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("approve-btn"));
    await waitFor(() => expect(approve).toHaveBeenCalledWith("default", 2));
  });

  it("reorders and deletes steps in edit mode", async () => {
    await renderLoaded();
    fireEvent.click(screen.getByTestId("edit-btn"));

    fireEvent.click(screen.getByTestId("move-step-down-1"));
    expect((screen.getByTestId("step-input-1") as HTMLInputElement).value).toBe(
      giteaWorkflowFixture.steps[1].instruction_text,
    );
    fireEvent.click(screen.getByTestId("move-step-up-2"));
    expect((screen.getByTestId("step-input-1") as HTMLInputElement).value).toBe(
      giteaWorkflowFixture.steps[0].instruction_text,
    );

    fireEvent.click(screen.getByTestId("delete-step-2"));
    expect(screen.getAllByTestId("step-item")).toHaveLength(4);
  });

  it("shows the conflict banner on a 409 conflict and reloads the latest plan", async () => {
    const client = new MockApiClient();
    client.updatePlan = async () => {
      throw new ApiRequestError("Plan revision 1 is stale; the current one is 2", 409, {
        code: "conflict",
        message: "Plan revision 1 is stale; the current one is 2",
      });
    };
    await renderLoaded(client);

    fireEvent.click(screen.getByTestId("edit-btn"));
    fireEvent.click(screen.getByTestId("edit-btn"));

    await waitFor(() => expect(screen.getByTestId("plan-conflict-banner")).toBeInTheDocument());
    expect(screen.getByText(/Plan revision 1 is stale/i)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("reload-plan-btn"));
    await waitFor(() => expect(screen.queryByTestId("plan-conflict-banner")).not.toBeInTheDocument());
  });

  it("shows plan_not_editable as an error, not as a conflict", async () => {
    const client = new MockApiClient();
    client.approvePlan = async () => {
      throw new ApiRequestError("Plan is already approved", 409, {
        code: "plan_not_editable",
        message: "Plan is already approved",
      });
    };
    await renderLoaded(client);
    fireEvent.click(screen.getByTestId("approve-btn"));
    await waitFor(() => expect(screen.getByTestId("approval-error-banner")).toHaveTextContent(/already approved/i));
    expect(screen.queryByTestId("plan-conflict-banner")).not.toBeInTheDocument();
  });

  it("shows the error view when the plan does not exist", async () => {
    render(<ApprovalScreen planId="unknown-404-id" client={new MockApiClient()} />);
    await waitFor(() => expect(screen.getByTestId("approval-screen-error")).toBeInTheDocument());
    expect(screen.getByText("Plan Not Found")).toBeInTheDocument();
  });
});
