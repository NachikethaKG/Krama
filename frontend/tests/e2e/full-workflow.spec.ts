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
    const customTargetOption = page.getByTestId("target-option-custom");
    if (await customTargetOption.isVisible().catch(() => false)) {
      await customTargetOption.click();
    }
    const targetUrlInput = page.getByTestId("custom-target-url-input");
    const submitBtn = page.getByTestId("submit-task-btn");

    await expect(promptInput).toBeVisible();
    await expect(targetUrlInput).toBeVisible();
    await expect(submitBtn).toBeDisabled();

    // 2. Enter prompt and target URL, then submit
    await promptInput.fill("Create a repository in local Gitea");
    await targetUrlInput.fill("http://localhost:3001");
    await expect(submitBtn).toBeEnabled();

    await submitBtn.click();

    // 3. Verify transition to plan approval screen
    const approvalScreen = page.getByTestId("approval-screen");
    await expect(approvalScreen).toBeVisible({ timeout: 20000 });

    const taskPrompt = page.getByTestId("task-prompt");
    await expect(taskPrompt).toBeVisible();
    await expect(taskPrompt).toContainText(/Create a repository.*in local Gitea/i);

    const targetUrl = page.getByTestId("target-url");
    await expect(targetUrl).toBeVisible();
    await expect(targetUrl).toHaveText("http://localhost:3001");

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
    await expect(completionBanner).toContainText(/Workflow Execution Complete/i);

    const statusBadge = page.getByTestId("execution-status-badge");
    await expect(statusBadge).toHaveAttribute("data-status", "completed");
  });

  test("navigates to /tasks route and initiates task planning", async ({ page }) => {
    await page.goto("/tasks");

    await expect(page.getByTestId("task-input-section")).toBeVisible();
    const promptInput = page.getByTestId("task-prompt-input");
    await promptInput.fill("Create a demo repository");

    const submitBtn = page.getByTestId("submit-task-btn");
    await expect(submitBtn).toBeEnabled({ timeout: 15000 });
    await submitBtn.click();

    await expect(page.getByTestId("approval-screen")).toBeVisible({ timeout: 20000 });
  });

  test("preserves MockApiClient fallback when NEXT_PUBLIC_API_MODE is unset or mock", async ({
    page,
  }) => {
    await page.goto("/approval");

    // In mock mode, fixtures load immediately without requiring live backend
    await expect(page.getByTestId("approval-screen")).toBeVisible();
    await expect(page.getByTestId("step-item")).toHaveCount(5);
  });
});
