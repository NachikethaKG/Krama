"use client";

import { useEffect, useState } from "react";

import { type ApiClient, getApiClient } from "@/lib/api";

export type SystemStatus = "online" | "offline" | "checking";

export interface ApiStatusBadgeProps {
  status: SystemStatus;
  className?: string;
}

export function ApiStatusBadge({ status, className = "" }: ApiStatusBadgeProps) {
  const dotColor =
    status === "online"
      ? "bg-emerald-500"
      : status === "offline"
        ? "bg-rose-500"
        : "bg-amber-500 animate-pulse";

  const label =
    status === "online"
      ? "Systems Operational"
      : status === "offline"
        ? "API Offline"
        : "Connecting...";

  return (
    <div
      className={`inline-flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400 ${className}`}
      aria-label="System Status"
      role="status"
    >
      <span className={`h-2 w-2 rounded-full ${dotColor}`} />
      <span>{label}</span>
    </div>
  );
}

export interface ApiStatusProps {
  client?: ApiClient;
  showOfflineBanner?: boolean;
  className?: string;
}

export function ApiStatus({
  client,
  showOfflineBanner = true,
  className = "",
}: ApiStatusProps) {
  const [status, setStatus] = useState<SystemStatus>("checking");

  useEffect(() => {
    let mounted = true;
    const api = client ?? getApiClient();

    api
      .health()
      .then((health) => {
        if (!mounted) return;
        if (health && health.status === "ok") {
          setStatus("online");
        } else {
          setStatus("offline");
        }
      })
      .catch(() => {
        if (mounted) {
          setStatus("offline");
        }
      });

    return () => {
      mounted = false;
    };
  }, [client]);

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {showOfflineBanner && status === "offline" && (
        <div
          role="alert"
          aria-label="Backend offline notification"
          className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300"
        >
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            <span>
              Backend service offline. Cached workflows and mock mode remain available.
            </span>
          </div>
        </div>
      )}
      <ApiStatusBadge status={status} />
    </div>
  );
}
