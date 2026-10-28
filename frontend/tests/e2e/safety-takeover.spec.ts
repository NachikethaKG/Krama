import { expect, test } from "@playwright/test";

test.describe("Safety Baseline: Policy Confirmation Modal & Manual Takeover Screen", () => {
  test("happy path: paused destructive step opens policy modal with high-risk badge and Allow resumes run", async ({
    page,
  }) => {
    // 1. Navigate to paused workflow route
    await page.goto("/runs/paused/live?speed=50");

    // 2. Policy confirmation modal appears upon pause
    const modal = page.getByTestId("policy-confirmation-modal");
    await expect(modal).toBeVisible({ timeout: 10000 });
    await expect(modal).toHaveAttribute("role", "dialog");
    await expect(modal).toHaveAttribute("aria-modal", "true");

    // 3. Verify title, step details, and high-risk badge
    await expect(modal.getByText(/Policy Confirmation Required/i)).toBeVisible();
    await expect(modal.getByText(/Step 2/i)).toBeVisible();

    const riskBadge = modal.getByTestId("risk-badge");
    await expect(riskBadge).toBeVisible();
    await expect(riskBadge).toHaveAttribute("data-risk-level", "high");
    await expect(riskBadge).toContainText(/Changes or deletes/i);

    // 4. Verify explicit policy rationale / safety flag
    await expect(modal.getByText(/Safety Policy Flag/i)).toBeVisible();
    await expect(modal.getByTestId("policy-flag-badge")).toHaveText(/DESTRUCTIVE ACTION/i);

    // 5. Verify status badge indicates paused
    const statusBadge = page.getByTestId("execution-status-badge");
    await expect(statusBadge).toHaveAttribute("data-status", "paused");

    // 6. Click Allow button to confirm action and resume execution
    const allowBtn = modal.getByTestId("modal-allow-btn");
    await expect(allowBtn).toBeVisible();
    await allowBtn.click();

    // 7. Modal dismisses; the run resumes (run.resumed) and completes
    await expect(modal).not.toBeVisible();
    await expect(page.getByTestId("completion-banner")).toBeVisible({ timeout: 15000 });
  });

  test("deny path: clicking Deny halts the destructive step and cancels the run safely", async ({
    page,
  }) => {
    // 1. Navigate to paused workflow route
    await page.goto("/runs/paused/live?speed=50");

    // 2. Wait for policy modal to appear
    const modal = page.getByTestId("policy-confirmation-modal");
    await expect(modal).toBeVisible({ timeout: 10000 });

    // 3. Click Deny button
    const denyBtn = modal.getByTestId("modal-deny-btn");
    await expect(denyBtn).toBeVisible();
    await denyBtn.click();

    // 4. Modal dismisses and cancelled banner is displayed
    await expect(modal).not.toBeVisible();
    const cancelledBanner = page.getByTestId("cancelled-banner");
    await expect(cancelledBanner).toBeVisible();
    await expect(page.getByTestId("execution-status-badge")).toHaveAttribute(
      "data-status",
      "cancelled"
    );
  });

  test("Escape does not deny: the modal stays and the run stays paused", async ({ page }) => {
    await page.goto("/runs/paused/live?speed=50");
    const modal = page.getByTestId("policy-confirmation-modal");
    await expect(modal).toBeVisible({ timeout: 10000 });
    await expect(page.getByTestId("pause-banner")).toHaveCount(0);
    await page.keyboard.press("Escape");
    await expect(modal).toBeVisible();
    await expect(page.getByTestId("execution-status-badge")).toHaveAttribute("data-status", "paused");
  });

  test("blocker path: a policy stop (run.failed, policy_stop) displays the Automation Restricted screen", async ({
    page,
  }) => {
    // 1. The blocked run ends with run.failed {error.details.reason: "policy_stop", policy_reason: "captcha"}
    await page.goto("/runs/blocked/live?speed=50");

    // 2. Wait for Automation Restricted screen to appear
    const restrictedScreen = page.getByTestId("automation-restricted-screen");
    await expect(restrictedScreen).toBeVisible({ timeout: 10000 });

    // 3. Verify screen heading and barrier badge
    await expect(
      restrictedScreen.getByText(/Automation restricted → Take over manually/i)
    ).toBeVisible();
    await expect(restrictedScreen.getByTestId("barrier-type-badge")).toHaveText(/CAPTCHA/i);
    await expect(restrictedScreen.getByText(/A CAPTCHA challenge was detected on the target page/i)).toBeVisible();

    // 4. Verify Open Target URL link
    const openUrlLink = restrictedScreen.getByTestId("open-target-url-btn");
    await expect(openUrlLink).toBeVisible();
    await expect(openUrlLink).toHaveAttribute("href", "http://localhost:3001");
    await expect(openUrlLink).toHaveAttribute("target", "_blank");

    // 5. The run already failed: no Resume / Abort, only ways forward
    await expect(restrictedScreen.getByTestId("takeover-resume-btn")).toHaveCount(0);
    await expect(restrictedScreen.getByTestId("takeover-new-task-link")).toBeVisible();
    await expect(page.getByTestId("execution-status-badge")).toHaveAttribute("data-status", "failed");
  });
});
