"use client";

import { useEffect, useRef, useState } from "react";
import { type ApiClient, errorMessage, getApiClient, type SessionStatus } from "@/lib/api";

export interface ManualLoginGuideProps {
  target?: string;
  client?: ApiClient;
  pollIntervalMs?: number;
  timeoutMs?: number;
  onSessionActive?: () => void;
  className?: string;
}

type Phase = "checking" | "idle" | "launching" | "pending" | "active" | "error";

export function ManualLoginGuide({
  target = "github",
  client,
  pollIntervalMs = 1000,
  timeoutMs = 300_000,
  onSessionActive,
  className = "",
}: ManualLoginGuideProps) {
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [phase, setPhase] = useState<Phase>("checking");
  const [session, setSession] = useState<SessionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const aliveRef = useRef(true);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const clearPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
      clearPolling();
    };
  }, []);

  // Check initial session status for the given target
  useEffect(() => {
    clearPolling();
    let cancelled = false;

    async function checkStatus() {
      try {
        setPhase("checking");
        const status = await apiClient.getSessionStatus(target);
        if (cancelled || !aliveRef.current) return;
        setSession(status);
        if (status.active) {
          setPhase("active");
          onSessionActive?.();
        } else {
          setPhase("idle");
        }
      } catch {
        if (cancelled || !aliveRef.current) return;
        setPhase("idle");
      }
    }

    void checkStatus();

    return () => {
      cancelled = true;
      clearPolling();
    };
  }, [apiClient, target, onSessionActive]);

  const startPolling = () => {
    clearPolling();
    const startTime = Date.now();

    pollTimerRef.current = setInterval(async () => {
      if (!aliveRef.current) {
        clearPolling();
        return;
      }

      if (Date.now() - startTime > timeoutMs) {
        clearPolling();
        setPhase("error");
        setError("Login timed out or browser was closed before completing sign-in.");
        return;
      }

      try {
        const status = await apiClient.getSessionStatus(target);
        if (!aliveRef.current) return;
        setSession(status);
        if (status.active) {
          clearPolling();
          setPhase("active");
          onSessionActive?.();
        }
      } catch (err) {
        clearPolling();
        setPhase("error");
        setError(errorMessage(err, "Failed checking session status"));
      }
    }, pollIntervalMs);
  };

  const handleLaunch = async () => {
    setError(null);
    setPhase("launching");
    try {
      await apiClient.launchManualLogin(target);
      if (!aliveRef.current) return;
      setPhase("pending");
      startPolling();
    } catch (err) {
      if (!aliveRef.current) return;
      setPhase("error");
      setError(errorMessage(err, "Failed to launch manual login session"));
    }
  };

  return (
    <div
      data-testid="manual-login-guide"
      className={`rounded-xl border border-indigo-100 bg-indigo-50/50 p-4 dark:border-indigo-900/40 dark:bg-indigo-950/20 ${className}`}
    >
      <div className="flex flex-col gap-3">
        <div className="flex items-start gap-3">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-xs dark:bg-indigo-500">
            <svg
              className="size-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
              />
            </svg>
          </div>
          <div className="flex flex-col gap-0.5">
            <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              One-Time Manual Authentication
            </h4>
            <p
              data-testid="manual-login-explainer"
              className="text-xs text-zinc-600 dark:text-zinc-400"
            >
              You will log in directly in a separate browser window. Krama only saves an encrypted session cookie, never your password.
            </p>
          </div>
        </div>

        {/* State: Active */}
        {phase === "active" && (
          <div className="flex items-center justify-between gap-3 pt-1">
            <div
              data-testid="manual-login-active-badge"
              className="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300"
            >
              <svg
                className="size-4 text-emerald-600 dark:text-emerald-400"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              <span>Session Active (Encrypted Storage State Saved)</span>
              {session?.expires_at && (
                <span className="text-[10px] font-normal text-emerald-700 dark:text-emerald-300">
                  (Expires {new Date(session.expires_at).toLocaleDateString()})
                </span>
              )}
            </div>
            <button
              type="button"
              data-testid="reauth-manual-login-btn"
              onClick={handleLaunch}
              className="text-xs font-medium text-zinc-500 underline hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              Re-authenticate
            </button>
          </div>
        )}

        {/* State: Pending / Launching */}
        {(phase === "launching" || phase === "pending") && (
          <div
            data-testid="manual-login-pending"
            className="flex items-center gap-2.5 rounded-lg border border-indigo-200 bg-white/80 px-3.5 py-2 text-xs font-medium text-indigo-900 shadow-xs dark:border-indigo-800 dark:bg-zinc-900/80 dark:text-indigo-200"
          >
            <svg
              className="size-4 animate-spin text-indigo-600 dark:text-indigo-400"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span>Waiting for you to complete sign-in in the open browser...</span>
          </div>
        )}

        {/* State: Error */}
        {phase === "error" && (
          <div
            data-testid="manual-login-error"
            role="alert"
            className="flex flex-col gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300"
          >
            <p>{error || "Authentication could not be completed."}</p>
            <div className="flex justify-end">
              <button
                type="button"
                data-testid="retry-manual-login-btn"
                onClick={handleLaunch}
                className="inline-flex items-center gap-1.5 rounded-md bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-700"
              >
                Retry Manual Login
              </button>
            </div>
          </div>
        )}

        {/* State: Idle */}
        {phase === "idle" && (
          <div className="flex justify-end pt-1">
            <button
              type="button"
              data-testid="launch-manual-login-btn"
              onClick={handleLaunch}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-indigo-700 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 dark:bg-indigo-600 dark:hover:bg-indigo-500"
            >
              <span>Launch Manual Login</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
