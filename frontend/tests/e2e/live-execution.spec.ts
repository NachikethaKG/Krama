import { expect, test } from "@playwright/test";

test.describe("Workflow Live Execution - Happy Path", () => {
  test("replays fixture events and tracks step progression to completion", async ({ page }) => {
    // 1. Navigate to the execution view with accelerated replay speed
    await page.goto("/workflows/default/execution?mock=true&speed=50");

    // 2. Assert header, timer, and progress bar elements are visible
    const header = page.getByTestId("execution-header");
    await expect(header).toBeVisible();

    const elapsedTimer = page.getByTestId("elapsed-timer");
    await expect(elapsedTimer).toBeVisible();

    const progressBar = page.getByTestId("execution-progress-bar");
    await expect(progressBar).toBeVisible();

    // 3. Assert step list displays all 5 planned steps
    const stepList = page.getByTestId("execution-step-list");
    await expect(stepList).toBeVisible();

    const stepItems = page.getByTestId("step-progress-item");
    await expect(stepItems).toHaveCount(5);

    // 4. Wait for full execution stream to complete
    const completionBanner = page.getByTestId("completion-banner");
    await expect(completionBanner).toBeVisible({ timeout: 15000 });
    await expect(completionBanner).toContainText(/Workflow Execution Complete/i);

    // 5. Assert final verified status on status badge and progress bar
    const statusBadge = page.getByTestId("execution-status-badge");
    await expect(statusBadge).toHaveAttribute("data-status", "completed");
    await expect(statusBadge).toContainText(/completed/i);

    const progressPercent = page.getByTestId("progress-percent");
    await expect(progressPercent).toHaveText("100%");

    // 6. Assert all 5 steps have reached verified status with checkmarks
    for (let seq = 1; seq <= 5; seq++) {
      const stepItem = page.locator(`[data-testid="step-progress-item"][data-step-seq="${seq}"]`);
      await expect(stepItem).toHaveAttribute("data-step-status", "verified");
      await expect(stepItem.getByTestId("step-verified-icon")).toBeVisible();
      await expect(stepItem.getByTestId("step-verified-badge")).toBeVisible();
    }
  });

  test("loads direct /execution route and runs execution", async ({ page }) => {
    await page.goto("/execution?mock=true&speed=50");

    await expect(page.getByTestId("execution-header")).toBeVisible();
    await expect(page.getByTestId("execution-step-list")).toBeVisible();

    const completionBanner = page.getByTestId("completion-banner");
    await expect(completionBanner).toBeVisible({ timeout: 15000 });
  });
});

test.describe("Workflow Live Execution - Interruption & Failure Handling", () => {
  test("handles run.paused event with pause banner, reason details, and resume control", async ({
    page,
  }) => {
    // 1. Navigate to paused workflow route
    await page.goto("/workflows/paused/execution?mock=true&speed=50");

    // 2. Wait for pause banner to appear
    const pauseBanner = page.getByTestId("pause-banner");
    await expect(pauseBanner).toBeVisible({ timeout: 10000 });
    await expect(pauseBanner).toHaveAttribute("data-pause-reason", "destructive_action");
    await expect(pauseBanner).toContainText(/Execution Paused at Step 2/i);
    await expect(pauseBanner).toContainText(/Destructive action requires confirmation/i);

    // 3. Verify status badge indicates paused
    const statusBadge = page.getByTestId("execution-status-badge");
    await expect(statusBadge).toHaveAttribute("data-status", "paused");
    await expect(statusBadge).toContainText(/paused/i);

    // 4. Verify step 1 is verified and step 2 is active
    const step1 = page.locator('[data-testid="step-progress-item"][data-step-seq="1"]');
    await expect(step1).toHaveAttribute("data-step-status", "verified");

    const step2 = page.locator('[data-testid="step-progress-item"][data-step-seq="2"]');
    await expect(step2).toHaveAttribute("data-step-status", "started");

    // 5. Test resume action control
    const resumeBtn = page.getByTestId("resume-run-btn");
    await expect(resumeBtn).toBeVisible();
    await resumeBtn.click();

    // After resume, status transitions back to running and pause banner dismisses
    await expect(pauseBanner).not.toBeVisible();
    await expect(statusBadge).toHaveAttribute("data-status", "running");
  });

  test("handles run.failed event with terminal failure banner and step error callout", async ({
    page,
  }) => {
    // 1. Navigate to failed workflow route
    await page.goto("/workflows/failed/execution?mock=true&speed=50");

    // 2. Wait for failure banner to appear
    const failureBanner = page.getByTestId("failure-banner");
    await expect(failureBanner).toBeVisible({ timeout: 10000 });
    await expect(failureBanner).toContainText(/Workflow Execution Failed/i);

    // 3. Verify error code badge and message details
    const errorCode = page.getByTestId("failure-code-badge");
    await expect(errorCode).toHaveText(/validation_error/i);

    const errorMessage = page.getByTestId("failure-message");
    await expect(errorMessage).toContainText(/target URL did not match expected path/i);

    // 4. Verify status badge indicates failed
    const statusBadge = page.getByTestId("execution-status-badge");
    await expect(statusBadge).toHaveAttribute("data-status", "failed");
    await expect(statusBadge).toContainText(/failed/i);

    // 5. Verify step 2 displays failed status and error callout
    const failedStep = page.locator('[data-testid="step-progress-item"][data-step-seq="2"]');
    await expect(failedStep).toHaveAttribute("data-step-status", "failed");
    await expect(failedStep.getByTestId("step-failed-icon")).toBeVisible();
    await expect(failedStep.getByTestId("step-error-callout")).toBeVisible();

    // 6. Test retry action control resets execution
    const retryBtn = page.getByTestId("retry-run-btn");
    await expect(retryBtn).toBeVisible();
    await retryBtn.click();

    // After retry, failure banner dismisses and run transitions
    await expect(failureBanner).not.toBeVisible();
  });
});
