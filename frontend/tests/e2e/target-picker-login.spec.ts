import { expect, test } from "@playwright/test";

test.describe("Target Picker and Manual Login Flow", () => {
  test("switches between targets, validates custom URLs, and executes guided login flow", async ({
    page,
  }) => {
    // 1. Navigate to Create Workflow Run page
    await page.goto("/runs/new");

    const targetPicker = page.getByTestId("target-picker");
    await expect(targetPicker).toBeVisible();

    const giteaOption = page.getByTestId("target-option-gitea");
    const githubOption = page.getByTestId("target-option-github");
    const customOption = page.getByTestId("target-option-custom");

    await expect(giteaOption).toBeVisible();
    await expect(githubOption).toBeVisible();
    await expect(customOption).toBeVisible();

    // 2. Custom Target selection and URL validation
    await customOption.click();
    await expect(customOption).toHaveAttribute("aria-checked", "true");

    const customInput = page.getByTestId("custom-target-url-input");
    await expect(customInput).toBeVisible();

    // Type malformed URL
    await customInput.fill("ftp://wrong.protocol/git");
    const errorBanner = page.getByTestId("target-url-error");
    await expect(errorBanner).toBeVisible();
    await expect(errorBanner).toContainText(/must use http:\/\/ or https:\/\//i);

    // Type valid custom URL
    await customInput.fill("https://git.company.internal");
    await expect(errorBanner).not.toBeVisible();

    // 3. Switch to GitHub (Real) and verify Manual Login Guide appears
    await githubOption.click();
    await expect(githubOption).toHaveAttribute("aria-checked", "true");

    const loginGuide = page.getByTestId("manual-login-guide");
    await expect(loginGuide).toBeVisible();

    // Verify zero-password security model explainer
    const explainer = page.getByTestId("manual-login-explainer");
    await expect(explainer).toBeVisible();
    await expect(explainer).toContainText(
      "You will log in directly in a separate browser window. Krama only saves an encrypted session cookie, never your password.",
    );

    // 4. Trigger manual login
    const launchBtn = page.getByTestId("launch-manual-login-btn");
    await expect(launchBtn).toBeVisible();
    await launchBtn.click();

    // 5. Verify pending/waiting state
    const pendingBanner = page.getByTestId("manual-login-pending");
    await expect(pendingBanner).toBeVisible();
    await expect(pendingBanner).toContainText(
      "Waiting for you to complete sign-in in the open browser...",
    );

    // 6. Verify transition to active session badge
    const activeBadge = page.getByTestId("manual-login-active-badge");
    await expect(activeBadge).toBeVisible({ timeout: 10000 });
    await expect(activeBadge).toContainText(
      "Session Active (Encrypted Storage State Saved)",
    );
  });
});
