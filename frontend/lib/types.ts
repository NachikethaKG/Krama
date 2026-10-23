import type {
  ApiError,
  ExpectedState,
  ObservedState,
  Plan,
  RunStatus,
  Task,
  VerificationMethod,
  Workflow,
} from "@krama/contracts-ts";

export type VerificationEvidenceMethod = "url_dom" | "aria" | "network" | "vision";

export interface StepVerificationEvidence {
  method: VerificationEvidenceMethod;
  /** The contract's verification methods for this step, when known. */
  methods?: VerificationMethod[];
  /** null when the step has no verification result yet. */
  confidence?: number | null;
  screenshotUrl?: string | null;
  observedAt?: string | null;
  details?: Record<string, unknown>;
}

export interface RunListItem {
  id: string;
  /** The task prompt (Run → Plan → Task). null when it could not be loaded. */
  prompt: string | null;
  status: RunStatus;
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  durationSeconds?: number | null;
  workflowId?: string | null;
  planId?: string;
  retryCount?: number;
}

/** One page of GET /runs (newest first). `nextCursor` is opaque; null on the last page. */
export interface RunsPage {
  items: RunListItem[];
  nextCursor: string | null;
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
  /** A loadable URL (already resolved with artifactUrl). */
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
  plan?: Plan | null;
  task?: Task | null;
  error?: ApiError | null;
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

export interface SessionStatus {
  target: string;
  active: boolean;
  expires_at?: string | null;
  message?: string;
}

export interface ManualLoginResponse {
  target: string;
  status: "launched" | "pending" | "active" | "error";
  message?: string;
}
