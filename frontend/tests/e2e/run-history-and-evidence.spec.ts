import { expect, test } from "@playwright/test";

test.describe("Run History & Step Verification Evidence View", () => {
  test("lists runs 20 to a page with the task as the link", async ({ page }) => {
    await page.goto("/runs");

    await expect(page.getByRole("heading", { name: "Runs", level: 1 })).toBeVisible();
    await expect(page.getByTestId("runs-list-table")).toBeVisible();
    // The 12 mock runs fit on one page, so both page buttons are disabled
    await expect(page.getByTestId("pagination-info")).toContainText("Showing 1 to 12");
    await expect(page.getByTestId("run-row-run-1")).toBeVisible();
    await expect(page.getByTestId("run-row-run-12")).toBeVisible();
    await expect(page.getByTestId("pagination-prev")).toBeDisabled();
    await expect(page.getByTestId("pagination-next")).toBeDisabled();
    // No raw run ids on screen: the task text is the link
    await expect(page.getByTestId("run-row-run-1").getByTestId("run-link")).toHaveAttribute("href", "/runs/run-1");
  });

  test("drills down into step verification evidence with multi-layer badges and screenshots", async ({
    page,
  }) => {
    // 1. Navigate to runs list and click view evidence for run-1
    await page.goto("/runs");
    const run1Row = page.getByTestId("run-row-run-1");
    await expect(run1Row).toBeVisible();

    const viewEvidenceBtn = run1Row.getByTestId("run-view-button");
    await viewEvidenceBtn.click();

    // 2. Validate URL and detail header
    await expect(page).toHaveURL(/\/runs\/run-1$/);
    await expect(page.getByTestId("run-detail-id")).toHaveText("run-1");
    await expect(page.getByTestId("run-detail-prompt")).toBeVisible();

    // 3. Validate KPI summary cards
    await expect(page.getByTestId("stat-total-steps")).toHaveText("5");
    await expect(page.getByTestId("stat-verified-steps")).toHaveText("5");
    await expect(page.getByTestId("stat-failed-steps")).toHaveText("0");
    await expect(page.getByTestId("stat-duration")).toHaveText("5s");

    // 4. Validate Step 1 (ARIA tree layer)
    const step1Card = page.getByTestId("step-evidence-card-1");
    await expect(step1Card).toBeVisible();
    await expect(step1Card.getByTestId("verification-method-badge")).toHaveAttribute("data-method", "aria");
    await expect(step1Card.getByTestId("verification-method-badge")).toContainText("Page content");
    await expect(step1Card.getByTestId("confidence-score")).toContainText("100%");
    const step1Img = step1Card.getByTestId("step-screenshot");
    await expect(step1Img).toBeVisible();
    await expect(step1Img).toHaveAttribute("src", "/screenshots/step-1.png");

    // 5. Validate Step 2 (URL & DOM layer)
    const step2Card = page.getByTestId("step-evidence-card-2");
    await expect(step2Card).toBeVisible();
    await expect(step2Card.getByTestId("verification-method-badge")).toHaveAttribute("data-method", "url_dom");
    await expect(step2Card.getByTestId("verification-method-badge")).toContainText("Page address");
    await expect(step2Card.getByTestId("confidence-score")).toContainText("98%");

    // 6. Validate Step 4 (Network layer)
    const step4Card = page.getByTestId("step-evidence-card-4");
    await expect(step4Card).toBeVisible();
    await expect(step4Card.getByTestId("verification-method-badge")).toHaveAttribute("data-method", "network");
    await expect(step4Card.getByTestId("verification-method-badge")).toContainText("Site's answer");
    await expect(step4Card.getByTestId("confidence-score")).toContainText("85%");

    // 7. Validate Step 5 (Vision layer)
    const step5Card = page.getByTestId("step-evidence-card-5");
    await expect(step5Card).toBeVisible();
    await expect(step5Card.getByTestId("verification-method-badge")).toHaveAttribute("data-method", "vision");
    await expect(step5Card.getByTestId("verification-method-badge")).toContainText("Screenshot");
    await expect(step5Card.getByTestId("confidence-score")).toContainText("95%");

    // 8. Toggle state details on Step 1
    const toggleBtn = step1Card.getByTestId("toggle-state-details-button");
    await toggleBtn.click();
    await expect(step1Card.getByTestId("step-state-details")).toBeVisible();
  });

  test("handles missing and broken screenshot fallbacks gracefully", async ({ page }) => {
    // Navigate to run-3 (contains missing and broken screenshot edge cases)
    await page.goto("/runs/run-3");

    // Step 1: screenshotUrl is undefined
    const step1Card = page.getByTestId("step-evidence-card-1");
    await expect(step1Card).toBeVisible();
    const placeholder1 = step1Card.getByTestId("step-screenshot-placeholder");
    await expect(placeholder1).toBeVisible();
    await expect(placeholder1).toContainText("No screenshot captured for this step");

    // Step 2: screenshotUrl points to broken image
    const step2Card = page.getByTestId("step-evidence-card-2");
    await expect(step2Card).toBeVisible();
    // In browser, loading broken image triggers onError which swaps to placeholder
    const placeholder2 = step2Card.getByTestId("step-screenshot-placeholder");
    await expect(placeholder2).toBeVisible({ timeout: 5000 });
    await expect(placeholder2).toContainText("Screenshot failed to load from artifact store");
  });

  test("renders run-not-found state and back navigation on invalid run id", async ({ page }) => {
    await page.goto("/runs/unknown-run-999");

    const notFoundCard = page.getByTestId("run-not-found");
    await expect(notFoundCard).toBeVisible();
    await expect(page.getByText("Run Not Found")).toBeVisible();

    const backBtn = page.getByTestId("back-to-runs-button");
    await expect(backBtn).toBeVisible();
    await backBtn.click();

    await expect(page).toHaveURL(/\/runs$/);
  });
});
