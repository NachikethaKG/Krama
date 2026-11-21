import type { RunStatus } from "@krama/contracts-ts";
import { useTranslations } from "next-intl";

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
    labelKey: "verified" | "failed" | "paused" | "cancelled" | "queued" | "running";
    containerClass: string;
    dotClass: string;
  }
> = {
  verified: {
    labelKey: "verified",
    containerClass:
      "bg-verify/15 text-verify border-verify/40",
    dotClass: "bg-verify",
  },
  completed: {
    labelKey: "verified",
    containerClass:
      "bg-verify/15 text-verify border-verify/40",
    dotClass: "bg-verify",
  },
  failed: {
    labelKey: "failed",
    containerClass:
      "bg-danger/15 text-danger border-danger/40",
    dotClass: "bg-danger",
  },
  paused: {
    labelKey: "paused",
    containerClass:
      "bg-plan/15 text-plan border-plan/40",
    dotClass: "bg-plan",
  },
  cancelled: {
    labelKey: "cancelled",
    containerClass:
      "bg-white/[0.06] text-ink-300 border-white/10",
    dotClass: "bg-ink-400",
  },
  queued: {
    labelKey: "queued",
    containerClass:
      "bg-approve/15 text-approve border-approve/40",
    dotClass: "bg-approve animate-pulse",
  },
  running: {
    labelKey: "running",
    containerClass:
      "bg-run/15 text-run border-run/40",
    dotClass: "bg-run kr-dot-live",
  },
};

export function RunStatusBadge({ status, className = "", size = "md" }: RunStatusBadgeProps) {
  const t = useTranslations("runs");
  const normalized = (status ?? "queued").toLowerCase().trim();
  const known = STATUS_CONFIG[normalized];
  // An unknown status from the API is shown as-is (capitalised), not translated.
  const label = known
    ? t(`statusBadge.${known.labelKey}`)
    : normalized.charAt(0).toUpperCase() + normalized.slice(1);
  const config = known ?? {
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
      aria-label={t("statusBadge.ariaLabel", { label })}
      className={`inline-flex items-center rounded-full border font-bold tracking-wide backdrop-blur ${config.containerClass} ${sizeClasses} ${className}`}
    >
      <span
        aria-hidden="true"
        className={`inline-block size-1.5 rounded-full shadow-[0_0_8px_currentColor] ${config.dotClass}`}
      />
      <span>{label}</span>
    </span>
  );
}
