import { expect, test } from "@playwright/test";

test.describe("Workflow Approval Screen - Happy Path", () => {
  test("loads workflow plan and completes approval flow", async ({ page }) => {
    // 1. Navigate to the dynamic approval route
    await page.goto("/workflows/default/approval");

    // 2. Verify Task Header displaying prompt and target URL
    const taskHeader = page.getByTestId("task-header");
    await expect(taskHeader).toBeVisible();

    const taskPrompt = page.getByTestId("task-prompt");
    await expect(taskPrompt).toBeVisible();
    await expect(taskPrompt).toContainText(/Create a repository.*in local Gitea/i);

    const targetUrl = page.getByTestId("target-url");
    await expect(targetUrl).toBeVisible();
    await expect(targetUrl).toHaveText("http://localhost:3001");

    // 3. Verify Step List with instructions and risk badges
    const stepList = page.getByTestId("step-list");
    await expect(stepList).toBeVisible();

    const stepItems = page.getByTestId("step-item");
    await expect(stepItems).toHaveCount(5);

    // Verify first step instruction text
    const firstStepInstruction = stepItems.first().getByTestId("step-instruction");
    await expect(firstStepInstruction).toHaveText("Open the + menu at the top right.");

    // Verify risk badges are present
    const riskBadges = page.getByTestId("risk-badge");
    await expect(riskBadges).toHaveCount(5);

    // 4. Verify Approval Action controls
    const approveBtn = page.getByTestId("approve-btn");
    const rejectBtn = page.getByTestId("reject-btn");
    const editBtn = page.getByTestId("edit-btn");

    await expect(approveBtn).toBeVisible();
    await expect(rejectBtn).toBeVisible();
    await expect(editBtn).toBeVisible();

    // 5. User clicks "Approve & Execute"
    await approveBtn.click();

    // 6. Assert state transitions to approved
    const successBanner = page.getByTestId("approval-success-banner");
    await expect(successBanner).toBeVisible();
    await expect(successBanner).toContainText(/Plan approved!.*transitioning to execution/i);

    const statusBadge = page.getByTestId("workflow-status-badge");
    await expect(statusBadge).toHaveText(/approved/i);

    // Assert action buttons are now disabled
    await expect(approveBtn).toBeDisabled();
    await expect(rejectBtn).toBeDisabled();
    await expect(editBtn).toBeDisabled();
  });

  test("loads default approval route and verifies direct navigation", async ({ page }) => {
    await page.goto("/approval");

    await expect(page.getByTestId("task-header")).toBeVisible();
    await expect(page.getByTestId("step-list")).toBeVisible();
    await expect(page.getByTestId("approve-btn")).toBeVisible();
  });
});

test.describe("Workflow Approval Screen - Rejection & Edge Cases", () => {
  test("completes rejection flow and transitions to rejected state", async ({ page }) => {
    await page.goto("/workflows/default/approval");

    const rejectBtn = page.getByTestId("reject-btn");
    const approveBtn = page.getByTestId("approve-btn");
    const editBtn = page.getByTestId("edit-btn");

    await expect(rejectBtn).toBeVisible();
    await rejectBtn.click();

    // Verify rejection banner and state transition
    const rejectedBanner = page.getByTestId("approval-rejected-banner");
    await expect(rejectedBanner).toBeVisible();
    await expect(rejectedBanner).toContainText(/Workflow plan rejected.*Execution canceled/i);

    const statusBadge = page.getByTestId("workflow-status-badge");
    await expect(statusBadge).toHaveText(/rejected/i);

    // Verify all buttons disabled post-rejection
    await expect(approveBtn).toBeDisabled();
    await expect(rejectBtn).toBeDisabled();
    await expect(editBtn).toBeDisabled();
  });

  test("allows inline editing of step instructions", async ({ page }) => {
    await page.goto("/workflows/default/approval");

    const editBtn = page.getByTestId("edit-btn");
    await editBtn.click();
    await expect(editBtn).toHaveText("Done Editing");

    // Edit step 1 input
    const input1 = page.getByTestId("step-input-1");
    await expect(input1).toBeVisible();
    await input1.fill("Custom edited instruction: Click menu");

    // Toggle Done Editing
    await editBtn.click();
    await expect(editBtn).toHaveText("Edit Plan");

    // Assert updated text is rendered
    await expect(page.getByText("Custom edited instruction: Click menu")).toBeVisible();
  });

  test("displays error screen when workflow ID does not exist", async ({ page }) => {
    await page.goto("/workflows/non-existent-uuid/approval");

    const errorView = page.getByTestId("approval-screen-error");
    await expect(errorView).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workflow Not Found" })).toBeVisible();
  });
});
