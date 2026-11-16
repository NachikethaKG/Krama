"use client";

export interface LatencySparklineProps {
  p50Ms: number;
  p90Ms: number;
  maxMs?: number;
  width?: number;
  height?: number;
}

export function formatMs(ms: number): string {
  if (ms <= 0) return "0s";
  const seconds = ms / 1000;
  if (seconds < 1) return `${Math.round(ms)}ms`;
  return `${seconds.toFixed(1)}s`;
}

/**
 * Lightweight SVG sparkline showing P50 vs P90 latency relative to a 60s/90s target budget.
 * Zero external charting library dependencies (PRD §33 RSC-compliant).
 */
export function LatencySparkline({
  p50Ms,
  p90Ms,
  maxMs = 90000,
  width = 140,
  height = 20,
}: LatencySparklineProps) {
  // Target budget is 60s per PRD §33
  const targetBudgetMs = 60000;
  const effectiveMax = Math.max(maxMs, p90Ms * 1.15, targetBudgetMs * 1.25);

  const p50Ratio = Math.min(1, Math.max(0, p50Ms / effectiveMax));
  const p90Ratio = Math.min(1, Math.max(0, p90Ms / effectiveMax));
  const budgetRatio = Math.min(1, Math.max(0, targetBudgetMs / effectiveMax));

  const p50X = p50Ratio * width;
  const p90X = p90Ratio * width;
  const budgetX = budgetRatio * width;

  const isUnderBudget = p90Ms <= targetBudgetMs;
  const gradientId = `kr-spark-${isUnderBudget ? "ok" : "warn"}`;

  return (
    <div
      className="inline-flex flex-col gap-1 items-start"
      role="img"
      aria-label={`Latency profile: P50 ${formatMs(p50Ms)}, P90 ${formatMs(p90Ms)} (Target budget: 60s)`}
    >
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="overflow-visible"
      >
        <defs>
          <linearGradient id="kr-spark-ok" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="var(--run)" />
            <stop offset="100%" stopColor="var(--verify)" />
          </linearGradient>
          <linearGradient id="kr-spark-warn" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="var(--plan)" />
            <stop offset="100%" stopColor="var(--ask)" />
          </linearGradient>
        </defs>
        {/* Track background */}
        <rect
          x={0}
          y={6}
          width={width}
          height={8}
          rx={4}
          className="fill-white/10"
        />

        {/* 60s target budget line marker */}
        <line
          x1={budgetX}
          y1={2}
          x2={budgetX}
          y2={18}
          strokeDasharray="2 2"
          className="stroke-ink-400"
          strokeWidth="1.5"
        />

        {/* P90 range fill (lighter) */}
        <rect
          x={0}
          y={6}
          width={Math.max(4, p90X)}
          height={8}
          rx={4}
          className="fill-approve/30"
        />

        {/* P50 bar fill (solid) */}
        <rect
          x={0}
          y={6}
          width={Math.max(4, p50X)}
          height={8}
          rx={4}
          fill={`url(#${gradientId})`}
        />

        {/* P90 whisker marker */}
        <line
          x1={p90X}
          y1={4}
          x2={p90X}
          y2={16}
          className="stroke-white"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>

      <div className="flex w-full justify-between text-[10px] text-ink-400 font-mono">
        <span>P50: {formatMs(p50Ms)}</span>
        <span className={isUnderBudget ? "text-verify" : "text-plan"}>
          P90: {formatMs(p90Ms)}
        </span>
      </div>
    </div>
  );
}
