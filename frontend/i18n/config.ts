/**
 * The app's own UI languages (#423, decisions L1-L3). Separate from a tutorial's language (#427): someone can read
 * the app in Hindi and watch a tutorial in German.
 */

export const LOCALES = ["en", "hi", "kn"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

/** Set by the language picker; read before Accept-Language. No locale in the URL (L2). */
export const LOCALE_COOKIE = "KRAMA_LOCALE";

/** Each language's own name, for the picker. */
export const LOCALE_NAMES: Record<Locale, string> = { en: "English", hi: "हिन्दी", kn: "ಕನ್ನಡ" };

export function isLocale(value: string | null | undefined): value is Locale {
  return LOCALES.includes(value as Locale);
}

/** The best supported language for an Accept-Language header ("hi-IN,hi;q=0.9,en;q=0.8" -> "hi"). */
export function fromAcceptLanguage(header: string | null | undefined): Locale {
  const ranked = (header ?? "")
    .split(",")
    .map((part, i) => {
      const [tag, ...params] = part.trim().split(";");
      const q = Number(params.find((p) => p.trim().startsWith("q="))?.split("=")[1] ?? 1);
      return { lang: tag.toLowerCase().split("-")[0], q: Number.isFinite(q) ? q : 0, i };
    })
    .filter((r) => r.lang && r.q > 0)
    .sort((a, b) => b.q - a.q || a.i - b.i);
  return ranked.map((r) => r.lang).find(isLocale) ?? DEFAULT_LOCALE;
}

/** Message files are split by area (messages/<locale>/<namespace>.json) so areas can be translated apart. */
export const NAMESPACES = [
  "common",
  "shell",
  "home",
  "auth",
  "library",
  "tutorial",
  "player",
  "runs",
  "execution",
  "approval",
  "safety",
  "reviews",
  "export",
  "share",
  "doIt",
  "takeover",
  "metrics",
  "landing",
] as const;
export type Namespace = (typeof NAMESPACES)[number];
