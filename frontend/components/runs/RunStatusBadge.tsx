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
      "bg-verify/15 text-verify border-verify/40",
    dotClass: "bg-verify",
  },
  completed: {
    label: "Verified",
    containerClass:
      "bg-verify/15 text-verify border-verify/40",
    dotClass: "bg-verify",
  },
  failed: {
    label: "Failed",
    containerClass:
      "bg-danger/15 text-danger border-danger/40",
    dotClass: "bg-danger",
  },
  paused: {
    label: "Paused",
    containerClass:
      "bg-plan/15 text-plan border-plan/40",
    dotClass: "bg-plan",
  },
  cancelled: {
    label: "Cancelled",
    containerClass:
      "bg-white/[0.06] text-ink-300 border-white/10",
    dotClass: "bg-ink-400",
  },
  queued: {
    label: "Queued",
    containerClass:
      "bg-approve/15 text-approve border-approve/40",
    dotClass: "bg-approve animate-pulse",
  },
  running: {
    label: "Running",
    containerClass:
      "bg-run/15 text-run border-run/40",
    dotClass: "bg-run kr-dot-live",
  },
};

export function RunStatusBadge({ status, className = "", size = "md" }: RunStatusBadgeProps) {
  const normalized = (status ?? "queued").toLowerCase().trim();
  const config = STATUS_CONFIG[normalized] ?? {
    label: normalized.charAt(0).toUpperCase() + normalized.slice(1),
    containerClass:
      "bg-white/[0.06] text-ink-300 border-white/10",
    dotClass: "bg-ink-400",
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
      className={`inline-flex items-center rounded-full border font-bold tracking-wide backdrop-blur ${config.containerClass} ${sizeClasses} ${className}`}
    >
      <span
        aria-hidden="true"
        className={`inline-block size-1.5 rounded-full shadow-[0_0_8px_currentColor] ${config.dotClass}`}
      />
      <span>{config.label}</span>
    </span>
  );
}
