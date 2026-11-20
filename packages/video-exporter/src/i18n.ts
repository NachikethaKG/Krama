/**
 * The video's own words per tutorial language (#429, #132): chapter names, the intro and outro cards. The step
 * texts and captions come translated from the backend (#422); these are the few fixed strings around them.
 * Hindi and Kannada need a native reader before they ship (docs/research/phase-6-nachiketha-multiple-languages.md).
 */

export type VideoLanguage = "en" | "hi" | "kn" | "de" | "es" | "fr";

export interface VideoStrings {
  intro: string;
  done: string;
  step: (n: number) => string;
  verifiedOn: (site: string) => string;
  madeWith: string;
  /** Attribution a CC BY voice needs (L7): shown in the outro. */
  voiceCredit?: string;
}

export const STRINGS: Record<VideoLanguage, VideoStrings> = {
  en: {
    intro: "Intro",
    done: "Done",
    step: (n) => `Step ${n}`,
    verifiedOn: (site) => `Verified on ${site}`,
    madeWith: "Made with Krama",
  },
  hi: {
    intro: "परिचय",
    done: "पूरा हुआ",
    step: (n) => `चरण ${n}`,
    verifiedOn: (site) => `${site} पर सत्यापित`,
    madeWith: "Krama से बनाया गया",
  },
  kn: {
    intro: "ಪರಿಚಯ",
    done: "ಮುಗಿದಿದೆ",
    step: (n) => `ಹಂತ ${n}`,
    verifiedOn: (site) => `${site} ನಲ್ಲಿ ಪರಿಶೀಲಿಸಲಾಗಿದೆ`,
    madeWith: "Krama ದಿಂದ ಮಾಡಲಾಗಿದೆ",
  },
  de: {
    intro: "Einführung",
    done: "Fertig",
    step: (n) => `Schritt ${n}`,
    verifiedOn: (site) => `Geprüft auf ${site}`,
    madeWith: "Erstellt mit Krama",
  },
  es: {
    intro: "Introducción",
    done: "Listo",
    step: (n) => `Paso ${n}`,
    verifiedOn: (site) => `Verificado en ${site}`,
    madeWith: "Hecho con Krama",
  },
  fr: {
    intro: "Introduction",
    done: "Terminé",
    step: (n) => `Étape ${n}`,
    verifiedOn: (site) => `Vérifié sur ${site}`,
    madeWith: "Réalisé avec Krama",
    voiceCredit: "Voix : siwis (CC BY 4.0)",
  },
};

/** The strings for `language`; English for anything unknown. */
export function videoStrings(language?: string | null): VideoStrings {
  return STRINGS[(language ?? "en") as VideoLanguage] ?? STRINGS.en;
}

/** Bundled fonts (SIL OFL 1.1, packages/video-exporter/fonts): Chromium on a Linux renderer has no Indic fonts. */
export const BUNDLED_FONTS = [
  { family: "Noto Sans Devanagari", file: "NotoSansDevanagari.ttf" },
  { family: "Noto Sans Kannada", file: "NotoSansKannada.ttf" },
] as const;

/** Text font for cards and captions: the bundled Indic fonts first, so Devanagari and Kannada always render. */
export const TEXT_FONT = `"Noto Sans Devanagari", "Noto Sans Kannada", system-ui, -apple-system, sans-serif`;

/** Languages whose script needs a bundled font. */
export function needsBundledFonts(language?: string | null): boolean {
  return language === "hi" || language === "kn";
}
