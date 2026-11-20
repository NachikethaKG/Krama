import type { TutorialSpec } from "@krama/contracts-ts";
import { videoStrings } from "../i18n.js";
import type { VideoChapter } from "../types.js";

/** Longest chapter title before it is shortened at a word boundary (players show one line). */
export const MAX_CHAPTER_TITLE = 60;

/**
 * A step's chapter name (#395): the step's own text, as the learner reads it in the captions, without the final
 * period and shortened at a word boundary. The scene title (the target's accessible name, e.g. "Repository
 * name *") is only a fallback: it read differently from step to step and kept required-field stars.
 */
export function chapterTitle(text: string | null | undefined, max = MAX_CHAPTER_TITLE): string | null {
  const clean = (text ?? "").replace(/\s+/g, " ").trim().replace(/\s*\*$/, "").replace(/[.]$/, "");
  if (!clean) return null;
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return `${(space > max / 2 ? cut.slice(0, space) : cut).replace(/[\s,;:]+$/, "")}…`;
}

/**
 * Builds the chapter list for a tutorial video (Decision D12).
 * Formats: Intro (2s), Step 1..N, Done (2s).
 */
export function buildTutorialChapters(
  spec: TutorialSpec,
  introDurationMs = 2000,
  outroDurationMs = 2000,
  language?: string,
): VideoChapter[] {
  const chapters: VideoChapter[] = [];
  const words = videoStrings(language);

  // Chapter 1: Intro
  chapters.push({
    title: words.intro,
    startMs: 0,
    endMs: introDurationMs,
  });

  let currentOffset = introDurationMs;

  // Step chapters
  spec.scenes.forEach((scene, index) => {
    const stepNumber = scene.step_seq ?? index + 1;
    const cleanTitle = chapterTitle(scene.caption?.text) ?? chapterTitle(scene.title) ?? words.step(stepNumber);
    const duration = scene.duration_ms;

    chapters.push({
      title: `${words.step(stepNumber)}: ${cleanTitle}`,
      startMs: currentOffset,
      endMs: currentOffset + duration,
    });

    currentOffset += duration;
  });

  // Final Chapter: Done
  chapters.push({
    title: words.done,
    startMs: currentOffset,
    endMs: currentOffset + outroDurationMs,
  });

  return chapters;
}

/**
 * Escapes special characters for FFMETADATA format (=, ;, #, \, :)
 */
function escapeFFMetadataValue(str: string): string {
  return str
    .replace(/\\/g, "\\\\")
    .replace(/=/g, "\\=")
    .replace(/;/g, "\\;")
    .replace(/#/g, "\\#")
    .replace(/:/g, "\\:");
}

/**
 * Formats chapters into FFmpeg FFMETADATA1 plaintext syntax.
 */
export function formatFFMetadata(title: string, chapters: VideoChapter[]): string {
  const lines: string[] = [";FFMETADATA1", `title=${escapeFFMetadataValue(title)}`, ""];

  for (const chapter of chapters) {
    lines.push("[CHAPTER]");
    lines.push("TIMEBASE=1/1000");
    lines.push(`START=${Math.round(chapter.startMs)}`);
    lines.push(`END=${Math.round(chapter.endMs)}`);
    lines.push(`title=${escapeFFMetadataValue(chapter.title)}`);
    lines.push("");
  }

  return lines.join("\n");
}
