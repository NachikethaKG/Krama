import { describe, expect, it } from "vitest";
import { workflowFreshness } from "@/lib/freshness";
import { freshness } from "@/components/player/WorkflowTutorial";

describe("workflowFreshness (#382)", () => {
  it("shows auto-updated for a verified workflow a self-heal updated", () => {
    expect(workflowFreshness({ status: "verified", current_version_source: "heal" })).toBe("auto-updated");
  });

  it("stays verified for a first version or a regenerated one", () => {
    expect(workflowFreshness({ status: "verified", current_version_source: "initial" })).toBe("verified");
    expect(workflowFreshness({ status: "verified", current_version_source: "regenerate" })).toBe("verified");
    expect(workflowFreshness({ status: "verified", current_version_source: null })).toBe("verified");
  });

  it("an outdated workflow is outdated even after an earlier heal", () => {
    expect(workflowFreshness({ status: "outdated", current_version_source: "heal" })).toBe("outdated");
  });

  it("the player uses the same rule", () => {
    expect(freshness({ status: "verified", current_version_source: "heal" })).toBe("auto-updated");
  });
});
