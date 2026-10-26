import { expect, test } from "@playwright/test";

test.describe("PRD §33 Technical Metrics Dashboard & Multi-Target Benchmark", () => {
  test("logs in with seeded credentials, navigates to /dashboard/metrics, and verifies layout without hydration errors", async ({
    page,
    context,
  }) => {
    // Collect console errors to detect any client hydration mismatch
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    // 1. Clear session cookies to begin from unauthenticated state
    await context.clearCookies();

    // 2. Navigate to /login with 'from' parameter pointing to metrics dashboard
    await page.goto("/login?from=%2Fdashboard%2Fmetrics");
    await expect(page).toHaveURL(/\/login\?from=%2Fdashboard%2Fmetrics/);

    // 3. Fill seeded credentials (demo@krama.dev)
    const fillBtn = page.getByTestId("use-demo-creds-btn");
    await expect(fillBtn).toBeVisible();
    await fillBtn.click();

    // 4. Submit login form
    const submitBtn = page.getByTestId("login-submit");
    await submitBtn.click();

    // 5. Verify redirection directly to /dashboard/metrics
    await expect(page).toHaveURL(/\/dashboard\/metrics/);

    // 6. Assert zero React hydration errors
    const hydrationErrors = consoleErrors.filter(
      (err) => err.toLowerCase().includes("hydration") || err.toLowerCase().includes("did not match"),
    );
    expect(hydrationErrors).toHaveLength(0);

    // 7. Verify no horizontal page overflow scrollbar
    const hasHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(hasHorizontalOverflow).toBe(false);

    // 8. Assert all 4 PRD §33 KPI Summary Cards are visible
    // (a) Task Success Rate (Target >= 80%)
    const successCard = page.getByTestId("kpi-success-rate");
    await expect(successCard).toBeVisible();
    await expect(page.getByTestId("value-success-rate")).toHaveText("93.3%");
    await expect(page.getByTestId("badge-success-rate")).toHaveText("Target ≥ 80%");

    // (b) Verifier Accuracy (Target >= 90%)
    const accuracyCard = page.getByTestId("kpi-verifier-accuracy");
    await expect(accuracyCard).toBeVisible();
    await expect(page.getByTestId("value-verifier-accuracy")).toHaveText("99.7%");
    await expect(page.getByTestId("badge-verifier-accuracy")).toHaveText("Target ≥ 90%");

    // (c) Recovery Rate (Target >= 50%)
    const recoveryCard = page.getByTestId("kpi-recovery-rate");
    await expect(recoveryCard).toBeVisible();
    await expect(page.getByTestId("value-recovery-rate")).toHaveText("100.0%");
    await expect(page.getByTestId("badge-recovery-rate")).toHaveText("Target ≥ 50%");

    // (d) Latency Profile (< 15s plan, < 60s total)
    const latencyCard = page.getByTestId("kpi-latency-profile");
    await expect(latencyCard).toBeVisible();
    await expect(page.getByTestId("value-latency-profile")).toHaveText("41.1s");
    await expect(page.getByTestId("badge-latency-profile")).toHaveText("Target < 60s");

    // 9. Assert Workflow Breakdown Table renders 12 tasks initially
    const table = page.getByTestId("metrics-breakdown-table");
    await expect(table).toBeVisible();

    // Check presence of both platforms
    await expect(page.getByTestId("task-row-gitea-create-repo")).toBeVisible();
    await expect(page.getByTestId("platform-badge-gitea-create-repo")).toHaveText("Gitea");

    await expect(page.getByTestId("task-row-github-create-repo")).toBeVisible();
    await expect(page.getByTestId("platform-badge-github-create-repo")).toHaveText("GitHub");

    // 10. Test Platform Filtering
    // Filter to Gitea
    const giteaTab = page.getByTestId("filter-tab-gitea");
    await giteaTab.click();
    await expect(page.getByTestId("task-row-gitea-create-repo")).toBeVisible();
    await expect(page.getByTestId("task-row-github-create-repo")).not.toBeVisible();

    // Filter to GitHub
    const githubTab = page.getByTestId("filter-tab-github");
    await githubTab.click();
    await expect(page.getByTestId("task-row-github-create-repo")).toBeVisible();
    await expect(page.getByTestId("task-row-gitea-create-repo")).not.toBeVisible();

    // Filter back to All
    const allTab = page.getByTestId("filter-tab-all");
    await allTab.click();
    await expect(page.getByTestId("task-row-gitea-create-repo")).toBeVisible();
    await expect(page.getByTestId("task-row-github-create-repo")).toBeVisible();
  });

  test("navigates to /dashboard/metrics via dashboard header link", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/);

    const metricsLink = page.getByTestId("nav-technical-metrics");
    await expect(metricsLink).toBeVisible();
    await metricsLink.click();

    await expect(page).toHaveURL(/\/dashboard\/metrics/);
    await expect(page.getByTestId("metrics-kpi-grid")).toBeVisible();
    await expect(page.getByTestId("metrics-breakdown-table")).toBeVisible();
  });
});
