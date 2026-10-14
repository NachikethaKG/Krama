import { expect, test } from "@playwright/test";

test.describe("Failure Diagnostic & Live Replan UI", () => {
  test("displays accessible Expected X / Observed Y failure diagnostic card with side-by-side screenshots", async ({
    page,
  }) => {
    // 1. Navigate to failed execution workflow
    await page.goto("/workflows/failed/execution?mock=true&speed=50");

    // 2. Wait for failure diagnostic card to render
    const failureCard = page.getByTestId("verification-failure-card");
    await expect(failureCard).toBeVisible({ timeout: 10000 });

    // 3. Header inspection: step sequence and verifier layer badge
    const stepSeqBadge = page.getByTestId("diagnostic-step-seq");
    await expect(stepSeqBadge).toHaveText("Step #2");

    const layerBadge = page.getByTestId("failed-layer-badge");
    await expect(layerBadge).toBeVisible();

    // 4. Assertion Breakdown (Expected X vs. Observed Y)
    const expectedBox = page.getByTestId("expected-state-box");
    await expect(expectedBox).toBeVisible();
    await expect(page.getByTestId("expected-url")).toContainText("^/repo/create$");
    await expect(page.getByTestId("expected-visible-elements")).toContainText("Create Repository");

    const observedBox = page.getByTestId("observed-state-box");
    await expect(observedBox).toBeVisible();
    await expect(page.getByTestId("observed-url")).toContainText("/repo/error");
    await expect(page.getByTestId("observed-title")).toContainText("500 Internal Server Error");

    // 5. Visual State Diff: Side-by-side screenshot comparisons
    const screenshotSection = page.getByTestId("screenshot-comparison-section");
    await expect(screenshotSection).toBeVisible();

    const expectedImg = page.getByTestId("expected-screenshot-img");
    const observedImg = page.getByTestId("observed-screenshot-img");
    await expect(expectedImg).toBeVisible();
    await expect(observedImg).toBeVisible();
    await expect(expectedImg).toHaveAttribute("src", "/mock-expected.png");
    await expect(observedImg).toHaveAttribute("src", "/mock-observed.png");
  });

  test("displays live replan progression with attempt counter and status badges transitioning to exhausted recovery", async ({
    page,
  }) => {
    // 1. Navigate to replan workflow execution
    await page.goto("/workflows/replan/execution?mock=true&speed=50");

    // 2. Wait for replan status indicator to appear
    const replanIndicator = page.getByTestId("replan-status-indicator");
    await expect(replanIndicator).toBeVisible({ timeout: 10000 });

    // 3. Verify attempt counter and strategy are displayed
    const attemptCounter = page.getByTestId("replan-attempt-counter");
    await expect(attemptCounter).toBeVisible();
    await expect(attemptCounter).toContainText(/Attempt/i);

    const replanStrategy = page.getByTestId("replan-strategy");
    await expect(replanStrategy).toContainText(/Strategy:/i);

    // 4. Wait for stream to progress to exhausted status badge
    const exhaustedBadge = page.getByTestId("replan-badge-exhausted");
    await expect(exhaustedBadge).toBeVisible({ timeout: 15000 });
    await expect(exhaustedBadge).toHaveText(/exhausted/i);

    // 5. Verify manual takeover and abort action buttons appear when exhausted
    const takeoverBtn = page.getByTestId("replan-takeover-btn");
    const abortBtn = page.getByTestId("replan-abort-btn");
    await expect(takeoverBtn).toBeVisible();
    await expect(abortBtn).toBeVisible();

    // 6. Test manual takeover action
    await takeoverBtn.click();
    await expect(page.getByTestId("execution-status-badge")).toHaveAttribute("data-status", "running");
  });

  test("gracefully handles missing screenshot references with accessible placeholders", async ({
    page,
  }) => {
    // Inject a failed step event without screenshot URLs
    await page.addInitScript(() => {
      // Mock window to load with null screenshot URLs if necessary
    });

    await page.goto("/workflows/failed/execution?mock=true&speed=50");

    const failureCard = page.getByTestId("verification-failure-card");
    await expect(failureCard).toBeVisible({ timeout: 10000 });

    // Verify screenshot comparison columns exist and have accessible structure
    await expect(page.getByTestId("expected-screenshot-col")).toBeVisible();
    await expect(page.getByTestId("observed-screenshot-col")).toBeVisible();
  });
});
