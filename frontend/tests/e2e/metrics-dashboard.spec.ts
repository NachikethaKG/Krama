import { expect, test } from "@playwright/test";

test.describe("PRD §33 Technical Metrics Dashboard & Multi-Target Benchmark", () => {
  test("navigates to /dashboard/metrics from user dashboard and verifies KPI cards & platform filters", async ({
    page,
  }) => {
    // 1. Visit User Dashboard
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/);

    // 2. Click "Technical Metrics" navigation link in dashboard header
    const metricsLink = page.getByTestId("nav-technical-metrics");
    await expect(metricsLink).toBeVisible();
    await metricsLink.click();

    // 3. Verify URL is /dashboard/metrics
    await expect(page).toHaveURL(/\/dashboard\/metrics/);

    // 4. Assert header and benchmark badges
    await expect(page.getByRole("heading", { name: "PRD §33 Technical Metrics" })).toBeVisible();
    await expect(page.getByTestId("metrics-task-count-badge")).toHaveText("12 Benchmark Workflows");
    await expect(page.getByTestId("metrics-generated-at")).toBeVisible();

    // 5. Assert the 4 PRD §33 KPI Summary Cards
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

    // 6. Assert Workflow Breakdown Table renders 12 tasks initially
    const table = page.getByTestId("metrics-breakdown-table");
    await expect(table).toBeVisible();

    // Check presence of both platforms
    await expect(page.getByTestId("task-row-gitea-create-repo")).toBeVisible();
    await expect(page.getByTestId("platform-badge-gitea-create-repo")).toHaveText("Gitea");

    await expect(page.getByTestId("task-row-github-create-repo")).toBeVisible();
    await expect(page.getByTestId("platform-badge-github-create-repo")).toHaveText("GitHub");

    // 7. Test Platform Filtering
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

  test("direct navigation to /dashboard/metrics displays full technical matrix", async ({ page }) => {
    await page.goto("/dashboard/metrics");
    await expect(page).toHaveURL(/\/dashboard\/metrics/);
    await expect(page.getByTestId("metrics-kpi-grid")).toBeVisible();
    await expect(page.getByTestId("metrics-breakdown-table")).toBeVisible();
    await expect(page.getByTestId("task-row-gitea-comment-issue")).toBeVisible();
    await expect(page.getByTestId("task-row-github-add-file")).toBeVisible();
  });
});
