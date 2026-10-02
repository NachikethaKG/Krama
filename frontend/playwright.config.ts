import { defineConfig, devices } from "@playwright/test";

// Frontend e2e runs against mock API mode, so no backend is needed.
// First run: `pnpm exec playwright install chromium`
export default defineConfig({
  testDir: "./tests/e2e",
  use: { baseURL: "http://localhost:3000" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    env: { NEXT_PUBLIC_API_MODE: "mock" },
  },
});
