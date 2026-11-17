export type TutorialFreshnessStatus =
  | "verified"
  | "auto-updated"
  | "outdated"
  | "not_auto_checked";

export type TutorialStatus = TutorialFreshnessStatus;

export type TargetPlatform = "gitea" | "github" | "custom";

export interface StepDiffItem {
  stepIndex: number;
  stepTitle: string;
  changeType: "locator_healed" | "wording_only" | "unchanged";
  oldLabel?: string;
  newLabel?: string;
  oldSelector?: string;
  newSelector?: string;
  oldCaption?: string;
  newCaption?: string;
}

export interface WorkflowVersionRecord {
  id: string;
  version: string; // e.g., "v1.0", "v1.1"
  status: "active" | "auto-updated" | "heal_pending" | "archived" | "current" | "pending_review" | "superseded" | "rejected";
  changeSummary: string;
  isWordingOnly: boolean;
  createdAt: string;
  stepDiffs: StepDiffItem[];
}

export interface TutorialSummary {
  id: string;
  title: string;
  description?: string;
  taskPrompt?: string;
  target: TargetPlatform;
  status: TutorialFreshnessStatus;
  stepCount: number;
  durationMs: number;
  createdAt: string;
  thumbnailUrl?: string;
  activeVersion?: string;
  hasDiff?: boolean;
}

export interface TutorialFilterOptions {
  searchQuery?: string;
  status?: "all" | TutorialFreshnessStatus;
  target?: "all" | TargetPlatform;
}
