"use client";

import type { MetricsSummary } from "@krama/contracts-ts";
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
    <div
      data-testid="metrics-kpi-grid"
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
    >
      {/* 1. Success Rate KPI */}
      <div
        data-testid="kpi-success-rate"
        className="relative overflow-hidden rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider dark:text-zinc-400">
            Task Success Rate
          </span>
          <span
            data-testid="badge-success-rate"
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
              isSuccessPassed
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                : "bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300 border border-rose-200 dark:border-rose-800"
            }`}
          >
            <span
              className={`size-1.5 rounded-full ${
                isSuccessPassed ? "bg-emerald-500" : "bg-rose-500"
              }`}
            />
            Target ≥ 80%
          </span>
        </div>

        <div className="mt-3 flex items-baseline gap-2">
          <span
            data-testid="value-success-rate"
            className="text-3xl font-extrabold tracking-tight text-zinc-900 dark:text-zinc-50 font-mono"
          >
            {successRatePct}%
          </span>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            ({summary.overall_successful_runs ?? 0}/{summary.overall_total_runs ?? 0} runs)
          </span>
        </div>

        <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
          Workflows executing end-to-end to verified state
        </p>
      </div>

      {/* 2. Verifier Accuracy KPI */}
      <div
        data-testid="kpi-verifier-accuracy"
        className="relative overflow-hidden rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider dark:text-zinc-400">
            Verifier Accuracy
          </span>
          <span
            data-testid="badge-verifier-accuracy"
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
              isAccuracyPassed
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                : "bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300 border border-rose-200 dark:border-rose-800"
            }`}
          >
            <span
              className={`size-1.5 rounded-full ${
                isAccuracyPassed ? "bg-emerald-500" : "bg-rose-500"
              }`}
            />
            Target ≥ 90%
          </span>
        </div>

        <div className="mt-3 flex items-baseline gap-2">
          <span
            data-testid="value-verifier-accuracy"
            className="text-3xl font-extrabold tracking-tight text-zinc-900 dark:text-zinc-50 font-mono"
          >
            {verifierAccuracyPct}%
          </span>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">precision</span>
        </div>

        <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
          Layered verifier (DOM + visual + network) without false alarms
        </p>
      </div>

      {/* 3. Recovery Rate KPI */}
      <div
        data-testid="kpi-recovery-rate"
        className="relative overflow-hidden rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider dark:text-zinc-400">
            Recovery Rate
          </span>
          <span
            data-testid="badge-recovery-rate"
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
              isRecoveryPassed
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                : "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
            }`}
          >
            <span
              className={`size-1.5 rounded-full ${
                isRecoveryPassed ? "bg-emerald-500" : "bg-amber-500"
              }`}
            />
            Target ≥ 50%
          </span>
        </div>

        <div className="mt-3 flex items-baseline gap-2">
          <span
            data-testid="value-recovery-rate"
            className="text-3xl font-extrabold tracking-tight text-zinc-900 dark:text-zinc-50 font-mono"
          >
            {recoveryRatePct}
          </span>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">replan success</span>
        </div>

        <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
          Automatic recovery from transient DOM drift and step failures
        </p>
      </div>

      {/* 4. Latency Profile KPI */}
      <div
        data-testid="kpi-latency-profile"
        className="relative overflow-hidden rounded-xl border border-zinc-200 bg-white p-5 shadow-xs dark:border-zinc-800 dark:bg-zinc-950"
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider dark:text-zinc-400">
            Latency Profile
          </span>
          <span
            data-testid="badge-latency-profile"
            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
              isLatencyPassed
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                : "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
            }`}
          >
            <span
              className={`size-1.5 rounded-full ${
                isLatencyPassed ? "bg-emerald-500" : "bg-amber-500"
              }`}
            />
            Target &lt; 60s
          </span>
        </div>

        <div className="mt-3 flex items-baseline gap-2">
          <span
            data-testid="value-latency-profile"
            className="text-3xl font-extrabold tracking-tight text-zinc-900 dark:text-zinc-50 font-mono"
          >
            {formatMs(avgLatencyMs)}
          </span>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">mean total</span>
        </div>

        <div className="mt-2 flex items-center justify-between text-xs text-zinc-600 dark:text-zinc-400 font-mono">
          <span>Plan: {planningLatencyMs == null ? "not measured" : formatMs(planningLatencyMs)} (&lt; 15s)</span>
          <span>P90: {formatMs(p90LatencyMs)}</span>
        </div>
      </div>
    </div>
  );
}
