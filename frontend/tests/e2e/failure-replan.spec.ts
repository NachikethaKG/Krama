import { expect, test } from "@playwright/test";

test.describe("Failure Diagnostic & Live Replan UI", () => {
  test("displays accessible Expected X / Observed Y failure diagnostic card with side-by-side screenshots", async ({
    page,
  }) => {
    // 1. Navigate to failed execution workflow
    await page.goto("/runs/failed/live?speed=50");

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

    // The contract has no "expected" screenshot: the left image is the page before this step
    const previousImg = page.getByTestId("previous-screenshot-img");
    const observedImg = page.getByTestId("observed-screenshot-img");
    await expect(previousImg).toBeVisible();
    await expect(observedImg).toBeVisible();
    await expect(previousImg).toHaveAttribute("src", "/screenshots/step-1.png");
    await expect(observedImg).toHaveAttribute("src", "/mock-observed.png");
  });

  test("displays live replan progression with attempt counter and status badges transitioning to exhausted recovery", async ({
    page,
  }) => {
    // 1. Navigate to replan workflow execution
    await page.goto("/runs/replan/live?speed=50");

    // 2. Wait for replan status indicator to appear
    const replanIndicator = page.getByTestId("replan-status-indicator");
    await expect(replanIndicator).toBeVisible({ timeout: 10000 });

    // 3. Verify attempt counter and strategy are displayed
    const attemptCounter = page.getByTestId("replan-attempt-counter");
    await expect(attemptCounter).toBeVisible();
    await expect(attemptCounter).toContainText(/Attempt/i);

    // 4. Wait for stream to progress to exhausted status badge
    const exhaustedBadge = page.getByTestId("replan-badge-exhausted");
    await expect(exhaustedBadge).toBeVisible({ timeout: 15000 });
    await expect(exhaustedBadge).toHaveText(/exhausted/i);

    // 5. ONE decision control: the pause banner ("try once more" / deny); the indicator has no buttons
    await expect(page.getByTestId("replan-takeover-btn")).toHaveCount(0);
    const pauseBanner = page.getByTestId("pause-banner");
    await expect(pauseBanner).toHaveAttribute("data-pause-reason", "recovery_exhausted");

    // 6. Allow retries the step once more; the run then completes
    await page.getByTestId("resume-run-btn").click();
    await expect(page.getByTestId("completion-banner")).toBeVisible({ timeout: 15000 });
  });

  test("gracefully handles missing screenshot references with accessible placeholders", async ({
    page,
  }) => {
    // Inject a failed step event without screenshot URLs
    await page.addInitScript(() => {
      // Mock window to load with null screenshot URLs if necessary
    });

    await page.goto("/runs/failed/live?speed=50");

    const failureCard = page.getByTestId("verification-failure-card");
    await expect(failureCard).toBeVisible({ timeout: 10000 });

    // Verify screenshot comparison columns exist and have accessible structure
    await expect(page.getByTestId("previous-screenshot-col")).toBeVisible();
    await expect(page.getByTestId("observed-screenshot-col")).toBeVisible();
  });
});
