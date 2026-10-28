import { expect, test } from "@playwright/test";

test.describe("Authentication, Route Protection, and User Dashboard", () => {
  test("redirects unauthenticated user to /login and allows login with seeded credentials", async ({
    page,
    context,
  }) => {
    // 1. Clear all cookies to simulate an unauthenticated user
    await context.clearCookies();

    // 2. Attempt navigating directly to protected route /dashboard
    await page.goto("/dashboard");

    // 3. Verify route protection middleware redirects to /login with 'from' parameter
    await expect(page).toHaveURL(/\/login\?from=%2Fdashboard/);

    // 4. Assert login page elements are visible
    const heading = page.getByRole("heading", { name: /Sign in to Krama/i });
    await expect(heading).toBeVisible();

    const emailInput = page.getByTestId("login-email");
    const passwordInput = page.getByTestId("login-password");
    const submitBtn = page.getByTestId("login-submit");

    await expect(emailInput).toBeVisible();
    await expect(passwordInput).toBeVisible();
    await expect(submitBtn).toBeVisible();

    // 5. Click "Fill credentials" button to populate seeded credentials
    const fillBtn = page.getByTestId("use-demo-creds-btn");
    await expect(fillBtn).toBeVisible();
    await fillBtn.click();

    await expect(emailInput).toHaveValue("demo@krama.dev");
    await expect(passwordInput).toHaveValue("krama-demo-pass");

    // 6. Submit the form
    await submitBtn.click();

    // 7. /dashboard is now the home screen (#318): the prompt and recent tutorials, under the app header
    await expect(page).toHaveURL(/localhost:3000\/$/);
    await expect(page.getByTestId("user-email-display")).toHaveText("demo@krama.dev");
    await expect(page.getByLabel("What do you want to learn?")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Recent tutorials/i })).toBeVisible();

    // 9. Test Logout action
    const logoutBtn = page.getByTestId("dashboard-logout-btn");
    await expect(logoutBtn).toBeVisible();
    await logoutBtn.click();

    // Redirects back to /login
    await expect(page).toHaveURL(/\/login/);
  });

  test("displays informational registration page with seeded credentials on /signup", async ({
    page,
    context,
  }) => {
    // Authenticated users are redirected away from /signup to the home screen
    await page.goto("/signup");
    await expect(page).toHaveURL(/localhost:3000\/$/);

    // Unauthenticated visitors see the informational signup notice
    await context.clearCookies();
    await page.goto("/signup");

    const heading = page.getByRole("heading", { name: /Public Registration Closed/i });
    await expect(heading).toBeVisible();

    await expect(page.getByText(/demo@krama.dev/)).toBeVisible();
    await expect(page.getByText(/KRAMA_DEMO_PASSWORD in .env/)).toBeVisible(); // never a real password (#104)

    const signInLink = page.getByTestId("signup-login-link");
    await expect(signInLink).toBeVisible();
    await signInLink.click();

    await expect(page).toHaveURL(/\/login/);
  });
});
