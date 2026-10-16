import { defineConfig, devices } from "@playwright/test";

// REAL full-stack e2e: the UI against the real backend (API on :8000, Gitea on :3001, real LLM planning).
// Opt-in: `KRAMA_E2E_REAL=1 pnpm e2e:real` (see tests/e2e-real/real-flow.spec.ts for what must be running).
// It starts its own `next dev` in http mode on :3000 (the backend's CORS allows http://localhost:3000), so port
// 3000 must be free: an already running mock-mode dev server would silently make this a mock test.
export default defineConfig({
  testDir: "./tests/e2e-real",
  timeout: 10 * 60_000,
  retries: 0,
  workers: 1,
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: false,
    timeout: 180_000,
    env: {
      NEXT_PUBLIC_API_MODE: "http",
      NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
    },
  },
});
