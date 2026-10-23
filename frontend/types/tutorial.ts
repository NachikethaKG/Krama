export type TutorialStatus = "verified" | "outdated";
export type TargetPlatform = "gitea" | "github" | "custom";

export interface TutorialSummary {
  id: string;
  title: string;
  description?: string;
  taskPrompt?: string;
  target: TargetPlatform;
  status: TutorialStatus;
  stepCount: number;
  durationMs: number;
  createdAt: string;
  thumbnailUrl?: string;
}

export interface TutorialFilterOptions {
  searchQuery?: string;
  status?: "all" | TutorialStatus;
  target?: "all" | TargetPlatform;
}
