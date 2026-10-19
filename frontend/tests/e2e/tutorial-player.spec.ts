import { expect, test } from "@playwright/test";

test.describe("Interactive Tutorial Player", () => {
  test("renders tutorial player, advances through steps, updates captions, and toggles auto-zoom", async ({
    page,
    context,
  }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);

    // 1. Navigate to the tutorial player page
    await page.goto("/tutorials");

    // 2. Assert tutorial root and header elements are visible
    const root = page.getByTestId("tutorial-player-root");
    await expect(root).toBeVisible();

    const title = page
      .locator("header")
      .getByRole("heading", {
        name: /Create a repository in local Gitea/i,
        level: 1,
      });
    await expect(title).toBeVisible();

    // 3. Assert playback controls are visible
    const controls = page.getByTestId("tutorial-controls");
    await expect(controls).toBeVisible();

    const playPauseBtn = page.getByTestId("control-play-pause");
    await expect(playPauseBtn).toBeVisible();

    const prevBtn = page.getByTestId("control-prev-step");
    await expect(prevBtn).toBeVisible();

    const nextBtn = page.getByTestId("control-next-step");
    await expect(nextBtn).toBeVisible();

    const muteBtn = page.getByTestId("control-toggle-mute");
    await expect(muteBtn).toBeVisible();

    // 4. Assert stage, camera viewport, and step 1 caption
    const stage = page.getByTestId("tutorial-stage-container");
    await expect(stage).toBeVisible();

    const cameraViewport = page.getByTestId("camera-viewport");
    await expect(cameraViewport).toBeVisible();
    // Default zoom is enabled (scale 1.35)
    await expect(cameraViewport).toHaveCSS("transform", /matrix/);

    const caption = page.getByTestId("tutorial-caption");
    await expect(caption).toBeVisible();
    await expect(caption).toContainText("Open the + menu at the top right.");

    // Assert screen reader announcement
    const announcer = page.getByTestId("screen-reader-announcer");
    await expect(announcer).toContainText("Step 1 of 5: Open the + menu at the top right.");

    // 5. Assert step list sidebar renders all 5 steps
    const stepList = page.getByTestId("step-list");
    await expect(stepList).toBeVisible();

    for (let seq = 1; seq <= 5; seq++) {
      const stepItem = page.getByTestId(`step-item-${seq}`);
      await expect(stepItem).toBeVisible();
    }

    // 6. Advance to Step 2 using Next button
    await nextBtn.click();
    await expect(controls.getByText("Step 2 of 5")).toBeVisible();
    await expect(caption).toContainText("Click New Repository in the menu.");
    await expect(announcer).toContainText("Step 2 of 5: Click New Repository in the menu.");

    // 7. Advance to Step 3 and verify input value is copyable
    await nextBtn.click();
    await expect(controls.getByText("Step 3 of 5")).toBeVisible();
    await expect(caption).toContainText("Enter demo-repo as the repository name.");

    const copyBtn = page.getByTestId("copy-button").first();
    await expect(copyBtn).toBeVisible();
    await copyBtn.click();
    await expect(page.getByText("Copied!").first()).toBeVisible();

    // 8. Jump to Step 4 via step list sidebar
    const step4 = page.getByTestId("step-item-4");
    await step4.click();
    await expect(controls.getByText("Step 4 of 5")).toBeVisible();
    await expect(caption).toContainText(
      "Check Initialize Repository to add .gitignore, License and README.",
    );

    // 9. Toggle Zoom to Overview (1.0x) and back
    const zoomToggle = page.getByTestId("control-toggle-zoom");
    await zoomToggle.click();
    await expect(zoomToggle).toHaveAttribute("aria-pressed", "false");
    await expect(cameraViewport).toHaveCSS("transform", "none");

    await zoomToggle.click();
    await expect(zoomToggle).toHaveAttribute("aria-pressed", "true");
    await expect(cameraViewport).toHaveCSS("transform", /matrix/);

    // 10. Toggle Audio Narration Mute
    await muteBtn.click();
    await expect(muteBtn).toHaveAttribute("aria-pressed", "false"); // Muted

    await muteBtn.click();
    await expect(muteBtn).toHaveAttribute("aria-pressed", "true"); // Active

    // 11. Toggle play/pause
    await playPauseBtn.click();
    await expect(playPauseBtn).toHaveAttribute("aria-label", /pause/i);

    await playPauseBtn.click();
    await expect(playPauseBtn).toHaveAttribute("aria-label", /play/i);
  });

  test("renders responsive mobile layout without overflow and supports step drawer", async ({
    page,
  }) => {
    // 1. Set mobile viewport: iPhone SE dimensions (375x667)
    await page.setViewportSize({ width: 375, height: 667 });

    // 2. Navigate to tutorial player
    await page.goto("/tutorials");

    const root = page.getByTestId("tutorial-player-root");
    await expect(root).toBeVisible();

    // 3. Verify no horizontal overflow occurs on phone width
    const scrollWidth = await page.evaluate(
      () => document.documentElement.scrollWidth,
    );
    const clientWidth = await page.evaluate(
      () => document.documentElement.clientWidth,
    );
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);

    // 4. Assert stage and controls render properly
    const stage = page.getByTestId("tutorial-stage-container");
    await expect(stage).toBeVisible();

    const controls = page.getByTestId("tutorial-controls");
    await expect(controls).toBeVisible();

    // 5. Open mobile step drawer
    const drawerToggle = page.getByTestId("mobile-step-drawer-toggle");
    await expect(drawerToggle).toBeVisible();
    await drawerToggle.click();

    const drawer = page.getByTestId("mobile-step-drawer");
    await expect(drawer).toBeVisible();

    // 6. Select Step 3 inside the mobile drawer
    const step3 = drawer.getByTestId("step-item-3");
    await expect(step3).toBeVisible();
    await step3.click();

    // Drawer closes after selecting step
    await expect(drawer).not.toBeVisible();
    await expect(controls.getByText("Step 3 of 5")).toBeVisible();

    // 7. Advance step on mobile using next button
    const nextBtn = page.getByTestId("control-next-step");
    await nextBtn.click();
    await expect(controls.getByText("Step 4 of 5")).toBeVisible();
  });
});
