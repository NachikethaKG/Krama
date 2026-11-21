import type { Risk } from "@krama/contracts-ts";
import { useTranslations } from "next-intl";

export type RiskLevel = Risk | "critical" | string;

export interface RiskBadgeProps {
  level?: RiskLevel | null;
  className?: string;
  size?: "sm" | "md";
}

// Neon chips: safe = verify lime, creates = plan amber, changes = learn orange, dangerous = coral (pulsing).
const RISK_CONFIG: Record<
  string,
  {
    labelKey: "safe" | "creates" | "changes" | "dangerous";
    tone: string;
    dotClass: string;
  }
> = {
  low: { labelKey: "safe", tone: "kr-verify", dotClass: "" },
  medium: { labelKey: "creates", tone: "kr-plan", dotClass: "" },
  high: { labelKey: "changes", tone: "kr-learn", dotClass: "kr-dot-live" },
  critical: { labelKey: "dangerous", tone: "kr-danger", dotClass: "kr-dot-live" },
};

export function RiskBadge({ level = "low", className = "", size = "md" }: RiskBadgeProps) {
  const t = useTranslations("approval");
  const normalizedLevel = (level ?? "low").toLowerCase().trim();
  const config = RISK_CONFIG[normalizedLevel] ?? RISK_CONFIG.low;

  const sizeClasses = size === "sm" ? "!text-[11px]" : "!px-3 !py-1 !text-xs";

  return (
    <span
      data-testid="risk-badge"
      data-risk-level={normalizedLevel}
      aria-label={t("riskBadge.ariaLabel", { level: normalizedLevel })}
      className={`kr-chip ${config.tone} whitespace-nowrap ${sizeClasses} ${className}`}
    >
      <span
        aria-hidden="true"
        className={`kr-dot !size-1.5 ${config.dotClass}`}
      />
      <span>{t(`riskBadge.${config.labelKey}`)}</span>
    </span>
  );
}
