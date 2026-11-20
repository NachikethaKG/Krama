import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { TutorialSpec } from "@krama/contracts-ts";
import { BUNDLED_FONTS, STRINGS, needsBundledFonts, videoStrings } from "../src/i18n.js";
import { buildTutorialChapters } from "../src/metadata/chapters.js";

const here = path.dirname(fileURLToPath(import.meta.url));

const SPEC: TutorialSpec = {
  version: "1.0",
  workflow_id: "wf-1",
  title: "रिपॉज़िटरी बनाएँ",
  viewport: { width: 1280, height: 800 },
  total_duration_ms: 3000,
  scenes: [
    {
      id: "s1",
      step_seq: 1,
      title: null,
      start_ms: 0,
      duration_ms: 3000,
      action: { type: "click" },
      recording: { start_ms: 0, end_ms: 3000 },
      caption: { text: "“New repository” पर क्लिक करें।" },
    },
  ],
} as TutorialSpec;

describe("video languages (#429)", () => {
  it("names the chapters in the tutorial's language", () => {
    const chapters = buildTutorialChapters(SPEC, 2000, 2000, "hi");

    expect(chapters.map((c) => c.title)).toEqual(["परिचय", "चरण 1: “New repository” पर क्लिक करें।", "पूरा हुआ"]);
    expect(buildTutorialChapters(SPEC, 2000, 2000, "de")[0].title).toBe("Einführung");
    expect(buildTutorialChapters(SPEC).at(-1)?.title).toBe("Done");
  });

  it("has every string for every language, English for anything unknown", () => {
    for (const words of Object.values(STRINGS)) {
      expect(words.intro && words.done && words.madeWith).toBeTruthy();
      expect(words.step(2)).toContain("2");
      expect(words.verifiedOn("github.com")).toContain("github.com");
    }
    expect(videoStrings("xx")).toBe(STRINGS.en);
    expect(videoStrings(null)).toBe(STRINGS.en);
    expect(STRINGS.fr.voiceCredit).toContain("CC BY 4.0"); // the French voice needs attribution
  });

  it("bundles the Indic fonts it loads, with their license", () => {
    expect(needsBundledFonts("hi") && needsBundledFonts("kn")).toBe(true);
    expect(needsBundledFonts("de") || needsBundledFonts(undefined)).toBe(false);
    for (const font of BUNDLED_FONTS) {
      expect(existsSync(path.resolve(here, "../fonts", font.file))).toBe(true);
    }
    expect(existsSync(path.resolve(here, "../fonts/OFL.txt"))).toBe(true);
  });
});
