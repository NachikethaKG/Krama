import { defineConfig, devices } from "@playwright/test";

// Frontend e2e runs against mock API mode, so no backend is needed. The real-backend e2e is separate:
// playwright.real.config.ts (`KRAMA_E2E_REAL=1 pnpm e2e:real`).
// First run: `pnpm exec playwright install chromium`
export default defineConfig({
  testDir: "./tests/e2e",
  use: {
    baseURL: "http://localhost:3000",
    storageState: {
      cookies: [
        {
          name: "krama_session",
          value: "mock-session-token",
          domain: "localhost",
          path: "/",
          expires: -1,
          httpOnly: false,
          secure: false,
          sameSite: "Lax",
        },
      ],
      origins: [],
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    // CI runs `pnpm -r build` first, so serve that build: `next dev` compiles each route on its first visit
    // (measured cold: 30 s for /, 14 s for /tasks), which made tests time out at random on CI runners.
    command: process.env.CI ? "pnpm start --port 3000" : "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    env: { NEXT_PUBLIC_API_MODE: "mock" },
  },
});
