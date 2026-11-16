"use client";

import type { MetricsSummary } from "@krama/contracts-ts";
import type { ReactNode } from "react";
import { Activity, Gauge, LifeBuoy, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { formatMs } from "./LatencySparkline";

export interface MetricsKpiGridProps {
  summary: MetricsSummary;
}

export function MetricsKpiGrid({ summary }: MetricsKpiGridProps) {
  // PRD §33 Targets:
  // 1. Success Rate >= 80%
  const successRate = summary.overall_success_rate ?? 0;
  const successRatePct = (successRate * 100).toFixed(1);
  const isSuccessPassed = successRate >= 0.8;

  // 2. Verifier Accuracy >= 90%
  const verifierAccuracy = summary.overall_verifier_accuracy ?? 0;
  const verifierAccuracyPct = (verifierAccuracy * 100).toFixed(1);
  const isAccuracyPassed = verifierAccuracy >= 0.9;

  // 3. Recovery Rate >= 50%
  // Only shown when the benchmark measured replans: the contract summary has no recovery or planning fields,
  // so a missing value is "not measured", never a made-up 100% (#104).
  const extendedSummary = summary as unknown as {
    overall_recovery_rate?: number;
    overall_replan_attempts?: number;
    overall_replan_successes?: number;
    overall_avg_planning_latency_ms?: number;
  };

  const rawRecovery = extendedSummary.overall_replan_attempts
    ? extendedSummary.overall_recovery_rate
    : undefined;
  // The reporter writes a percentage (0-100).
  const recoveryRate = rawRecovery == null ? null : rawRecovery > 1 ? rawRecovery / 100 : rawRecovery;
  const recoveryRatePct = recoveryRate == null ? "Not measured" : `${(recoveryRate * 100).toFixed(1)}%`;
  const isRecoveryPassed = recoveryRate != null && recoveryRate >= 0.5;

  // 4. Latency Profile: < 15s planning, < 60s total
  const avgLatencyMs = summary.overall_avg_latency_ms ?? 0;
  const p90LatencyMs = summary.overall_p90_latency_ms ?? avgLatencyMs;
  const planningLatencyMs = extendedSummary.overall_avg_planning_latency_ms || null;

  const isTotalLatencyPassed = avgLatencyMs <= 60000;
  const isPlanningLatencyPassed = planningLatencyMs == null || planningLatencyMs <= 15000;
  const isLatencyPassed = isTotalLatencyPassed && isPlanningLatencyPassed;

  return (
    <div data-testid="metrics-kpi-grid" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <KpiTile
        id="success-rate"
        tone="kr-verify"
        icon={Activity}
        label="Task Success Rate"
        target="Target ≥ 80%"
        passed={isSuccessPassed}
        value={`${successRatePct}%`}
        unit={`(${summary.overall_successful_runs ?? 0}/${summary.overall_total_runs ?? 0} runs)`}
        meter={successRate}
      >
        Workflows executing end-to-end to verified state
      </KpiTile>

      <KpiTile
        id="verifier-accuracy"
        tone="kr-approve"
        icon={ShieldCheck}
        label="Verifier Accuracy"
        target="Target ≥ 90%"
        passed={isAccuracyPassed}
        value={`${verifierAccuracyPct}%`}
        unit="precision"
        meter={verifierAccuracy}
      >
        Layered verifier (DOM + visual + network) without false alarms
      </KpiTile>

      <KpiTile
        id="recovery-rate"
        tone="kr-plan"
        icon={LifeBuoy}
        label="Recovery Rate"
        target="Target ≥ 50%"
        passed={isRecoveryPassed}
        warnOnly
        value={recoveryRatePct}
        unit="replan success"
        meter={recoveryRate ?? 0}
      >
        Automatic recovery from transient DOM drift and step failures
      </KpiTile>

      <KpiTile
        id="latency-profile"
        tone="kr-run"
        icon={Gauge}
        label="Latency Profile"
        target="Target < 60s"
        passed={isLatencyPassed}
        warnOnly
        value={formatMs(avgLatencyMs)}
        unit="mean total"
        meter={Math.max(0, 1 - avgLatencyMs / 90000)}
      >
        <span className="flex items-center justify-between font-mono">
          <span>Plan: {planningLatencyMs == null ? "not measured" : formatMs(planningLatencyMs)} (&lt; 15s)</span>
          <span>P90: {formatMs(p90LatencyMs)}</span>
        </span>
      </KpiTile>
    </div>
  );
}

function KpiTile({
  id,
  tone,
  icon: Icon,
  label,
  target,
  passed,
  warnOnly = false,
  value,
  unit,
  meter,
  children,
}: {
  id: string;
  tone: string;
  icon: LucideIcon;
  label: string;
  target: string;
  passed: boolean;
  warnOnly?: boolean;
  value: string;
  unit: string;
  meter: number;
  children: ReactNode;
}) {
  const badgeColor = passed ? "var(--verify)" : warnOnly ? "var(--plan)" : "var(--danger)";
  return (
    <div data-testid={`kpi-${id}`} className={`${tone} kr-tone-card group relative overflow-hidden rounded-3xl p-5`}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-ink-300">
          <span
            className="flex size-7 items-center justify-center rounded-lg text-ink-950 transition-transform group-hover:rotate-12"
            style={{ background: "var(--kr-tone)" }}
          >
            <Icon aria-hidden="true" className="size-4" />
          </span>
          {label}
        </span>
        <span
          data-testid={`badge-${id}`}
          className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold"
          style={{
            color: badgeColor,
            borderColor: `color-mix(in oklab, ${badgeColor} 45%, transparent)`,
            background: `color-mix(in oklab, ${badgeColor} 14%, transparent)`,
          }}
        >
          <span className="size-1.5 rounded-full" style={{ background: badgeColor, boxShadow: `0 0 8px ${badgeColor}` }} />
          {target}
        </span>
      </div>

      <div className="mt-4 flex items-baseline gap-2">
        <span
          data-testid={`value-${id}`}
          className="kr-display text-4xl font-extrabold tracking-tight"
          style={{ color: "var(--kr-tone)", textShadow: "0 0 28px var(--kr-tone)" }}
        >
          {value}
        </span>
        <span className="text-xs text-ink-400">{unit}</span>
      </div>

      <div aria-hidden="true" className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.min(100, Math.max(0, meter * 100))}%`,
            background: "linear-gradient(90deg, var(--kr-tone), white)",
            boxShadow: "0 0 12px var(--kr-tone)",
          }}
        />
      </div>

      <p className="mt-3 text-xs text-ink-300">{children}</p>
    </div>
  );
}
