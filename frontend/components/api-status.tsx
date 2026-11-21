"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { type ApiClient, getApiClient } from "@/lib/api";

export type SystemStatus = "online" | "offline" | "checking";

export interface ApiStatusBadgeProps {
  status: SystemStatus;
  className?: string;
}

export function ApiStatusBadge({ status, className = "" }: ApiStatusBadgeProps) {
  // The status wears a spectrum colour: lime when up, coral when down, amber while checking.
  const t = useTranslations("landing.apiStatus");
  const tone = status === "online" ? "kr-verify" : status === "offline" ? "kr-danger" : "kr-plan";

  const label = t(status === "online" ? "online" : status === "offline" ? "offline" : "checking");

  return (
    <div
      className={`${tone} kr-chip !px-3 !py-1 ${className}`}
      aria-label={t("label")}
      role="status"
    >
      <span className={`kr-dot !size-2 ${status === "offline" ? "" : "kr-dot-live"}`} />
      <span>{label}</span>
    </div>
  );
}

export interface ApiStatusProps {
  client?: ApiClient;
  showOfflineBanner?: boolean;
  className?: string;
}

export function ApiStatus({
  client,
  showOfflineBanner = true,
  className = "",
}: ApiStatusProps) {
  const t = useTranslations("landing.apiStatus");
  const [status, setStatus] = useState<SystemStatus>("checking");

  useEffect(() => {
    let mounted = true;
    const api = client ?? getApiClient();

    api
      .health()
      .then((health) => {
        if (!mounted) return;
        if (health && health.status === "ok") {
          setStatus("online");
        } else {
          setStatus("offline");
        }
      })
      .catch(() => {
        if (mounted) {
          setStatus("offline");
        }
      });

    return () => {
      mounted = false;
    };
  }, [client]);

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {showOfflineBanner && status === "offline" && (
        <div
          role="alert"
          aria-label={t("offlineLabel")}
          className="kr-plan kr-tone-card rounded-2xl px-3 py-2 text-xs text-plan"
        >
          <div className="flex items-center gap-2">
            <span className="kr-dot !size-1.5" />
            <span>{t("offlineBanner")}</span>
          </div>
        </div>
      )}
      <ApiStatusBadge status={status} />
    </div>
  );
}
