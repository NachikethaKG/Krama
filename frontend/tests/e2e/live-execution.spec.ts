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
