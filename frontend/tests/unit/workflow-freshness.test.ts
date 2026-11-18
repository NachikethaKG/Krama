import { describe, expect, it } from "vitest";
import { freshness } from "@/components/player/WorkflowTutorial";

describe("the stored tutorial's badge (#116 gate re-check)", () => {
  it("says outdated for an outdated workflow instead of always 'Verified'", () => {
    expect(freshness({ status: "outdated" })).toBe("outdated");
  });

  it("says verified for a verified workflow", () => {
    expect(freshness({ status: "verified" })).toBe("verified");
  });
});
