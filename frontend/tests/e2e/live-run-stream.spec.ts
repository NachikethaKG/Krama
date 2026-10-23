import { expect, test } from "@playwright/test";

test.describe("Polished Live Agent View (/runs/[id])", () => {
  const sampleSseEvents = [
    `event: plan\ndata: {"steps":[{"seq":1,"instruction_text":"Navigate to repository dashboard"},{"seq":2,"instruction_text":"Select Settings danger zone"},{"seq":3,"instruction_text":"Delete repository"}],"target_url":"https://github.com/krama-org/demo-repo"}\n\n`,
    `event: step_started\ndata: {"step_seq":1}\n\n`,
    `event: screenshot\ndata: {"image_url":"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360'><rect width='640' height='360' fill='%230f172a'/><text x='50%25' y='50%25' fill='white' font-size='20' text-anchor='middle'>GitHub Repo Dashboard</text></svg>","step_seq":1,"timestamp_ms":1700000000000}\n\n`,
    `event: step_completed\ndata: {"step_seq":1,"duration_ms":1250}\n\n`,
    `event: step_started\ndata: {"step_seq":2}\n\n`,
    `event: paused\ndata: {"reason":"destructive_action","message":"Repository deletion requires human confirmation before continuing","step_seq":2,"trigger_context":"github_danger_zone"}\n\n`,
  ].join("");

  test("streams execution progress with live viewport, step checklist, and paused approval state", async ({
    page,
  }) => {
    // 1. Mock SSE stream endpoint
    await page.route("**/api/v1/runs/test-run-stream/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
        body: sampleSseEvents,
      });
    });

    let resumeHeaders: Record<string, string> = {};
    await page.route("**/api/v1/runs/test-run-stream/resume", async (route) => {
      resumeHeaders = route.request().headers();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "resumed" }),
      });
    });

    // 2. Navigate to stream live run page
    await page.goto("/runs/test-run-stream");

    // 3. Verify Observer Layout and Header elements
    await expect(page.getByTestId("live-agent-observer-view")).toBeVisible();
    await expect(page.getByTestId("run-detail-id")).toHaveText("test-run-stream");
    await expect(page.getByTestId("run-detail-prompt")).toContainText("demo-repo");

    // 4. Verify Live Viewport Stream elements
    const viewport = page.getByTestId("live-viewport-stream");
    await expect(viewport).toBeVisible();
    await expect(page.getByTestId("live-indicator-badge")).toHaveText("LIVE HEADLESS");
    await expect(page.getByTestId("live-dot")).toBeVisible();
    await expect(page.getByTestId("stream-target-url")).toHaveText("https://github.com/krama-org/demo-repo");

    // Verify screenshot was rendered
    const liveImg = page.getByTestId("live-stream-image");
    await expect(liveImg).toBeVisible();
    await expect(liveImg).toHaveAttribute("src", /^data:image\/svg\+xml/);

    // 5. Verify Real-Time Step Checklist
    const checklist = page.getByTestId("step-checklist");
    await expect(checklist).toBeVisible();
    await expect(page.getByTestId("step-count-badge")).toHaveText("3");

    // Step 1: Completed with duration
    const step1 = page.getByTestId("step-checklist-item-1");
    await expect(step1).toBeVisible();
    await expect(step1.getByTestId("step-completed")).toBeVisible();
    await expect(step1).toContainText("1.3s"); // 1250ms rounds to 1.3s

    // Step 2: Paused status
    const step2 = page.getByTestId("step-checklist-item-2");
    await expect(step2).toBeVisible();
    await expect(step2.getByTestId("step-paused")).toBeVisible();

    // Step 3: Pending status
    const step3 = page.getByTestId("step-checklist-item-3");
    await expect(step3).toBeVisible();
    await expect(step3.getByTestId("step-pending")).toBeVisible();

    // 6. Verify Actionable Paused Banner
    const pausedBanner = page.getByTestId("paused-banner");
    await expect(pausedBanner).toBeVisible();
    await expect(pausedBanner).toContainText("Execution Paused: Action requires manual approval / bot barrier detected");
    await expect(pausedBanner).toContainText("Repository deletion requires human confirmation before continuing");
    await expect(pausedBanner).toContainText("github_danger_zone");

    // 7. Click Allow & Resume and verify X-Krama: 1 header was sent
    const resumeBtn = page.getByTestId("allow-resume-button");
    await expect(resumeBtn).toBeVisible();
    await resumeBtn.click();

    // Verify header X-Krama: 1
    expect(resumeHeaders["x-krama"]).toBe("1");

    // Paused banner disappears on resume
    await expect(pausedBanner).not.toBeVisible();
  });

  test("handles execution failure with expected vs observed diff card", async ({ page }) => {
    const failedSseEvents = [
      `event: plan\ndata: {"steps":[{"seq":1,"instruction_text":"Click on submit button"}],"target_url":"https://github.com"}\n\n`,
      `event: step_started\ndata: {"step_seq":1}\n\n`,
      `event: failed\ndata: {"step_seq":1,"error":"Element button#submit not clickable","expected":{"state":"visible_and_enabled"},"observed":{"state":"disabled_by_form_validation"}}\n\n`,
    ].join("");

    await page.route("**/api/v1/runs/failed-run-stream/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
        },
        body: failedSseEvents,
      });
    });

    await page.goto("/runs/failed-run-stream");

    // Failed banner is rendered
    const failedBanner = page.getByTestId("failed-banner");
    await expect(failedBanner).toBeVisible();
    await expect(failedBanner).toContainText("Execution Failed at Step 1: Element button#submit not clickable");

    // Expected vs Observed diff card
    const diffCard = page.getByTestId("expected-observed-card");
    await expect(diffCard).toBeVisible();
    await expect(diffCard).toContainText("visible_and_enabled");
    await expect(diffCard).toContainText("disabled_by_form_validation");

    // Step checklist item 1 marked as failed
    const step1 = page.getByTestId("step-checklist-item-1");
    await expect(step1.getByTestId("step-failed")).toBeVisible();
  });

  test("resilient to connection drop and shows reconnecting indicator without UI crashes", async ({
    page,
  }) => {
    let connectionAttempts = 0;

    await page.route("**/api/v1/runs/drop-run-stream/stream", async (route) => {
      connectionAttempts++;
      if (connectionAttempts === 1) {
        // Drop first connection by closing immediately or returning 500
        await route.fulfill({
          status: 500,
          contentType: "text/plain",
          body: "Internal Server Error",
        });
      } else {
        // Reconnection succeeds
        await route.fulfill({
          status: 200,
          headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
          },
          body: `event: plan\ndata: {"steps":[{"seq":1,"instruction_text":"Reconnected step"}]}\n\n`,
        });
      }
    });

    await page.goto("/runs/drop-run-stream");

    // Observer view loads safely without crashing
    await expect(page.getByTestId("live-agent-observer-view")).toBeVisible();

    // Reconnecting banner appears when drop is detected
    const reconnectingBanner = page.getByTestId("stream-reconnecting-banner");
    await expect(reconnectingBanner).toBeVisible();
    await expect(reconnectingBanner).toContainText("Stream connection lost. Reconnecting to live observer stream…");
  });
});
