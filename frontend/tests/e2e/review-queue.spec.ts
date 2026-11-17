import { expect, test } from "@playwright/test";

test.describe("Owner Review Queue, Nav Badge, and Triage Actions", () => {
  test("unauthenticated access to /dashboard/reviews redirects to /login", async ({
    page,
    context,
  }) => {
    // 1. Clear cookies to simulate unauthenticated visitor
    await context.clearCookies();

    // 2. Navigate directly to /dashboard/reviews
    await page.goto("/dashboard/reviews");

    // 3. Verify middleware redirects to /login with from query param
    await expect(page).toHaveURL(/\/login\?from=%2Fdashboard%2Freviews/);
    await expect(page.getByRole("heading", { name: /Sign in to Krama/i })).toBeVisible();
  });

  test("authenticated owner reviews items, inspects step diffs, and decrements nav badge upon Accept", async ({
    page,
    context,
  }) => {
    // 1. Authenticate with seeded session cookie
    await context.addCookies([
      {
        name: "krama_session",
        value: "demo-mock-token",
        domain: "localhost",
        path: "/",
      },
    ]);

    // 2. Visit dashboard reviews page directly
    await page.goto("/dashboard/reviews");
    await expect(page).toHaveURL(/\/dashboard\/reviews/);

    // 3. Verify Review Queue view mounted and page heading rendered
    const view = page.getByTestId("review-queue-view");
    await expect(view).toBeVisible();
    await expect(page.getByRole("heading", { name: /Owner Review Queue/i })).toBeVisible();

    // 4. Verify Nav Count Badge in header displays initial count (4)
    const navBadge = page.getByTestId("review-queue-badge").first();
    await expect(navBadge).toBeVisible();
    await expect(navBadge).toHaveText("4");

    // 5. Verify all 4 category items are rendered initially
    const cards = page.getByTestId("review-queue-card");
    await expect(cards).toHaveCount(4);

    // 6. Test category filtering: Select "Pending Heal" tab
    const healTab = page.getByTestId("filter-tab-heal_pending");
    await healTab.click();

    // Only 1 item should be visible in Pending Heal category
    await expect(cards).toHaveCount(1);
    const healCard = cards.first();
    await expect(healCard).toHaveAttribute("data-category", "heal_pending");
    await expect(healCard.getByText("Heal Pending")).toBeVisible();

    // 7. Inspect Step-by-Step Diff on heal_pending item
    const diffViewer = healCard.getByTestId("step-diff-viewer");
    await expect(diffViewer).toBeVisible();

    // Assert selector diff highlight
    const oldSelector = diffViewer.getByTestId("diff-old-selector").first();
    const newSelector = diffViewer.getByTestId("diff-new-selector").first();
    await expect(oldSelector).toBeVisible();
    await expect(oldSelector).toHaveClass(/line-through/);
    await expect(newSelector).toBeVisible();
    await expect(newSelector).toHaveClass(/text-emerald/);

    // 8. Triage action: Click Accept
    const acceptBtn = healCard.getByTestId("action-accept");
    await expect(acceptBtn).toBeVisible();
    await acceptBtn.click();

    // 9. Verify toast confirmation surfaces ("Healed version is now live")
    const toast = page.getByTestId("review-queue-toast");
    await expect(toast).toBeVisible();
    await expect(toast).toHaveText(/Healed version is now live/i);

    // 10. Verify nav count badge decrements from 4 to 3
    await expect(navBadge).toHaveText("3");

    // 11. Reset filter to All tab and assert remaining 3 items
    const allTab = page.getByTestId("filter-tab-all");
    await allTab.click();
    await expect(cards).toHaveCount(3);
  });
});
