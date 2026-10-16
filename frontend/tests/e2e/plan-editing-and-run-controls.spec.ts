import { expect, test } from "@playwright/test";

test.describe("Workflow Plan Editing Flow", () => {
  test("allows reordering, deleting, and editing step instructions before approval", async ({
    page,
  }) => {
    // 1. Navigate to approval route
    await page.goto("/workflows/default/approval");

    // 2. Initial state verification
    const stepItems = page.getByTestId("step-item");
    await expect(stepItems).toHaveCount(5);

    const editBtn = page.getByTestId("edit-btn");
    await expect(editBtn).toHaveText("Edit Plan");

    // 3. Enter edit mode
    await editBtn.click();
    await expect(editBtn).toHaveText("Done Editing");

    // Verify move buttons and delete buttons are visible in edit mode
    const moveDownBtn1 = page.getByTestId("move-step-down-1");
    await expect(moveDownBtn1).toBeVisible();

    const deleteBtn3 = page.getByTestId("delete-step-3");
    await expect(deleteBtn3).toBeVisible();

    // 4. Reorder: move step 1 down
    await moveDownBtn1.click();
    const input1 = page.getByTestId("step-input-1");
    await expect(input1).toHaveValue(/Click New Repository/i);

    // 5. Delete step 3
    await deleteBtn3.click();
    await expect(page.getByTestId("step-item")).toHaveCount(4);

    // 6. Edit instruction text of step 1 inline
    await input1.fill("E2E custom updated instruction for repository creation");

    // 7. Click Done Editing to save the plan updates
    await editBtn.click();
    await expect(editBtn).toHaveText("Edit Plan");

    // Verify updated instruction is rendered
    await expect(
      page.getByText("E2E custom updated instruction for repository creation")
    ).toBeVisible();

    // 8. Approve the edited plan and verify transition
    const approveBtn = page.getByTestId("approve-btn");
    await approveBtn.click();

    await expect(page).toHaveURL(/\/runs\/mock-run-id\/live$/, { timeout: 10000 });
  });
});

test.describe("Workflow Run Controls & Lifecycle States", () => {
  test("allows cancelling an active run and verifies cancelled state banner", async ({
    page,
  }) => {
    // 1. Navigate to live execution view with moderate replay speed
    await page.goto("/runs/default/live?speed=5");

    // 2. Verify cancel run button is accessible during active execution
    const cancelBtn = page.getByTestId("cancel-run-btn");
    await expect(cancelBtn).toBeVisible({ timeout: 5000 });

    // 3. User clicks Cancel Run
    await cancelBtn.click();

    // 4. Verify cancelled banner appears and execution halts
    const cancelledBanner = page.getByTestId("cancelled-banner");
    await expect(cancelledBanner).toBeVisible();
    await expect(cancelledBanner).toContainText(/Workflow Execution Cancelled/i);

    // 5. Verify status badge indicates cancelled
    const statusBadge = page.getByTestId("execution-status-badge");
    await expect(statusBadge).toHaveAttribute("data-status", "cancelled");

    // 6. Back to Plan and New Task are available; a cancelled run is not restarted in place
    const backToPlanBtn = cancelledBanner.getByTestId("back-to-plan-btn");
    await expect(backToPlanBtn).toBeVisible();
    await expect(backToPlanBtn).toHaveAttribute("href", "/workflows/default/approval");
    await expect(cancelledBanner.getByTestId("new-task-link")).toBeVisible();
    await expect(cancelledBanner.getByTestId("retry-run-btn")).toHaveCount(0);
  });

  test("handles pause state denial by halting and showing cancelled state", async ({
    page,
  }) => {
    // 1. The "replan" run pauses with recovery_exhausted (banner pause)
    await page.goto("/runs/replan/live?speed=50");

    // 2. Wait for pause banner to appear
    const pauseBanner = page.getByTestId("pause-banner");
    await expect(pauseBanner).toBeVisible({ timeout: 10000 });
    await expect(pauseBanner).toHaveAttribute("data-pause-reason", "recovery_exhausted");

    // 3. Verify Confirm & Resume and Deny / Abort controls
    const resumeBtn = page.getByTestId("resume-run-btn");
    const denyBtn = page.getByTestId("deny-run-btn");
    await expect(resumeBtn).toBeVisible();
    await expect(denyBtn).toBeVisible();

    // 4. Click Deny / Abort
    await denyBtn.click();

    // 5. Pause banner dismisses and cancelled banner is shown
    await expect(pauseBanner).not.toBeVisible();
    const cancelledBanner = page.getByTestId("cancelled-banner");
    await expect(cancelledBanner).toBeVisible();
    await expect(page.getByTestId("execution-status-badge")).toHaveAttribute(
      "data-status",
      "cancelled"
    );
  });
});
