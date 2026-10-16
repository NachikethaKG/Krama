import { expect, test } from "@playwright/test";

test.describe("Safety Baseline: Policy Confirmation Modal & Manual Takeover Screen", () => {
  test("happy path: paused destructive step opens policy modal with high-risk badge and Allow resumes run", async ({
    page,
  }) => {
    // 1. Navigate to paused workflow route
    await page.goto("/workflows/paused/execution?mock=true&speed=50");

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
    await expect(riskBadge).toContainText(/High Risk/i);

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

    // 7. Modal dismisses and execution state transitions back to running
    await expect(modal).not.toBeVisible();
    await expect(statusBadge).toHaveAttribute("data-status", "running");
  });

  test("deny path: clicking Deny halts the destructive step and cancels the run safely", async ({
    page,
  }) => {
    // 1. Navigate to paused workflow route
    await page.goto("/workflows/paused/execution?mock=true&speed=50");

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

  test("blocker path: simulated run.stopped with bot barrier displays Automation Restricted screen", async ({
    page,
  }) => {
    // 1. Navigate to blocked workflow route emitting run.stopped with cloudflare_turnstile
    await page.goto("/workflows/blocked/execution?mock=true&speed=50");

    // 2. Wait for Automation Restricted screen to appear
    const restrictedScreen = page.getByTestId("automation-restricted-screen");
    await expect(restrictedScreen).toBeVisible({ timeout: 10000 });

    // 3. Verify screen heading and barrier badge
    await expect(
      restrictedScreen.getByText(/Automation restricted → Take over manually/i)
    ).toBeVisible();
    await expect(restrictedScreen.getByTestId("barrier-type-badge")).toHaveText(/Cloudflare Turnstile/i);
    await expect(
      restrictedScreen.getByText(/Cloudflare Turnstile challenge detected on target page/i)
    ).toBeVisible();

    // 4. Verify Open Target URL link
    const openUrlLink = restrictedScreen.getByTestId("open-target-url-btn");
    await expect(openUrlLink).toBeVisible();
    await expect(openUrlLink).toHaveAttribute("href", "http://localhost:3001/login");
    await expect(openUrlLink).toHaveAttribute("target", "_blank");

    // 5. Verify takeover manual controls: Resume Execution & Abort Run
    const resumeBtn = restrictedScreen.getByTestId("takeover-resume-btn");
    const abortBtn = restrictedScreen.getByTestId("takeover-abort-btn");
    await expect(resumeBtn).toBeVisible();
    await expect(abortBtn).toBeVisible();

    // 6. Click Abort Run to safely terminate blocked execution
    await abortBtn.click();
    await expect(page.getByTestId("cancelled-banner")).toBeVisible();
    await expect(page.getByTestId("execution-status-badge")).toHaveAttribute(
      "data-status",
      "cancelled"
    );
  });
});
