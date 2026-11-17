import { expect, test } from "@playwright/test";

test.describe("Freshness Badges, Share Banner, Version History & Step Diffs", () => {
  test("renders unified freshness badges across Library and Dashboard", async ({ page }) => {
    // 1. Visit Tutorial Library (/tutorials)
    await page.goto("/tutorials");

    // 2. Verify all 4 freshness statuses are represented on cards
    const verifiedBadge = page.getByTestId("tutorial-status-badge").filter({ hasText: "Verified" }).first();
    const outdatedBadge = page.getByTestId("tutorial-status-badge").filter({ hasText: "Outdated" }).first();
    const autoUpdatedBadge = page.getByTestId("tutorial-status-badge").filter({ hasText: "Auto-Updated" }).first();
    const notCheckedBadge = page.getByTestId("tutorial-status-badge").filter({ hasText: "Not Auto-Checked" }).first();

    await expect(verifiedBadge).toBeVisible();
    await expect(outdatedBadge).toBeVisible();
    await expect(autoUpdatedBadge).toBeVisible();
    await expect(notCheckedBadge).toBeVisible();

    // 3. Test filter tabs: Click "Auto-Updated" tab
    const autoUpdatedTab = page.getByTestId("filter-status-auto-updated");
    if (await autoUpdatedTab.isVisible()) {
      await autoUpdatedTab.click();
      await expect(
        page.getByTestId("tutorial-card").filter({ hasText: "Healed Repository Settings in Gitea" })
      ).toBeVisible();
      await expect(
        page.getByTestId("tutorial-card").filter({ hasText: "Create a repository in local Gitea" })
      ).not.toBeVisible();
    }

    // 4. Reset to All tab
    const allTab = page.getByTestId("filter-status-all");
    await allTab.click();

    // 5. Visit Dashboard / Home screen
    await page.goto("/");
    const dashboardList = page.getByTestId("my-tutorials-list");
    await expect(dashboardList).toBeVisible();

    // Verify freshness badges render on dashboard cards
    const dashboardBadge = dashboardList.getByTestId("tutorial-status-badge").first();
    await expect(dashboardBadge).toBeVisible();
  });

  test("opens auto-updated tutorial, opens Version History, expands wording changes, and inspects step diff", async ({
    page,
  }) => {
    // 1. Navigate to the auto-updated tutorial
    await page.goto("/tutorials/auto-updated-tutorial");

    // 2. Assert player stage is visible and header shows Auto-Updated badge
    const playerRoot = page.getByTestId("tutorial-player-root");
    await expect(playerRoot).toBeVisible();

    const headerBadge = playerRoot.getByTestId("tutorial-status-badge").filter({ hasText: "Auto-Updated" });
    await expect(headerBadge).toBeVisible();

    // 3. Open Version History drawer
    const openHistoryBtn = page.getByTestId("open-version-history-btn");
    await expect(openHistoryBtn).toBeVisible();
    await openHistoryBtn.click();

    const historyDrawer = page.getByTestId("version-history-drawer");
    await expect(historyDrawer).toBeVisible();

    // 4. Assert version record v1.1 has auto-updated badge
    const v11Record = historyDrawer.getByTestId("version-item").filter({ hasText: "v1.1" });
    await expect(v11Record).toBeVisible();
    await expect(v11Record.getByTestId("version-auto-updated-badge")).toHaveText(/Auto-Updated/i);

    // 5. Test wording-only changes collapse/expand (D11)
    const wordingToggle = historyDrawer.getByTestId("toggle-wording-changes");
    await expect(wordingToggle).toBeVisible();
    await expect(wordingToggle).toHaveText(/Wording-only changes/i);

    // Wording versions list is collapsed by default
    const wordingList = historyDrawer.getByTestId("wording-versions-list");
    await expect(wordingList).not.toBeVisible();

    // Click toggle to expand wording changes
    await wordingToggle.click();
    await expect(wordingList).toBeVisible();
    await expect(wordingList.getByTestId("wording-version-item")).toBeVisible();

    // 6. Inspect step diff for healed version v1.1
    const viewDiffBtn = v11Record.getByTestId("view-diff-btn");
    await expect(viewDiffBtn).toBeVisible();
    await viewDiffBtn.click();

    // Assert step diff modal opened
    const diffModal = page.getByTestId("inspect-diff-modal");
    await expect(diffModal).toBeVisible();

    const diffViewer = diffModal.getByTestId("step-diff-viewer");
    await expect(diffViewer).toBeVisible();

    // Assert selector diff highlighting: old selector in strikethrough, new in emerald
    const oldSelector = diffViewer.getByTestId("diff-old-selector").first();
    await expect(oldSelector).toBeVisible();
    await expect(oldSelector).toHaveClass(/line-through/);

    const newSelector = diffViewer.getByTestId("diff-new-selector").first();
    await expect(newSelector).toBeVisible();
    await expect(newSelector).toHaveClass(/text-emerald/);

    // Close diff modal
    const closeDiffBtn = page.getByTestId("close-diff-modal-btn");
    await closeDiffBtn.click();
    await expect(diffModal).not.toBeVisible();
  });

  test("opens outdated share link and confirms Site Changed alert banner is visible", async ({
    page,
  }) => {
    // 1. Navigate to public share link for outdated tutorial
    await page.goto("/share/outdated-token");

    // 2. Assert shared page header is present with Outdated badge
    const header = page.getByTestId("shared-page-header");
    await expect(header).toBeVisible();

    const headerBadge = header.getByTestId("tutorial-status-badge");
    await expect(headerBadge).toBeVisible();
    await expect(headerBadge).toHaveText(/Outdated/i);

    // 3. Confirm Site Changed alert banner is rendered prominently above stage
    const banner = page.getByTestId("outdated-site-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toHaveText(/Site Changed/i);
    await expect(banner).toHaveText(/The target website has changed since this tutorial was recorded/i);

    // 4. Confirm player is mounted in read-only mode
    await expect(page.getByTestId("readonly-badge")).toBeVisible();
    await expect(page.getByTestId("tutorial-player-root")).toBeVisible();
  });
});
