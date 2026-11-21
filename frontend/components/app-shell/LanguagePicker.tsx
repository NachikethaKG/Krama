"use client";

import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Languages } from "lucide-react";
import { LOCALES, LOCALE_COOKIE, LOCALE_NAMES, type Locale } from "@/i18n/config";

/** The app's own language (#423): a cookie the server reads on the next request; no URL change (L2). */
export function LanguagePicker() {
  const t = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();

  const choose = (next: Locale) => {
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
    router.refresh();
  };

  return (
    <label className="flex items-center gap-1.5 text-xs text-ink-300">
      <Languages aria-hidden="true" className="size-3.5" />
      <span className="sr-only">{t("language.label")}</span>
      <select
        data-testid="language-picker"
        value={locale}
        onChange={(e) => choose(e.target.value as Locale)}
        className="rounded-md border border-ink-700 bg-ink-900 px-1.5 py-1 text-xs text-ink-100"
      >
        {LOCALES.map((l) => (
          <option key={l} value={l} lang={l}>
            {LOCALE_NAMES[l]}
          </option>
        ))}
      </select>
    </label>
  );
}
