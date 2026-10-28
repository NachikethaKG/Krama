import { cookies, headers } from "next/headers";
import type { MetricsSummary } from "@krama/contracts-ts";
import { MetricsDashboardClient } from "@/components/metrics";
import { mockMetricsSummary } from "@/lib/fixtures";

export const metadata = {
  title: "Technical Metrics & Multi-Target Benchmark · Krama",
  description: "PRD §33 technical metrics dashboard covering Task Success Rate, Verifier Accuracy, Recovery Rate, and Latency Profile across Gitea and GitHub.",
};

async function fetchMetricsSummary(): Promise<MetricsSummary | null> {
  const isMockMode = process.env.NEXT_PUBLIC_API_MODE !== "http";
  if (isMockMode) {
    return mockMetricsSummary;
  }

  const rawBase =
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000/api/v1";
  const baseUrl = rawBase.endsWith("/api/v1") ? rawBase : `${rawBase}/api/v1`;
  const url = `${baseUrl}/metrics/summary`;

  try {
    const cookieStore = await cookies();
    const cookieHeader = cookieStore.toString();
    const headerStore = await headers();

    const fetchHeaders: Record<string, string> = {
      Accept: "application/json",
      "X-Krama": "1",
    };
    if (cookieHeader) {
      fetchHeaders["Cookie"] = cookieHeader;
    }
    const authorization = headerStore.get("authorization");
    if (authorization) {
      fetchHeaders["Authorization"] = authorization;
    }

    const res = await fetch(url, {
      method: "GET",
      headers: fetchHeaders,
      cache: "no-store",
    });

    if (!res.ok) {
      return null;
    }

    return (await res.json()) as MetricsSummary;
  } catch {
    // If backend isn't ready or hasn't produced summary yet, return null for graceful empty state
    return null;
  }
}

export default async function MetricsPage() {
  const summary = await fetchMetricsSummary();

  return <MetricsDashboardClient initialData={summary} />;
}
