"use client";

import type { Language } from "@krama/contracts-ts";
import { useTranslations } from "next-intl";

/** A tutorial's languages (#427, L3): separate from the app's own UI language (#423). */
export const TUTORIAL_LANGUAGES: readonly Language[] = ["en", "hi", "kn", "de", "es", "fr"];

/** Each language in its own script, the same in every UI language. */
export function TutorialLanguageSelect({
  value,
  onChange,
  label,
  testId = "tutorial-language-select",
  disabled = false,
}: {
  value: Language;
  onChange: (language: Language) => void;
  label: string;
  testId?: string;
  disabled?: boolean;
}) {
  const t = useTranslations("common");
  return (
    <label className="flex items-center gap-2 text-xs text-ink-300">
      <span>{label}</span>
      <select
        data-testid={testId}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as Language)}
        className="rounded-md border border-ink-700 bg-ink-900 px-2 py-1 text-xs text-ink-100"
      >
        {TUTORIAL_LANGUAGES.map((code) => (
          <option key={code} value={code} lang={code}>
            {t(`tutorialLanguages.${code}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
