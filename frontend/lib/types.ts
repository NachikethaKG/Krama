import type { ExpectedState, ObservedState, RunStatus, Workflow } from "@krama/contracts-ts";

export type VerificationEvidenceMethod = "url_dom" | "aria" | "network" | "vision";

export interface StepVerificationEvidence {
  method: VerificationEvidenceMethod;
  confidence: number;
  screenshotUrl?: string | null;
  observedAt: string;
  details?: Record<string, unknown>;
}

export interface RunListItem {
  id: string;
  prompt: string;
  status: RunStatus | "verified" | "failed" | "paused" | "cancelled" | "queued" | "running";
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  durationSeconds?: number | null;
  workflowId?: string | null;
  planId?: string;
  retryCount?: number;
}

export interface PaginatedRunsResponse {
  items: RunListItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  nextCursor?: string | null;
}

export interface StepEvidenceDetail {
  id: string;
  seq: number;
  instructionText: string;
  actionType: string;
  targetRole?: string | null;
  targetName?: string | null;
  risk: string;
  status: "verified" | "failed" | "pending";
  evidence: StepVerificationEvidence;
  screenshotUrl?: string | null;
  expectedState?: ExpectedState;
  observedState?: ObservedState;
  timing?: {
    startMs?: number | null;
    endMs?: number | null;
    durationMs?: number | null;
  };
}

export interface RunDetails {
  run: RunListItem;
  workflow?: Workflow | null;
  targetUrl?: string;
  targetApp?: string;
  steps: StepEvidenceDetail[];
  summary: {
    totalSteps: number;
    verifiedSteps: number;
    failedSteps: number;
    durationSeconds?: number | null;
  };
}
