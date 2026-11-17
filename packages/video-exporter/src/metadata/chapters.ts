import type { TutorialSpec } from "@krama/contracts-ts";
import type { VideoChapter } from "../types.js";

/**
 * Builds the chapter list for a tutorial video (Decision D12).
 * Formats: Intro (2s), Step 1..N, Done (2s).
 */
export function buildTutorialChapters(
  spec: TutorialSpec,
  introDurationMs = 2000,
  outroDurationMs = 2000,
): VideoChapter[] {
  const chapters: VideoChapter[] = [];

  // Chapter 1: Intro
  chapters.push({
    title: "Intro",
    startMs: 0,
    endMs: introDurationMs,
  });

  let currentOffset = introDurationMs;

  // Step chapters
  spec.scenes.forEach((scene, index) => {
    const stepNumber = scene.step_seq ?? index + 1;
    const cleanTitle = scene.title || scene.caption?.text || `Step ${stepNumber}`;
    const duration = scene.duration_ms;

    chapters.push({
      title: `Step ${stepNumber}: ${cleanTitle}`,
      startMs: currentOffset,
      endMs: currentOffset + duration,
    });

    currentOffset += duration;
  });

  // Final Chapter: Done
  chapters.push({
    title: "Done",
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
