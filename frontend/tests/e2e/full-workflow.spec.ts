import { expect, test } from "@playwright/test";

// Mock-mode UI flow (playwright.config.ts forces NEXT_PUBLIC_API_MODE=mock). The real-backend flow is
// tests/e2e-real/real-flow.spec.ts (`pnpm e2e:real`, opt-in with KRAMA_E2E_REAL=1).
test.describe("Mock-mode Workflow E2E: Prompt → Plan → Approve → Live Execution", () => {
  test("completes end-to-end task creation, plan review, approval, and live execution", async ({
    page,
  }) => {
    // 1. Navigate to task input page (home page)
    await page.goto("/");

    await expect(page.getByTestId("task-input-section")).toBeVisible();

    const promptInput = page.getByTestId("task-prompt-input");
    const submitBtn = page.getByTestId("submit-task-btn");

    await expect(promptInput).toBeVisible();
    await expect(submitBtn).toBeDisabled();

    // 2. Enter the prompt: the website comes from it (#318), no target to pick
    await promptInput.fill("Create a repository on GitHub");
    await expect(page.getByTestId("detected-site")).toHaveText(/GitHub/);
    await expect(submitBtn).toBeEnabled();

    await submitBtn.click();

    // 3. Verify transition to plan approval screen
    const approvalScreen = page.getByTestId("approval-screen");
    await expect(approvalScreen).toBeVisible({ timeout: 20000 });

    const taskPrompt = page.getByTestId("task-prompt");
    await expect(taskPrompt).toBeVisible();
    await expect(taskPrompt).toContainText(/Create a repository/i); // the mock plan is a fixture

    const targetUrl = page.getByTestId("target-url");
    await expect(targetUrl).toBeVisible();

    // Verify generated plan with step list and risk badges
    const stepList = page.getByTestId("step-list");
    await expect(stepList).toBeVisible();

    const stepItems = page.getByTestId("step-item");
    await expect(stepItems).toHaveCount(5);

    const riskBadges = page.getByTestId("risk-badge");
    await expect(riskBadges).toHaveCount(5);

    // 4. Click Approve & Execute
    const approveBtn = page.getByTestId("approve-btn");
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();

    // Approve returns the Run; the live view is keyed by its id
    await expect(page).toHaveURL(/\/runs\/mock-run-id\/live$/, { timeout: 15000 });

    // 5. Verify transition to live execution view showing steps executing live
    const liveExecutionView = page.getByTestId("live-execution-view");
    await expect(liveExecutionView).toBeVisible({ timeout: 15000 });

    const executionHeader = page.getByTestId("execution-header");
    await expect(executionHeader).toBeVisible();

    const executionStepList = page.getByTestId("execution-step-list");
    await expect(executionStepList).toBeVisible();

    const executionStepItems = page.getByTestId("step-progress-item");
    await expect(executionStepItems).toHaveCount(5);

    // Verify execution completes with verification of steps
    const completionBanner = page.getByTestId("completion-banner");
    await expect(completionBanner).toBeVisible({ timeout: 45000 });
    await expect(completionBanner).toContainText(/Tutorial ready/i);

    const statusBadge = page.getByTestId("execution-status-badge");
    await expect(statusBadge).toHaveAttribute("data-status", "completed");
  });

  test("/tasks goes to the home screen, which asks for the website when the prompt names none", async ({
    page,
  }) => {
    await page.goto("/tasks");
    await expect(page).toHaveURL(/localhost:3000\/$/);

    await expect(page.getByTestId("task-input-section")).toBeVisible();
    const promptInput = page.getByTestId("task-prompt-input");
    await promptInput.fill("Create a demo repository");

    const submitBtn = page.getByTestId("submit-task-btn");
    await expect(page.getByTestId("site-question")).toBeVisible();
    await expect(submitBtn).toBeDisabled();
    await page.getByTestId("site-option-github").click();
    await expect(submitBtn).toBeEnabled({ timeout: 15000 });
    await submitBtn.click();

    await expect(page.getByTestId("approval-screen")).toBeVisible({ timeout: 20000 });
  });

});
