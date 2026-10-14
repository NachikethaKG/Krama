import type { RunStatus } from "@krama/contracts-ts";

export type RunStatusType =
  | RunStatus
  | "verified"
  | "failed"
  | "paused"
  | "cancelled"
  | "queued"
  | "running";

export interface RunStatusBadgeProps {
  status: RunStatusType;
  className?: string;
  size?: "sm" | "md";
}

const STATUS_CONFIG: Record<
  string,
  {
    label: string;
    containerClass: string;
    dotClass: string;
  }
> = {
  verified: {
    label: "Verified",
    containerClass:
      "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800",
    dotClass: "bg-emerald-500",
  },
  completed: {
    label: "Verified",
    containerClass:
      "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800",
    dotClass: "bg-emerald-500",
  },
  failed: {
    label: "Failed",
    containerClass:
      "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800",
    dotClass: "bg-rose-500",
  },
  paused: {
    label: "Paused",
    containerClass:
      "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800",
    dotClass: "bg-amber-500",
  },
  cancelled: {
    label: "Cancelled",
    containerClass:
      "bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700",
    dotClass: "bg-zinc-400",
  },
  queued: {
    label: "Queued",
    containerClass:
      "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-400 dark:border-sky-800",
    dotClass: "bg-sky-500",
  },
  running: {
    label: "Running",
    containerClass:
      "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400 dark:border-indigo-800",
    dotClass: "bg-indigo-500 animate-pulse",
  },
};

export function RunStatusBadge({ status, className = "", size = "md" }: RunStatusBadgeProps) {
  const normalized = (status ?? "queued").toLowerCase().trim();
  const config = STATUS_CONFIG[normalized] ?? {
    label: normalized.charAt(0).toUpperCase() + normalized.slice(1),
    containerClass:
      "bg-zinc-100 text-zinc-700 border-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700",
    dotClass: "bg-zinc-400",
  };

  const sizeClasses =
    size === "sm"
      ? "text-xs px-2 py-0.5 gap-1"
      : "text-xs font-medium px-2.5 py-1 gap-1.5";

  return (
    <span
      data-testid="run-status-badge"
      data-status={normalized}
      aria-label={`Run status: ${config.label}`}
      className={`inline-flex items-center rounded-full border ${config.containerClass} ${sizeClasses} ${className}`}
    >
      <span
        aria-hidden="true"
        className={`inline-block size-1.5 rounded-full ${config.dotClass}`}
      />
      <span>{config.label}</span>
    </span>
  );
}
