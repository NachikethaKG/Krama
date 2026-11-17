import type { StepDiffItem } from "./tutorial";

export type ReviewItemCategory =
  | "outdated"
  | "heal_pending"
  | "unstable"
  | "cant_check";

export type ReviewFilterCategory = "all" | ReviewItemCategory;

export interface ReviewQueueItem {
  id: string;
  workflowId: string;
  workflowTitle: string;
  targetPlatform: "gitea" | "github" | "custom";
  category: ReviewItemCategory;
  reason: string; // e.g., "GitHub session expired", "2 flakes in 7 days", "Step 3 button missing"
  failedStepIndex?: number;
  createdAt: string;
  pendingVersion?: string; // e.g., "v1.1"
  stepDiffs?: StepDiffItem[];
  canRetryAiFix?: boolean;
}

export interface ReviewActionResponse {
  success: boolean;
  message?: string;
  workflow_id?: string;
  run_id?: string;
}

export interface ReviewQueueCountResponse {
  count: number;
}
