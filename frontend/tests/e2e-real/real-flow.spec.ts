import { expect, test, type Page } from "@playwright/test";

// REAL e2e: drives the UI against the real backend. Opt-in, because it needs the whole stack and spends real
// LLM quota (one planning call, plus replans if a step fails):
//
//   docker compose up -d postgres gitea           # Gitea on :3001 with the `demo` user
//   cd backend && uv run alembic upgrade head
//   uv run uvicorn app.main:app --port 8000 --loop app.dev_loop:factory   # LLM_PROVIDER=gemini in .env
//   cd frontend && KRAMA_E2E_REAL=1 pnpm e2e:real  # starts `next dev` in http mode on :3000
//
// Flow: task → plan → approve → live view (run id) → run completed → verified workflow page with loading
// screenshots → the repository really exists in Gitea.

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1").replace(/\/+$/, "");
const GITEA_URL = (process.env.GITEA_URL ?? "http://localhost:3001").replace(/\/+$/, "");
const GITEA_USER = process.env.GITEA_DEMO_USER ?? "demo";
const GITEA_PASSWORD = process.env.GITEA_DEMO_PASSWORD ?? "demo-local-only";

test.skip(process.env.KRAMA_E2E_REAL !== "1", "Real full-stack e2e is opt-in: set KRAMA_E2E_REAL=1");

/** Answers any pause by allowing it (a create-repository task should not pause; if it does, the log says so). */
async function allowPauses(page: Page, log: string[]) {
  const modalAllow = page.getByTestId("modal-allow-btn");
  const bannerAllow = page.getByTestId("resume-run-btn");
  if (await modalAllow.isVisible().catch(() => false)) {
    log.push("allowed a policy pause (modal)");
    await modalAllow.click();
  } else if (await bannerAllow.isVisible().catch(() => false)) {
    if (await bannerAllow.isEnabled()) {
      const reason = await page.getByTestId("pause-banner").getAttribute("data-pause-reason");
      log.push(`allowed a pause: ${reason}`);
      await bannerAllow.click();
    }
  }
}

test("creates a Gitea repository through the real API and shows the verified workflow", async ({ page, request }) => {
  const health = await request.get(`${API_URL}/health`);
  expect(health.ok(), `backend not reachable at ${API_URL}/health`).toBeTruthy();
  const gitea = await request.get(`${GITEA_URL}/api/v1/version`);
  expect(gitea.ok(), `Gitea not reachable at ${GITEA_URL}`).toBeTruthy();

  const name = `e2e-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  const apiResponses: string[] = [];
  page.on("response", (res) => {
    if (res.url().startsWith(API_URL) && res.status() >= 400) apiResponses.push(`${res.status()} ${res.request().method()} ${res.url()}`);
  });

  // 1. Task → planning (real LLM, 15-60 s) → plan
  await page.goto("/");
  await page.getByTestId("task-prompt-input").fill(`Create a repository called ${name}`);
  await page.getByTestId("target-url-input").fill(GITEA_URL);
  await page.getByTestId("submit-task-btn").click();
  await expect(page.getByTestId("task-planning-status")).toBeVisible({ timeout: 30_000 });

  const approval = page.getByTestId("approval-screen");
  const clarify = page.getByTestId("task-clarify-input");
  const taskError = page.getByTestId("task-error-banner");
  await expect(approval.or(clarify).or(taskError)).toBeVisible({ timeout: 200_000 });
  if (await clarify.isVisible()) {
    await clarify.fill(name);
    await page.getByTestId("task-clarify-submit").click();
    await expect(approval.or(taskError)).toBeVisible({ timeout: 200_000 });
  }
  await expect(taskError, "planning failed").toHaveCount(0);
  await expect(page).toHaveURL(/\/workflows\/[0-9a-f-]{36}\/approval$/);
  await expect(page.getByTestId("task-prompt")).toContainText(name);
  const stepCount = await page.getByTestId("step-item").count();
  expect(stepCount).toBeGreaterThan(0);

  // 2. Approve → the live view is keyed by the RUN id returned by POST /plans/{id}/approve
  await page.getByTestId("approve-btn").click();
  await expect(page).toHaveURL(/\/runs\/[0-9a-f-]{36}\/live$/, { timeout: 30_000 });
  const runId = /\/runs\/([0-9a-f-]{36})\/live/.exec(page.url())![1];
  await expect(page.getByTestId("live-execution-view")).toHaveAttribute("data-run-id", runId);

  // 3. Step events arrive over SSE
  await expect(page.locator('[data-testid="step-progress-item"][data-step-status="verified"]').first()).toBeVisible({
    timeout: 180_000,
  });

  // 4. Run completes (answer any pause; fail fast on a failed / cancelled run)
  const log: string[] = [];
  const deadline = Date.now() + 8 * 60_000;
  const status = page.getByTestId("execution-status-badge");
  for (;;) {
    const s = await status.getAttribute("data-status");
    if (s === "completed") break;
    if (s === "failed" || s === "cancelled") {
      const msg = (await page.getByTestId("failure-message").textContent().catch(() => null)) ?? "";
      const stop = (await page.getByTestId("automation-restricted-screen").textContent().catch(() => null)) ?? "";
      throw new Error(`run ${runId} ended ${s}: ${msg || stop}\nAPI errors: ${apiResponses.join("; ")}\n${log.join("\n")}`);
    }
    if (Date.now() > deadline) throw new Error(`run ${runId} did not finish in time (status ${s})`);
    if (s === "paused") await allowPauses(page, log);
    await page.waitForTimeout(1000);
  }
  await expect(page.getByTestId("completion-banner")).toBeVisible();
  await expect(page.getByTestId("execution-error-banner")).toHaveCount(0);
  if (log.length) console.log(`pauses answered: ${log.join("; ")}`);

  // 5. Verified workflow page: verified steps with screenshots that load from the API's artifact store
  await page.getByTestId("view-workflow-link").click();
  await expect(page).toHaveURL(new RegExp(`/runs/${runId}$`));
  await expect(page.getByTestId("step-evidence-list")).toBeVisible({ timeout: 30_000 });
  const cards = page.locator('[data-testid^="step-evidence-card-"]');
  const cardCount = await cards.count();
  expect(cardCount).toBeGreaterThan(0);
  for (let i = 0; i < cardCount; i++) {
    await expect(cards.nth(i).getByTestId("step-status")).toHaveAttribute("data-status", "verified");
  }
  const shots = page.getByTestId("step-screenshot");
  expect(await shots.count()).toBeGreaterThan(0);
  for (let i = 0; i < (await shots.count()); i++) {
    const img = shots.nth(i);
    await expect(img).toHaveAttribute("src", new RegExp(`^${API_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/artifacts/`));
    await expect
      .poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0), { timeout: 15_000 })
      .toBe(true);
  }
  await expect(page.getByTestId("step-screenshot-placeholder")).toHaveCount(0);

  // 6. The repository really exists in Gitea
  const repo = await request.get(`${GITEA_URL}/api/v1/repos/${GITEA_USER}/${name}`, {
    headers: { Authorization: `Basic ${Buffer.from(`${GITEA_USER}:${GITEA_PASSWORD}`).toString("base64")}` },
  });
  expect(repo.status(), `GET /api/v1/repos/${GITEA_USER}/${name}`).toBe(200);
});
