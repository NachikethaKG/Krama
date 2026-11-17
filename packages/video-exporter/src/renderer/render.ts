import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import type { RenderVideoOptions, RenderVideoResult, VideoExportProps } from "../types.js";
import { buildTutorialChapters, formatFFMetadata } from "../metadata/chapters.js";
import { generateWebVTT } from "../metadata/webvtt.js";
import { calculateTotalFrames } from "../compositions/TutorialComposition.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Programmatically renders a TutorialSpec into an MP4 video using Remotion on CPU.
 */
export async function renderTutorialVideo(options: RenderVideoOptions): Promise<RenderVideoResult> {
  const {
    spec,
    preset,
    outputPath,
    manifest,
    audioUrls = {},
    screenshots = {},
    site = "git.local",
    verifiedDate = "2026-11-17",
    concurrency = 4,
    crf = 18,
    onProgress,
    metadataPath,
    vttPath,
  } = options;

  const fps = options.fps ?? 30;
  const introDurationFrames = options.introDurationFrames ?? 60;
  const outroDurationFrames = options.outroDurationFrames ?? 60;

  const totalFrames = calculateTotalFrames(spec, fps, introDurationFrames, outroDurationFrames);
  const durationMs = Math.round((totalFrames / fps) * 1000);

  // 1. Generate Chapters & Metadata
  const chapters = buildTutorialChapters(
    spec,
    Math.round((introDurationFrames / fps) * 1000),
    Math.round((outroDurationFrames / fps) * 1000),
  );

  if (metadataPath) {
    const ffmetadata = formatFFMetadata(spec.title, chapters);
    await fs.mkdir(path.dirname(metadataPath), { recursive: true });
    await fs.writeFile(metadataPath, ffmetadata, "utf-8");
  }

  // 2. Generate WebVTT Sidecar
  if (vttPath) {
    const vttContent = generateWebVTT(spec, Math.round((introDurationFrames / fps) * 1000));
    await fs.mkdir(path.dirname(vttPath), { recursive: true });
    await fs.writeFile(vttPath, vttContent, "utf-8");
  }

  // 3. Ensure destination directory exists
  await fs.mkdir(path.dirname(outputPath), { recursive: true });

  // 4. Bundle Remotion entry
  const entryFile = path.resolve(__dirname, "../entry.ts");
  const bundleLocation = await bundle({
    entryPoint: entryFile,
    webpackOverride: (config) => config,
  });

  const compositionId = preset === "portrait" ? "TutorialPortrait" : "TutorialLandscape";

  const inputProps: VideoExportProps = {
    spec,
    preset,
    manifest,
    audioUrls,
    screenshots,
    site,
    verifiedDate,
    fps,
    introDurationFrames,
    outroDurationFrames,
  };

  // 5. Select Composition
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: compositionId,
    inputProps: inputProps as unknown as Record<string, unknown>,
  });

  // 6. Render Media via CPU
  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: outputPath,
    inputProps: inputProps as unknown as Record<string, unknown>,
    concurrency,
    crf,
    pixelFormat: "yuv420p",
    onProgress: ({ progress }) => {
      if (onProgress) {
        onProgress(Math.round(progress * 100));
      }
    },
  });

  return {
    outputPath,
    durationMs,
    totalFrames,
    chapters,
    vttPath,
    metadataPath,
  };
}
