"use client";

import type { Language } from "@krama/contracts-ts";
import { ChevronDown, Languages } from "lucide-react";
import { useTranslations } from "next-intl";

/** A tutorial's languages (#427, L3): separate from the app's own UI language (#423). */
export const TUTORIAL_LANGUAGES: readonly Language[] = ["en", "hi", "kn", "de", "es", "fr"];

/**
 * Each language in its own script, the same in every UI language. A pill like the player's other actions,
 * with a real <select> inside (keyboard and screen readers as usual); the label is for screen readers.
 */
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
    <label
      title={label}
      className={`kr-chip relative inline-flex items-center gap-1.5 pr-1.5 transition-colors ${
        disabled ? "opacity-60" : "cursor-pointer hover:text-white"
      }`}
    >
      <Languages aria-hidden="true" className="size-3.5" />
      <span className="sr-only">{label}</span>
      <select
        data-testid={testId}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as Language)}
        className="cursor-pointer appearance-none bg-transparent pr-4 font-semibold outline-none disabled:cursor-wait"
      >
        {TUTORIAL_LANGUAGES.map((code) => (
          <option key={code} value={code} lang={code} className="bg-ink-900 text-ink-100">
            {t(`tutorialLanguages.${code}`)}
          </option>
        ))}
      </select>
      <ChevronDown aria-hidden="true" className="pointer-events-none absolute right-1.5 size-3" />
    </label>
  );
}
