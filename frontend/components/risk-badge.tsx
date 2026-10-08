import type { Risk } from "@krama/contracts-ts";

export type RiskLevel = Risk | "critical" | string;

export interface RiskBadgeProps {
  level?: RiskLevel | null;
  className?: string;
  size?: "sm" | "md";
}

const RISK_CONFIG: Record<
  string,
  {
    label: string;
    containerClass: string;
    dotClass: string;
  }
> = {
  low: {
    label: "Low Risk",
    containerClass:
      "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800",
    dotClass: "bg-emerald-500",
  },
  medium: {
    label: "Medium Risk",
    containerClass:
      "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800",
    dotClass: "bg-amber-500",
  },
  high: {
    label: "High Risk",
    containerClass:
      "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/40 dark:text-orange-400 dark:border-orange-800",
    dotClass: "bg-orange-500",
  },
  critical: {
    label: "Critical Risk",
    containerClass:
      "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800",
    dotClass: "bg-rose-500",
  },
};

export function RiskBadge({ level = "low", className = "", size = "md" }: RiskBadgeProps) {
  const normalizedLevel = (level ?? "low").toLowerCase().trim();
  const config = RISK_CONFIG[normalizedLevel] ?? RISK_CONFIG.low;

  const sizeClasses =
    size === "sm"
      ? "text-xs px-2 py-0.5 gap-1"
      : "text-xs font-medium px-2.5 py-1 gap-1.5";

  return (
    <span
      data-testid="risk-badge"
      data-risk-level={normalizedLevel}
      aria-label={`Risk level: ${normalizedLevel}`}
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
