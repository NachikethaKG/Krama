"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Check, Languages } from "lucide-react";
import { LOCALES, LOCALE_COOKIE, LOCALE_NAMES, LOCALE_SHORT, type Locale } from "@/i18n/config";

function saveLocale(next: Locale): void {
  document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
}

/**
 * The app's own language (#423): a cookie the server reads on the next request; no URL change (L2).
 * A small pill with the language's own mark (EN / हि / ಕ) and a menu, so it never crowds the header.
 */
export function LanguagePicker() {
  const t = useTranslations("common");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    const escape = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  const choose = (next: Locale) => {
    setOpen(false);
    if (next === locale) return;
    saveLocale(next);
    router.refresh();
  };

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        data-testid="language-picker"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${t("language.label")}: ${LOCALE_NAMES[locale]}`}
        title={LOCALE_NAMES[locale]}
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 items-center gap-1 rounded-full bg-white/5 px-2.5 text-xs font-bold text-ink-200 transition-colors hover:bg-white/10 hover:text-white"
      >
        <Languages aria-hidden="true" className="size-3.5" />
        <span lang={locale}>{LOCALE_SHORT[locale]}</span>
      </button>
      {open ? (
        <div
          role="menu"
          aria-label={t("language.label")}
          className="kr-glass absolute right-0 top-full z-40 mt-2 min-w-36 rounded-2xl p-1 shadow-xl"
        >
          {LOCALES.map((l) => (
            <button
              key={l}
              type="button"
              role="menuitemradio"
              aria-checked={l === locale}
              data-testid={`language-option-${l}`}
              onClick={() => choose(l)}
              className={`flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm transition-colors hover:bg-white/10 ${
                l === locale ? "font-bold text-white" : "text-ink-300"
              }`}
            >
              <span lang={l} className="flex-1">
                {LOCALE_NAMES[l]}
              </span>
              {l === locale ? <Check aria-hidden="true" className="size-3.5" /> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
