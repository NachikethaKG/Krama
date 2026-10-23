"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ApiClient, getApiClient } from "@/lib/api";
import type { User } from "@krama/contracts-ts";

export interface DashboardHeaderProps {
  user: User;
  client?: ApiClient;
  onLogout?: () => void;
}

export function DashboardHeader({ user, client, onLogout }: DashboardHeaderProps) {
  const router = useRouter();
  const [apiClient] = useState<ApiClient>(() => client ?? getApiClient());
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await apiClient.logout();
      if (typeof document !== "undefined") {
        document.cookie = "krama_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
      }
      if (onLogout) {
        onLogout();
      } else {
        router.push("/login");
        router.refresh();
      }
    } catch {
      // In case of logout failure, force clear cookie and redirect
      if (typeof document !== "undefined") {
        document.cookie = "krama_session=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
      }
      router.push("/login");
      router.refresh();
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <header className="border-b border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      {/* Navigation breadcrumb bar */}
      <div className="border-b border-zinc-100 dark:border-zinc-800/60 px-4 py-2.5 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-2.5 text-xs text-zinc-500">
            <Link
              href="/"
              className="font-medium text-zinc-700 hover:text-indigo-600 dark:text-zinc-300 dark:hover:text-indigo-400 transition-colors"
            >
              ← Krama Home
            </Link>
            <span className="text-zinc-300 dark:text-zinc-700">/</span>
            <span className="font-semibold text-zinc-900 dark:text-zinc-100">User Dashboard</span>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/tutorials"
              className="text-xs font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              Tutorial Library
            </Link>
            <span className="text-zinc-300 dark:text-zinc-700">·</span>
            <Link
              href="/runs"
              className="text-xs font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
            >
              All Runs
            </Link>
          </div>
        </div>
      </div>

      {/* Main user summary section */}
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white font-bold text-lg shadow-sm">
              {user.display_name ? user.display_name[0].toUpperCase() : user.email[0].toUpperCase()}
            </div>

            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 sm:text-2xl">
                  {user.display_name ?? user.email.split("@")[0]}
                </h1>
                <span
                  data-testid="user-plan-badge"
                  className="inline-flex items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-[11px] font-semibold text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300"
                >
                  <span className="size-1.5 rounded-full bg-indigo-500" />
                  Seeded Pro MVP
                </span>
              </div>
              <p
                data-testid="user-email-display"
                className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400 font-mono"
              >
                {user.email}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/runs/new"
              data-testid="dashboard-new-run-btn"
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 transition-colors"
            >
              <span>+ New Run</span>
            </Link>

            <button
              type="button"
              data-testid="dashboard-logout-btn"
              onClick={handleLogout}
              disabled={isLoggingOut}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-3.5 py-2 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50"
            >
              {isLoggingOut ? "Signing out…" : "Sign Out"}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
