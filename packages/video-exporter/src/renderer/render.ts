import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import type { RenderVideoOptions, RenderVideoResult, VideoExportProps } from "../types.js";
import { buildTutorialChapters, formatFFMetadata } from "../metadata/chapters.js";
import { generateWebVTT } from "../metadata/webvtt.js";
import { addMp4Chapters } from "../metadata/mp4-chapters.js";
import { calculateTotalFrames } from "../compositions/TutorialComposition.js";
import { BUNDLED_FONTS, needsBundledFonts } from "../i18n.js";

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
    language,
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
    language,
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

  // 4. Bundle Remotion entry. Chromium can't load local paths (C:\..., file://), so local screenshots and
  // narration clips are copied into the bundle's public folder and referenced by name (staticFile).
  const publicDir = await fs.mkdtemp(path.join(os.tmpdir(), "krama-remotion-public-"));
  const servedScreenshots = await copyIntoPublic(screenshots, publicDir, "shot");
  const servedAudio = await copyIntoPublic(audioUrls, publicDir, "audio");
  if (needsBundledFonts(language)) {
    for (const font of BUNDLED_FONTS) {
      await fs.copyFile(path.resolve(__dirname, "../../fonts", font.file), path.join(publicDir, font.file));
    }
  }
  const entryFile = path.resolve(__dirname, "../entry.ts");
  const bundleLocation = await bundle({
    entryPoint: entryFile,
    publicDir,
    // The sources use TypeScript's ESM import style (`./Root.js` for `Root.tsx`); webpack needs the mapping.
    webpackOverride: (config) => ({
      ...config,
      resolve: {
        ...config.resolve,
        extensionAlias: { ".js": [".tsx", ".ts", ".js"] },
      },
    }),
  });

  const compositionId = preset === "portrait" ? "TutorialPortrait" : "TutorialLandscape";

  const inputProps: VideoExportProps = {
    spec,
    preset,
    manifest,
    audioUrls: servedAudio,
    screenshots: servedScreenshots,
    site,
    verifiedDate,
    language,
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

  await fs.rm(publicDir, { recursive: true, force: true });

  // 7. Chapter markers inside the MP4 (D12). Remotion doesn't write chapters, and its bundled ffmpeg can't read
  // FFMETADATA, so they go in as a Nero chapter box (the metadata file above stays for other tools).
  const rendered = await fs.readFile(outputPath);
  await fs.writeFile(outputPath, addMp4Chapters(rendered, chapters));

  return {
    outputPath,
    durationMs,
    totalFrames,
    chapters,
    vttPath,
    metadataPath,
  };
}

/**
 * Copies local files into the bundle's public folder and returns their names there (for `staticFile`).
 * URLs (http, https, data) are passed through unchanged.
 */
async function copyIntoPublic(
  files: Record<number, string>,
  publicDir: string,
  prefix: string,
): Promise<Record<number, string>> {
  const served: Record<number, string> = {};
  for (const [seq, source] of Object.entries(files)) {
    if (/^(https?:|data:)/.test(source)) {
      served[Number(seq)] = source;
      continue;
    }
    const name = `${prefix}-${seq}${path.extname(source)}`;
    await fs.copyFile(source, path.join(publicDir, name));
    served[Number(seq)] = name;
  }
  return served;
}
