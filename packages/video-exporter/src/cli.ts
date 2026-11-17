import fs from "node:fs/promises";
import path from "node:path";
import type { TutorialSpec } from "@krama/contracts-ts";
import { compileWorkflow } from "@krama/tutorial-compiler";
import type { NarrationManifestData, VideoPreset } from "./types.js";
import { renderTutorialVideo } from "./renderer/render.js";

function parseArgs(): Record<string, string> {
  const args = process.argv.slice(2);
  const result: Record<string, string> = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const next = args[i + 1];
      if (next && !next.startsWith("--")) {
        result[key] = next;
        i++;
      } else {
        result[key] = "true";
      }
    }
  }

  return result;
}

async function main() {
  const args = parseArgs();

  const specPath = args.spec;
  const workflowPath = args.workflow;
  const outputPath = args.output;
  const preset = (args.preset || "landscape") as VideoPreset;
  const manifestPath = args.manifest;
  const screenshotsJson = args.screenshots;
  const audioJson = args.audio;
  const site = args.site || "git.local";
  const verifiedDate = args.date || new Date().toISOString().split("T")[0];
  const vttPath = args.vtt;
  const metadataPath = args.metadata;
  const concurrency = args.concurrency ? parseInt(args.concurrency, 10) : 4;

  if ((!specPath && !workflowPath) || !outputPath) {
    console.error(
      "Usage: node cli.js (--spec <spec.json> | --workflow <workflow.json>) --output <out.mp4> [--preset landscape|portrait] [--manifest manifest.json] [--screenshots screenshots.json] [--audio audio.json] [--vtt out.vtt] [--metadata metadata.txt]",
    );
    process.exit(1);
  }

  let manifest: NarrationManifestData | undefined;
  if (manifestPath) {
    const manifestContent = await fs.readFile(path.resolve(manifestPath), "utf-8");
    manifest = JSON.parse(manifestContent);
  }

  let spec: TutorialSpec;
  if (specPath) {
    const specContent = await fs.readFile(path.resolve(specPath), "utf-8");
    spec = JSON.parse(specContent);
  } else {
    const workflowContent = await fs.readFile(path.resolve(workflowPath!), "utf-8");
    const workflow = JSON.parse(workflowContent);
    const stepDurations: Record<number, number> = {};
    if (manifest?.clips) {
      for (const clip of manifest.clips) {
        stepDurations[clip.step_seq] = clip.duration_ms;
      }
    }
    spec = compileWorkflow(workflow, {
      fps: 30,
      stepDurations: Object.keys(stepDurations).length > 0 ? stepDurations : undefined,
    });
  }

  let screenshots: Record<number, string> | undefined;
  if (screenshotsJson) {
    try {
      if (screenshotsJson.startsWith("{")) {
        screenshots = JSON.parse(screenshotsJson);
      } else {
        const content = await fs.readFile(path.resolve(screenshotsJson), "utf-8");
        screenshots = JSON.parse(content);
      }
    } catch {
      // Ignored
    }
  }

  let audioUrls: Record<number, string> | undefined;
  if (audioJson) {
    try {
      if (audioJson.startsWith("{")) {
        audioUrls = JSON.parse(audioJson);
      } else {
        const content = await fs.readFile(path.resolve(audioJson), "utf-8");
        audioUrls = JSON.parse(content);
      }
    } catch {
      // Ignored
    }
  }

  const result = await renderTutorialVideo({
    spec,
    preset,
    outputPath: path.resolve(outputPath),
    manifest,
    audioUrls,
    screenshots,
    site,
    verifiedDate,
    concurrency,
    vttPath: vttPath ? path.resolve(vttPath) : undefined,
    metadataPath: metadataPath ? path.resolve(metadataPath) : undefined,
    onProgress: (percent) => {
      console.log(JSON.stringify({ type: "progress", percent }));
    },
  });

  console.log(JSON.stringify({ type: "completed", result }));
}

main().catch((err) => {
  console.error(JSON.stringify({ type: "error", message: err.message, stack: err.stack }));
  process.exit(1);
});
