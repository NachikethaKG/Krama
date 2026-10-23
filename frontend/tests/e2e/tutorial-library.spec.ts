import { expect, test } from "@playwright/test";

test.describe("Tutorial Library & Filtering (/tutorials)", () => {
  test("renders tutorial library, filters by search keyword and status tabs, and opens player", async ({
    page,
  }) => {
    // 1. Navigate to the tutorial library page
    await page.goto("/tutorials");

    // 2. Assert page header and title are visible
    const pageTitle = page.getByRole("heading", {
      name: /Interactive Tutorials/i,
      level: 1,
    });
    await expect(pageTitle).toBeVisible();

    // 3. Assert search bar and status filter tabs are present
    const searchInput = page.getByTestId("tutorial-search-input");
    await expect(searchInput).toBeVisible();

    const allTab = page.getByTestId("filter-status-all");
    const verifiedTab = page.getByTestId("filter-status-verified");
    const outdatedTab = page.getByTestId("filter-status-outdated");

    await expect(allTab).toBeVisible();
    await expect(verifiedTab).toBeVisible();
    await expect(outdatedTab).toBeVisible();

    // 4. Assert tutorial cards are rendered in the grid
    const cards = page.getByTestId("tutorial-card");
    await expect(cards.first()).toBeVisible();
    const initialCount = await cards.count();
    expect(initialCount).toBeGreaterThanOrEqual(4);

    // Assert cards show target badges and status badges
    const giteaCard = page
      .getByTestId("tutorial-card")
      .filter({ hasText: "Create a repository in local Gitea" });
    await expect(giteaCard).toBeVisible();
    await expect(giteaCard.getByTestId("tutorial-card-target")).toHaveText(/Gitea/i);
    await expect(giteaCard.getByTestId("tutorial-card-status")).toHaveText(/Verified/i);

    // 5. Test real-time search filtering: type "GitHub"
    await searchInput.fill("GitHub");

    // Cards should filter dynamically
    await expect(
      page.getByTestId("tutorial-card").filter({ hasText: "Star a repository on GitHub" }),
    ).toBeVisible();
    await expect(
      page.getByTestId("tutorial-card").filter({ hasText: "Create an issue with template on GitHub" }),
    ).toBeVisible();
    await expect(
      page.getByTestId("tutorial-card").filter({ hasText: "Create a repository in local Gitea" }),
    ).not.toBeVisible();

    // 6. Test clear search button
    const clearBtn = page.getByTestId("tutorial-search-clear");
    await expect(clearBtn).toBeVisible();
    await clearBtn.click();
    await expect(searchInput).toHaveValue("");
    await expect(giteaCard).toBeVisible();

    // 7. Test status filtering: click "Verified" tab
    await verifiedTab.click();
    await expect(verifiedTab).toHaveAttribute("aria-selected", "true");
    await expect(allTab).toHaveAttribute("aria-selected", "false");

    await expect(
      page.getByTestId("tutorial-card").filter({ hasText: "Create a repository in local Gitea" }),
    ).toBeVisible();
    await expect(
      page.getByTestId("tutorial-card").filter({ hasText: "Create an issue with template on GitHub" }),
    ).not.toBeVisible();

    // 8. Test status filtering: click "Outdated" tab
    await outdatedTab.click();
    await expect(outdatedTab).toHaveAttribute("aria-selected", "true");

    await expect(
      page.getByTestId("tutorial-card").filter({ hasText: "Create an issue with template on GitHub" }),
    ).toBeVisible();
    await expect(
      page.getByTestId("tutorial-card").filter({ hasText: "Create a repository in local Gitea" }),
    ).not.toBeVisible();

    // 9. Reset to "All" tab
    await allTab.click();
    await expect(allTab).toHaveAttribute("aria-selected", "true");
    await expect(giteaCard).toBeVisible();

    // 10. Search with no matches to verify empty state and reset button
    await searchInput.fill("nonexistent-tutorial-xyz-12345");
    const emptyState = page.getByTestId("empty-tutorials");
    await expect(emptyState).toBeVisible();
    await expect(page.getByText(/No tutorials match your search or filter/i)).toBeVisible();

    const resetBtn = page.getByTestId("reset-filters-btn");
    await expect(resetBtn).toBeVisible();
    await resetBtn.click();

    // Reset restores all cards
    await expect(searchInput).toHaveValue("");
    await expect(giteaCard).toBeVisible();

    // 11. Click "Open Tutorial" and verify navigation into interactive player
    const openLink = giteaCard.getByTestId("tutorial-card-open");
    await expect(openLink).toBeVisible();
    await openLink.click();

    // Assert navigation to player route /tutorials/[id]
    await expect(page).toHaveURL(/\/tutorials\/.+/);
    const playerRoot = page.getByTestId("tutorial-player-root");
    await expect(playerRoot).toBeVisible();
  });
});
