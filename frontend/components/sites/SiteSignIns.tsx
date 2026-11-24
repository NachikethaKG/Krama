"use client";

import { useEffect, useId, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { SiteProfile } from "@krama/contracts-ts";

import { type ApiClient, errorMessage, getApiClient, isApiError } from "@/lib/api";

export interface SiteSignInsProps {
  initialUrl?: string;
  client?: ApiClient;
}

/** A site key as a person reads it: the host of an origin, or the name (github, gitea). */
export function siteLabel(site: string): string {
  try {
    return site.includes("://") ? new URL(site).host : site;
  } catch {
    return site;
  }
}

function validUrl(value: string): boolean {
  try {
    const u = new URL(value.trim());
    return u.protocol === "https:" || u.protocol === "http:";
  } catch {
    return false;
  }
}

/**
 * Your sign-ins (ADR 0012): the sites Krama keeps a session for, each one forgettable, and a form to sign in to any
 * public site by hand. Signing in opens the site in Krama's browser, paused for you to take over.
 */
export function SiteSignIns({ initialUrl = "", client }: SiteSignInsProps) {
  const t = useTranslations("sites");
  const router = useRouter();
  const [api] = useState<ApiClient>(() => client ?? getApiClient());
  const [profiles, setProfiles] = useState<SiteProfile[] | null>(null);
  const [url, setUrl] = useState(initialUrl);
  const [termsOk, setTermsOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const urlId = useId();
  const termsId = useId();

  useEffect(() => {
    let active = true;
    api
      .listSiteProfiles()
      .then((list) => active && setProfiles(list.items))
      .catch(() => active && setProfiles([]));
    return () => {
      active = false;
    };
  }, [api]);

  const canSignIn = validUrl(url) && termsOk && !busy;

  const signIn = async () => {
    if (!canSignIn) return;
    setBusy(true);
    setError(null);
    try {
      const run = await api.startSignInAt(url.trim());
      router.push(`/runs/${encodeURIComponent(run.id)}/live?back=${encodeURIComponent("/sites")}`);
    } catch (err) {
      const sensitive = isApiError(err) && err.details?.reason === "sensitive_site";
      setError(sensitive ? t("form.sensitive") : errorMessage(err, t("form.failed")));
      setBusy(false);
    }
  };

  const forget = async (site: string) => {
    setError(null);
    try {
      await api.forgetSiteProfile(site);
      setProfiles((prev) => (prev ?? []).filter((p) => p.site !== site));
    } catch (err) {
      setError(errorMessage(err, t("list.forgetFailed")));
    }
  };

  return (
    <section data-testid="site-sign-ins" className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="kr-display text-3xl font-extrabold text-white">{t("title")}</h1>
        <p className="text-sm text-ink-300">{t("intro")}</p>
      </header>

      <div className="kr-tone-card kr-plan flex flex-col gap-3 rounded-2xl p-5">
        <label htmlFor={urlId} className="text-sm font-bold text-white">
          {t("form.url")}
        </label>
        <input
          id={urlId}
          data-testid="sign-in-url"
          type="url"
          inputMode="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={t("form.placeholder")}
          className="rounded-xl border border-white/15 bg-ink-850 px-3 py-2 text-sm text-white"
        />
        <label htmlFor={termsId} className="flex items-start gap-2 text-xs leading-relaxed text-ink-300">
          <input
            id={termsId}
            data-testid="sign-in-terms"
            type="checkbox"
            checked={termsOk}
            onChange={(e) => setTermsOk(e.target.checked)}
            className="mt-0.5"
          />
          <span>{t("form.terms")}</span>
        </label>
        <p className="text-xs text-ink-400">{t("form.refused")}</p>
        <button
          type="button"
          data-testid="sign-in-btn"
          disabled={!canSignIn}
          onClick={signIn}
          className="kr-btn kr-btn-tone kr-plan self-start px-4 py-2 text-sm disabled:opacity-50"
        >
          {busy ? t("form.opening") : t("form.signIn")}
        </button>
        {error && (
          <p role="alert" data-testid="sign-in-error" className="text-sm text-danger">
            {error}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <h2 className="text-lg font-bold text-white">{t("list.title")}</h2>
        {profiles === null ? (
          <p className="text-sm text-ink-400">{t("list.loading")}</p>
        ) : profiles.length === 0 ? (
          <p data-testid="site-list-empty" className="text-sm text-ink-400">
            {t("list.empty")}
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {profiles.map((p) => (
              <li
                key={p.site}
                data-testid="site-profile"
                className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-ink-850/60 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-white">{siteLabel(p.site)}</p>
                  <p className="truncate text-xs text-ink-400">{p.account}</p>
                </div>
                <button
                  type="button"
                  data-testid="forget-site"
                  onClick={() => forget(p.site)}
                  className="kr-btn kr-btn-ghost shrink-0 px-3 py-1.5 text-xs"
                >
                  {t("list.forget")}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
