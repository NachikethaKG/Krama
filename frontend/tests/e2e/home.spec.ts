import { expect, test } from "@playwright/test";

// #318: the signed-in home is the prompt, not a landing page.
test("home asks what to learn and has no testing targets", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("app-header")).toBeVisible();
  await expect(page.getByLabel("What do you want to learn?")).toBeVisible();
  await expect(page.getByTestId("example-prompts")).toBeVisible();
  // No testing targets in the prompt box (recent tutorials may still be Gitea ones in mock data)
  await expect(page.getByTestId("task-input-section").getByText(/Gitea|Custom Target|Target environment/i)).toHaveCount(0);
  await expect(page.getByText("Systems Operational")).toHaveCount(0);
});

test("the website comes from the prompt, or from one question", async ({ page }) => {
  await page.goto("/");
  const prompt = page.getByTestId("task-prompt-input");

  await prompt.fill("Show me how to add a label on GitHub");
  await expect(page.getByTestId("detected-site")).toHaveText(/GitHub/);

  await prompt.fill("Create a project on gitlab.com");
  await expect(page.getByTestId("site-unsupported")).toContainText("gitlab.com");
  await expect(page.getByTestId("submit-task-btn")).toBeDisabled();

  await prompt.fill("Create a repository named demo");
  await expect(page.getByTestId("site-question")).toBeVisible();
});
