import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useWorkflowExecutionStream } from "@/hooks/useWorkflowExecutionStream";
import { MockApiClient } from "@/lib/api";
import {
  giteaEventsFixture,
  giteaFailedEventsFixture,
  giteaPausedEventsFixture,
  giteaWorkflowFixture,
} from "@/lib/fixtures";

describe("useWorkflowExecutionStream", () => {
  it("initializes with pending step states from workflow", async () => {
    const client = new MockApiClient(giteaEventsFixture);
    const { result } = renderHook(() =>
      useWorkflowExecutionStream({
        workflowId: "default",
        client,
        autoStart: false,
      })
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.runStatus).toBe("idle");
    expect(result.current.steps).toHaveLength(5);
    expect(result.current.steps[0].status).toBe("pending");
    expect(result.current.totalSteps).toBe(5);
  });

  it("streams events and marks steps verified through completion", async () => {
    const client = new MockApiClient(giteaEventsFixture);
    const { result } = renderHook(() =>
      useWorkflowExecutionStream({
        workflowId: "default",
        client,
        speed: 1000, // fast replay for unit tests
        initialWorkflow: giteaWorkflowFixture,
      })
    );

    await waitFor(
      () => {
        expect(result.current.runStatus).toBe("completed");
      },
      { timeout: 3000 }
    );

    expect(result.current.verifiedCount).toBe(5);
    expect(result.current.progressPercent).toBe(100);
    expect(result.current.steps[0].status).toBe("verified");
    expect(result.current.steps[4].status).toBe("verified");
  });

  it("handles run.paused event correctly", async () => {
    const client = new MockApiClient(giteaPausedEventsFixture);
    const { result } = renderHook(() =>
      useWorkflowExecutionStream({
        workflowId: "paused",
        client,
        speed: 1000,
        initialWorkflow: giteaWorkflowFixture,
      })
    );

    await waitFor(
      () => {
        expect(result.current.runStatus).toBe("paused");
      },
      { timeout: 3000 }
    );

    expect(result.current.pauseDetails).toEqual({
      reason: "destructive_action",
      stepSeq: 2,
      message: "Destructive action requires confirmation before proceeding",
    });

    // Test resume
    act(() => {
      result.current.resume();
    });
    expect(result.current.runStatus).toBe("running");
    expect(result.current.pauseDetails).toBeNull();
  });

  it("handles step.failed and run.failed events correctly", async () => {
    const client = new MockApiClient(giteaFailedEventsFixture);
    const { result } = renderHook(() =>
      useWorkflowExecutionStream({
        workflowId: "failed",
        client,
        speed: 1000,
        initialWorkflow: giteaWorkflowFixture,
      })
    );

    await waitFor(
      () => {
        expect(result.current.runStatus).toBe("failed");
      },
      { timeout: 3000 }
    );

    expect(result.current.runError).toBeDefined();
    expect(result.current.runError?.code).toBe("validation_error");
    expect(result.current.stepStates[2].status).toBe("failed");
    expect(result.current.stepStates[2].error).toContain("Verification failed");
  });
});
