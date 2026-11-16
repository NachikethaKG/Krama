"use client";

import { useState } from "react";

export interface ApprovalControlsProps {
  /** The run created by POST /plans/{id}/approve; the success banner links to its live view. */
  runId?: string | null;
  onApprove?: () => Promise<void> | void;
  onReject?: () => Promise<void> | void;
  onToggleEdit?: () => void;
  isEditing?: boolean;
  isPending?: boolean;
  disabled?: boolean;
  /** Plan status: `proposed`, `approved` or `rejected`. */
  status?: string | null;
  error?: string | null;
  className?: string;
}

export function ApprovalControls({
  runId,
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
  // Approving while editing would approve the revision the user is no longer looking at.
  const approveDisabled = pending || disabled || isTerminal || isEditing;

  const handleApprove = async () => {
    if (approveDisabled || !onApprove) return;
    setInternalError(null);
    setInternalPending(true);
    try {
      await onApprove();
    } catch (err) {
      setInternalError(err instanceof Error ? err.message : "Couldn't approve the plan");
    } finally {
      setInternalPending(false);
    }
  };

  const handleReject = async () => {
    if (pending || disabled || isTerminal || !onReject) return;
    setInternalError(null);
    setInternalPending(true);
    try {
      await onReject();
    } catch (err) {
      setInternalError(err instanceof Error ? err.message : "Couldn't cancel the plan");
    } finally {
      setInternalPending(false);
    }
  };

  return (
    <section
      role="region"
      data-testid="approval-controls"
      aria-label="Workflow approval controls"
      className={`flex flex-col gap-3 ${className}`}
    >
      {/* Error banner */}
      {error && (
        <div
          role="alert"
          data-testid="approval-error-banner"
          className="kr-danger kr-tone-card flex items-center justify-between rounded-2xl px-4 py-3 text-sm text-danger"
        >
          <div className="flex items-center gap-2">
            <svg
              aria-hidden="true"
              className="size-4 shrink-0 text-danger"
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
            className="text-xs font-bold text-danger underline hover:text-white"
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
          className="kr-verify kr-tone-card flex flex-col gap-2 rounded-2xl px-4 py-3 text-sm font-semibold text-verify"
        >
          <div className="flex items-center gap-2">
            <svg
              aria-hidden="true"
              className="size-4 shrink-0 text-verify"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            <span>Approved. Starting the task…</span>
          </div>
          {runId && (
            <div>
              <a
                href={`/runs/${runId}/live`}
                data-testid="live-execution-link"
                className="inline-flex items-center gap-1 text-xs font-bold text-verify underline hover:text-white"
              >
                Go to Live Execution &rarr;
              </a>
            </div>
          )}
        </div>
      )}

      {(status === "rejected" || status === "cancelled") && (
        <div
          data-testid="approval-rejected-banner"
          role="status"
          className="kr-glass flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium text-ink-300"
        >
          <svg
            aria-hidden="true"
            className="size-4 shrink-0 text-danger"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
          <span>Plan cancelled. Nothing was run.</span>
        </div>
      )}

      {/* Action buttons bar */}
      <div className="kr-spectrum-border sticky bottom-4 z-20 flex flex-wrap items-center justify-between gap-3 rounded-[2rem] bg-ink-900/90 p-3 backdrop-blur-xl">
        <div>
          {onToggleEdit && (
            <button
              type="button"
              data-testid="edit-btn"
              disabled={pending || disabled || isTerminal}
              onClick={onToggleEdit}
              className={`kr-btn kr-plan px-4 py-2.5 text-sm ${isEditing ? "kr-btn-tone" : "kr-btn-ghost"}`}
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
              <span>{isEditing ? "Done editing" : "Edit steps"}</span>
            </button>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            data-testid="reject-btn"
            disabled={pending || disabled || isTerminal}
            onClick={handleReject}
            className="kr-btn kr-btn-ghost kr-danger px-4 py-2.5 text-sm text-danger"
          >
            <span>Cancel</span>
          </button>

          <button
            type="button"
            data-testid="approve-btn"
            aria-busy={pending}
            disabled={approveDisabled}
            title={isEditing ? "Save your edits before approving" : undefined}
            onClick={handleApprove}
            className="kr-btn kr-btn-primary px-7 py-3 text-base"
          >
            {pending ? (
              <>
                <svg
                  aria-hidden="true"
                  className="size-4 animate-spin text-ink-950"
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
                <span>Approve & run</span>
              </>
            )}
          </button>
        </div>
      </div>
    </section>
  );
}
