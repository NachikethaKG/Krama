import type { Workflow, WorkflowSummary } from "@krama/contracts-ts";
import type { TutorialFreshnessStatus } from "@/types/tutorial";

/**
 * A stored workflow's badge (D11, #114, #382): outdated stays outdated; a verified workflow whose current version a
 * self-heal made is "auto-updated"; anything else is "verified". Library, player and share page all use this.
 */
export function workflowFreshness(
  workflow: Pick<Workflow | WorkflowSummary, "status" | "current_version_source">,
): TutorialFreshnessStatus {
  if (workflow.status === "outdated") return "outdated";
  if (workflow.status === "verified" && workflow.current_version_source === "heal") return "auto-updated";
  return "verified";
}
