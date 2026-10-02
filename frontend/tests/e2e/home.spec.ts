import { expect, test } from "@playwright/test";

test("home page loads and reports API status", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Krama" })).toBeVisible();
  await expect(page.getByRole("status")).toHaveText(/API ok/);
});
