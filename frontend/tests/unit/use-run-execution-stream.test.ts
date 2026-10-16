import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RunEvent } from "@krama/contracts-ts";

import { useRunExecutionStream } from "@/hooks/useRunExecutionStream";
import { ApiRequestError, MockApiClient, type StreamOptions } from "@/lib/api";
import { giteaEventsFixture } from "@/lib/fixtures";

const FAST = 1000;

function hook(runId: string, client = new MockApiClient(), autoStart = true) {
  return renderHook(() => useRunExecutionStream({ runId, client, speed: FAST, autoStart }));
}

describe("useRunExecutionStream", () => {
  it("loads Run → Plan (via run.plan_id) → Task and shows pending steps before streaming", async () => {
    const client = new MockApiClient();
    const getPlan = vi.spyOn(client, "getPlan");
    const { result } = hook("paused", client, false);

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(getPlan).toHaveBeenCalledWith("paused");
    expect(result.current.run?.id).toBe("paused");
    expect(result.current.runStatus).toBe("queued");
    expect(result.current.steps).toHaveLength(5);
    expect(result.current.steps.every((s) => s.status === "pending")).toBe(true);
    await waitFor(() => expect(result.current.task?.target_url).toBe("http://localhost:3001"));
  });

  it("streams the RUN's events through completion", async () => {
    const client = new MockApiClient();
    const stream = vi.spyOn(client, "streamRunEvents");
    const { result } = hook("default", client);

    await waitFor(() => expect(result.current.runStatus).toBe("completed"), { timeout: 4000 });
    expect(stream.mock.calls[0][0]).toBe("default");
    expect(result.current.verifiedCount).toBe(5);
    expect(result.current.progressPercent).toBe(100);
    expect(result.current.workflowId).toBe(giteaEventsFixture.at(-1)?.type === "run.completed" ? "6f1c2a4e-1111-4b8a-9a1b-123456789abc" : null);
    expect(result.current.steps[0].screenshotUrl).toBe("/screenshots/step-1.png");
  });

  it("answers a pause with the paused step_seq, once, and follows the server's events", async () => {
    const client = new MockApiClient();
    const confirm = vi.spyOn(client, "confirmRun");
    const { result } = hook("paused", client);

    await waitFor(() => expect(result.current.pauseDetails?.reason).toBe("destructive_action"), { timeout: 4000 });
    expect(result.current.pauseDetails?.stepSeq).toBe(2);

    await act(async () => {
      // A double click must not send two answers.
      await Promise.all([result.current.resume(), result.current.resume()]);
    });
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(confirm).toHaveBeenCalledWith("paused", 2, "allow");

    await waitFor(() => expect(result.current.runStatus).toBe("completed"), { timeout: 4000 });
    expect(result.current.pauseDetails).toBeNull();
  });

  it("deny ends the run as cancelled", async () => {
    const client = new MockApiClient();
    const { result } = hook("paused", client);
    await waitFor(() => expect(result.current.pauseDetails).not.toBeNull(), { timeout: 4000 });

    await act(async () => {
      await result.current.deny();
    });
    await waitFor(() => expect(result.current.runStatus).toBe("cancelled"));
  });

  it("keeps the pause and shows an error when /confirm fails (no optimistic state)", async () => {
    const client = new MockApiClient();
    client.confirmRun = async () => {
      throw new ApiRequestError("Run is running, not paused at step 2", 409, {
        code: "run_not_active",
        message: "Run is running, not paused at step 2",
      });
    };
    const { result } = hook("paused", client);
    await waitFor(() => expect(result.current.pauseDetails).not.toBeNull(), { timeout: 4000 });

    await act(async () => {
      await result.current.resume();
    });
    expect(result.current.error).toMatch(/no longer waiting/i);
    expect(result.current.runStatus).toBe("paused");
    expect(result.current.pauseDetails?.stepSeq).toBe(2);
    expect(result.current.isConfirming).toBe(false);
  });

  it("shows an error and keeps the status when /cancel fails", async () => {
    const client = new MockApiClient();
    client.cancelRun = async () => {
      throw new ApiRequestError("Run already verified", 409, { code: "run_not_active", message: "Run already verified" });
    };
    const { result } = hook("paused", client);
    await waitFor(() => expect(result.current.pauseDetails).not.toBeNull(), { timeout: 4000 });

    await act(async () => {
      await result.current.cancel();
    });
    expect(result.current.error).toMatch(/already finished/i);
    expect(result.current.runStatus).toBe("paused");
    expect(result.current.isCancelling).toBe(false);
  });

  it("replan_review: loads the proposed plan from plan_id, and allow switches to its steps", async () => {
    const client = new MockApiClient();
    const { result } = hook("replan-review", client);

    await waitFor(() => expect(result.current.proposedPlan?.plan?.id).toBe("6f1c2a4e-4444-4b8a-9a1b-123456789abc"), { timeout: 4000 });
    expect(result.current.pauseDetails?.reason).toBe("replan_review");
    expect(result.current.replanState.status).not.toBe("exhausted");
    expect(result.current.proposedPlan?.steps[0]).toMatchObject({ seq: 2, instruction_text: "Open the New Repository page directly." });

    await act(async () => {
      await result.current.resume();
    });
    await waitFor(() => expect(result.current.runStatus).toBe("completed"), { timeout: 4000 });
    expect(result.current.steps.find((s) => s.seq === 2)?.instructionText).toBe("Open the New Repository page directly.");
  });

  it("recovery_exhausted marks the replan state exhausted", async () => {
    const { result } = hook("replan");
    await waitFor(() => expect(result.current.pauseDetails?.reason).toBe("recovery_exhausted"), { timeout: 4000 });
    expect(result.current.replanState.status).toBe("exhausted");
  });

  it("a policy stop arrives as run.failed with details.reason policy_stop", async () => {
    const { result } = hook("blocked");
    await waitFor(() => expect(result.current.runStatus).toBe("failed"), { timeout: 4000 });
    expect(result.current.policyStop).toMatchObject({ policyReason: "captcha", stepSeq: 1 });
    expect(result.current.pauseDetails).toBeNull();
  });

  it("a step failure keeps the observed screenshot and the previous step's screenshot", async () => {
    const { result } = hook("failed");
    await waitFor(() => expect(result.current.runStatus).toBe("failed"), { timeout: 4000 });
    const failed = result.current.steps.find((s) => s.status === "failed");
    expect(failed?.seq).toBe(2);
    expect(failed?.screenshotUrl).toBe("/mock-observed.png");
    expect(failed?.previousScreenshotUrl).toBe("/screenshots/step-1.png");
    expect(result.current.policyStop).toBeNull();
  });

  it("skips duplicate seqs and never re-opens the stream after a final event", async () => {
    const client = new MockApiClient();
    const events: RunEvent[] = [giteaEventsFixture[0], giteaEventsFixture[0], ...giteaEventsFixture.slice(1)];
    const calls: StreamOptions[] = [];
    client.streamRunEvents = async function* (_runId: string, options: StreamOptions = {}) {
      calls.push(options);
      for (const e of events) yield e;
    };
    const { result } = hook("default", client);
    await waitFor(() => expect(result.current.runStatus).toBe("completed"));
    act(() => result.current.reconnect());
    expect(calls).toHaveLength(1);
    expect(result.current.verifiedCount).toBe(5);
  });

  it("reports a lost stream and reconnects from the last seq", async () => {
    const client = new MockApiClient();
    const calls: StreamOptions[] = [];
    client.streamRunEvents = async function* (_runId: string, options: StreamOptions = {}) {
      calls.push(options);
      if (calls.length === 1) {
        yield giteaEventsFixture[0];
        yield giteaEventsFixture[1];
        throw new Error("Lost the live event stream");
      }
      for (const e of giteaEventsFixture) if (e.seq > (options.lastEventId ?? 0)) yield e;
    };
    const { result } = hook("default", client);
    await waitFor(() => expect(result.current.streamState).toBe("lost"));
    expect(result.current.error).toMatch(/lost/i);

    act(() => result.current.reconnect());
    await waitFor(() => expect(result.current.runStatus).toBe("completed"));
    expect(calls[1].lastEventId).toBe(2);
  });
});
