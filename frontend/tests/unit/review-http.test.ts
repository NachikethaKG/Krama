import { readFileSync } from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError, HttpApiClient } from "@/lib/api";

// The contract fixture (contracts/fixtures/reviews): one ReviewItem per category, as the backend sends them.
const FIXTURE = JSON.parse(
  readFileSync(path.resolve(__dirname, "../../../contracts/fixtures/reviews/review-queue.json"), "utf-8"),
);

function respond(body: unknown, status = 200) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
}

describe("HttpApiClient review queue (#377)", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("maps the contract's review items to the queue UI", async () => {
    respond(FIXTURE);
    const items = await new HttpApiClient("http://api/api/v1").getReviewQueue();

    expect(items.map((i) => i.category)).toEqual(["heal_pending", "outdated", "cant_check", "unstable"]);
    const heal = items[0];
    expect(heal.workflowId).toBe(FIXTURE.items[0].workflow_id);
    expect(heal.pendingVersion).toBe("v2");
    expect(heal.currentVersion).toBe("v1");
    expect(heal.failedStepIndex).toBe(4);
    expect(heal.stepDiffs?.length).toBeGreaterThan(0);
    expect(items[1].canRetryAiFix).toBe(true);
    expect(items[2].canRetryAiFix).toBe(false);
    expect(fetch).toHaveBeenCalledWith("http://api/api/v1/reviews", expect.anything());
  });

  it("never shows mock items when the server fails", async () => {
    respond({ error: { code: "internal", message: "boom" } }, 500);
    await expect(new HttpApiClient("http://api/api/v1").getReviewQueue()).rejects.toBeInstanceOf(ApiRequestError);
    await expect(new HttpApiClient("http://api/api/v1").getReviewQueueCount()).rejects.toBeInstanceOf(
      ApiRequestError,
    );
  });

  it("never pretends an accept worked", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    await expect(new HttpApiClient("http://api/api/v1").acceptReview("heal_pending:x")).rejects.toThrow();
  });

  it("returns the server's message after accepting", async () => {
    respond({ workflow_id: "w1", workflow_status: "verified", revision: 2, message: "Version 2 is now live." });
    await expect(new HttpApiClient("http://api/api/v1").acceptReview("heal_pending:x")).resolves.toEqual({
      success: true,
      message: "Version 2 is now live.",
      workflow_id: "w1",
    });
  });

  it("starts a real reverify run for 'retry check'", async () => {
    respond({ id: "r1", plan_id: "p1", plan_revision: 1, status: "queued", retry_count: 0, created_at: "x" }, 202);
    const run = await new HttpApiClient("http://api/api/v1").reverifyWorkflow("w1");
    expect(run.id).toBe("r1");
    expect(fetch).toHaveBeenCalledWith(
      "http://api/api/v1/workflows/w1/reverify",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
