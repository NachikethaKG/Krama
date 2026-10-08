"use client";

import { useState } from "react";
import type { MockApiClient } from "@/lib/api";

export interface ApprovalResult {
  status: "approved" | "executing" | "rejected" | "cancelled";
  workflowId: string;
}

/**
 * Executes mock approval transition against MockApiClient data.
 */
export async function mockApproveWorkflow(
  client: MockApiClient,
  workflowId: string
): Promise<ApprovalResult> {
  // Validate workflow exists in client
  await client.getWorkflow(workflowId);
  return { status: "approved", workflowId };
}

/**
 * Executes mock rejection transition against MockApiClient data.
 */
export async function mockRejectWorkflow(
  client: MockApiClient,
  workflowId: string,
  reason?: string
): Promise<ApprovalResult> {
  void reason;
  await client.getWorkflow(workflowId);
  return { status: "rejected", workflowId };
}

export interface ApprovalControlsProps {
  workflowId?: string;
  client?: MockApiClient;
  onApprove?: () => Promise<void> | void;
  onReject?: () => Promise<void> | void;
  onToggleEdit?: () => void;
  isEditing?: boolean;
  isPending?: boolean;
  disabled?: boolean;
  status?: string | null;
  error?: string | null;
  className?: string;
}

export function ApprovalControls({
  workflowId = "default",
  client,
  onApprove,
  onReject,
  onToggleEdit,
  isEditing = false,
  isPending = false,
  disabled = false,
  status,
  error: externalError,
  className = "",
}: ApprovalControlsProps) {
  const [internalPending, setInternalPending] = useState(false);
  const [internalError, setInternalError] = useState<string | null>(null);

  const pending = isPending || internalPending;
  const error = externalError ?? internalError;
  const isTerminal = status === "approved" || status === "executing" || status === "rejected" || status === "cancelled";

  const handleApprove = async () => {
    if (pending || disabled || isTerminal) return;
    setInternalError(null);
    setInternalPending(true);
    try {
      if (onApprove) {
        await onApprove();
      } else if (client) {
        await mockApproveWorkflow(client, workflowId);
      }
    } catch (err) {
      setInternalError(err instanceof Error ? err.message : "Failed to approve workflow plan");
    } finally {
      setInternalPending(false);
    }
  };

  const handleReject = async () => {
    if (pending || disabled || isTerminal) return;
    setInternalError(null);
    setInternalPending(true);
    try {
      if (onReject) {
        await onReject();
      } else if (client) {
        await mockRejectWorkflow(client, workflowId);
      }
    } catch (err) {
      setInternalError(err instanceof Error ? err.message : "Failed to reject workflow plan");
    } finally {
      setInternalPending(false);
    }
  };

  return (
    <div
      data-testid="approval-controls"
      aria-label="Workflow approval controls"
      className={`flex flex-col gap-3 ${className}`}
    >
      {/* Error banner */}
      {error && (
        <div
          role="alert"
          data-testid="approval-error-banner"
          className="flex items-center justify-between rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300"
        >
          <div className="flex items-center gap-2">
            <svg
              aria-hidden="true"
              className="size-4 shrink-0 text-rose-600 dark:text-rose-400"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
              />
            </svg>
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => setInternalError(null)}
            className="text-xs text-rose-600 underline hover:text-rose-800 dark:text-rose-400"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Terminal status banners */}
      {status === "approved" && (
        <div
          data-testid="approval-success-banner"
          role="status"
          className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300"
        >
          <svg
            aria-hidden="true"
            className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
          <span>Plan approved! Workflow is transitioning to execution.</span>
        </div>
      )}

      {(status === "rejected" || status === "cancelled") && (
        <div
          data-testid="approval-rejected-banner"
          role="status"
          className="flex items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm font-medium text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
        >
          <svg
            aria-hidden="true"
            className="size-4 shrink-0 text-zinc-500"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
          <span>Workflow plan rejected. Execution canceled.</span>
        </div>
      )}

      {/* Action buttons bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-xs dark:border-zinc-800 dark:bg-zinc-900">
        <div>
          {onToggleEdit && (
            <button
              type="button"
              data-testid="edit-btn"
              disabled={pending || disabled || isTerminal}
              onClick={onToggleEdit}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-3.5 py-2 text-sm font-medium transition-colors ${
                isEditing
                  ? "border-amber-300 bg-amber-50 text-amber-800 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
                  : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
              } disabled:cursor-not-allowed disabled:opacity-50`}
            >
              <svg
                aria-hidden="true"
                className="size-4"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"
                />
              </svg>
              <span>{isEditing ? "Done Editing" : "Edit Plan"}</span>
            </button>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            data-testid="reject-btn"
            disabled={pending || disabled || isTerminal}
            onClick={handleReject}
            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-white px-4 py-2 text-sm font-medium text-rose-700 transition-colors hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-rose-900/60 dark:bg-zinc-900 dark:text-rose-400 dark:hover:bg-rose-950/40"
          >
            <span>Reject Plan</span>
          </button>

          <button
            type="button"
            data-testid="approve-btn"
            disabled={pending || disabled || isTerminal}
            onClick={handleApprove}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2 text-sm font-medium text-white shadow-xs transition-colors hover:bg-emerald-700 focus:outline-hidden focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-emerald-600 dark:hover:bg-emerald-500"
          >
            {pending ? (
              <>
                <svg
                  aria-hidden="true"
                  className="size-4 animate-spin text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8v8H4z"
                  />
                </svg>
                <span>Processing…</span>
              </>
            ) : (
              <>
                <svg
                  aria-hidden="true"
                  className="size-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                <span>Approve & Execute</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
