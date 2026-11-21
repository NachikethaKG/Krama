"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, LayoutDashboard, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ApiClient, getApiClient } from "@/lib/api";

export interface DashboardNavProps {
  pendingCount?: number;
  activeTab?: "overview" | "reviews" | "metrics";
  onTabChange?: (tab: string) => void;
  client?: ApiClient;
  className?: string;
}

export function DashboardNav({
  pendingCount: initialCount,
  activeTab,
  client,
  className = "",
}: DashboardNavProps) {
  const t = useTranslations("shell");
  const pathname = usePathname() ?? "/dashboard";
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [fetchedCount, setFetchedCount] = useState<number>(0);

  const count = initialCount !== undefined ? initialCount : fetchedCount;

  useEffect(() => {
    if (initialCount !== undefined) return;

    let isMounted = true;
    apiClient
      .getReviewQueueCount()
      .then((res) => {
        if (isMounted) setFetchedCount(res.count);
      })
      .catch(() => undefined);

    const handleCountChange = (e: Event) => {
      const customEvent = e as CustomEvent<{ count: number }>;
      if (customEvent.detail && typeof customEvent.detail.count === "number") {
        setFetchedCount(customEvent.detail.count);
      } else {
        apiClient.getReviewQueueCount().then((res) => isMounted && setFetchedCount(res.count)).catch(() => undefined);
      }
    };

    window.addEventListener("krama:review-count-changed", handleCountChange);
    return () => {
      isMounted = false;
      window.removeEventListener("krama:review-count-changed", handleCountChange);
    };
  }, [apiClient, initialCount]);

  const navItems = [
    {
      id: "overview",
      label: t("dashboardNav.overview"),
      href: "/",
      icon: LayoutDashboard,
      active: activeTab === "overview" || pathname === "/" || pathname === "/dashboard",
    },
    {
      id: "reviews",
      label: t("dashboardNav.reviews"),
      href: "/dashboard/reviews",
      icon: ShieldAlert,
      active: activeTab === "reviews" || pathname.startsWith("/dashboard/reviews"),
      badge: count,
    },
    {
      id: "metrics",
      label: t("dashboardNav.metrics"),
      href: "/dashboard/metrics",
      icon: BarChart3,
      active: activeTab === "metrics" || pathname.startsWith("/dashboard/metrics"),
    },
  ];

  return (
    <nav
      data-testid="dashboard-nav"
      aria-label={t("dashboardNav.label")}
      className={`flex items-center gap-2 border-b border-white/10 pb-4 ${className}`}
    >
      {navItems.map((item) => {
        const Icon = item.icon;
        return (
          <Link
            key={item.id}
            href={item.href}
            data-testid={item.id === "reviews" ? "review-queue-nav-link" : `nav-${item.id}`}
            aria-current={item.active ? "page" : undefined}
            className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition-all ${
              item.active
                ? "bg-white/10 text-white shadow-xs"
                : "text-ink-400 hover:bg-white/5 hover:text-white"
            }`}
          >
            <Icon className="size-4" aria-hidden="true" />
            <span>{item.label}</span>
            {item.badge !== undefined && (
              item.badge > 0 ? (
                <span
                  data-testid="review-queue-badge"
                  aria-label={t("header.pendingReviews", { count: item.badge })}
                  className="inline-flex size-5 items-center justify-center rounded-full bg-rose-500 text-[10px] font-extrabold text-white"
                >
                  {item.badge}
                </span>
              ) : (
                <span data-testid="review-queue-badge" className="hidden">0</span>
              )
            )}
          </Link>
        );
      })}
    </nav>
  );
}
