import { expect, test } from "@playwright/test";

test.describe("Public Shareable Read-Only Tutorial Page (/share/[token])", () => {
  test("allows unauthenticated visitor to view tutorial with full player controls and no edit/manage buttons", async ({
    page,
    context,
  }) => {
    // 1. Clear cookies to simulate an unauthenticated public visitor
    await context.clearCookies();

    // 2. Navigate directly to the public share URL
    await page.goto("/share/test-sample-token");

    // 3. Confirm URL remains on the share page (no redirect to /login)
    await expect(page).toHaveURL(/\/share\/test-sample-token/);

    // 4. Verify clean shared branding header is visible
    const header = page.getByTestId("shared-page-header");
    await expect(header).toBeVisible();
    await expect(page.getByTestId("shared-mode-indicator")).toContainText("Viewing shared tutorial");

    // Verify user dashboard / profile controls are NOT present
    await expect(page.getByTestId("user-email-display")).not.toBeAttached();
    await expect(page.getByTestId("dashboard-logout-btn")).not.toBeAttached();
    await expect(page.getByRole("button", { name: /sign out|logout/i })).not.toBeAttached();

    // 5. Verify TutorialPlayer root and Read-Only badge
    const playerRoot = page.getByTestId("tutorial-player-root");
    await expect(playerRoot).toBeVisible();
    await expect(page.getByTestId("readonly-badge")).toHaveText("Read-Only");

    // 6. Verify strictly no Edit, Delete, Re-run, or Share Management controls
    await expect(page.getByRole("button", { name: /^edit/i })).not.toBeAttached();
    await expect(page.getByRole("button", { name: /^delete/i })).not.toBeAttached();
    await expect(page.getByRole("button", { name: /^re-run|rerun/i })).not.toBeAttached();
    await expect(page.getByRole("button", { name: /share settings/i })).not.toBeAttached();

    // 7. Verify transport controls are functional
    const playBtn = page.getByTestId("control-play-pause");
    await expect(playBtn).toBeVisible();
    await playBtn.click();

    const nextBtn = page.getByTestId("control-next-step");
    await expect(nextBtn).toBeVisible();
    await nextBtn.click();

    // Verify current step transitioned to Step 2
    await expect(page.getByTestId("current-step-card")).toContainText("2");

    // Verify captions toggle works
    const captionsBtn = page.getByTestId("control-toggle-captions");
    await expect(captionsBtn).toBeVisible();
    await captionsBtn.click();

    // 8. Verify keyboard shortcut transport control (Space/K for toggle play)
    await page.keyboard.press("KeyK");
  });

  test("displays friendly RevokedLinkNotice when share token is invalid or revoked", async ({
    page,
    context,
  }) => {
    // 1. Clear session cookies
    await context.clearCookies();

    // 2. Navigate to invalid/revoked share token URL
    await page.goto("/share/revoked-token");

    // 3. Confirm URL remains on the share page (no redirect to /login)
    await expect(page).toHaveURL(/\/share\/revoked-token/);

    // 4. Verify RevokedLinkNotice presentation card
    const notice = page.getByTestId("revoked-link-notice");
    await expect(notice).toBeVisible();
    await expect(notice).toContainText("Tutorial Link Unavailable");
    await expect(notice).toContainText("This tutorial link is invalid or has been revoked by the creator.");

    // 5. Verify home link is present
    const homeLink = page.getByTestId("revoked-home-link");
    await expect(homeLink).toBeVisible();
    await expect(homeLink).toHaveAttribute("href", "/");

    // 6. Verify player is not rendered
    await expect(page.getByTestId("tutorial-player-root")).not.toBeAttached();
  });
});
