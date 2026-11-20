import fs from "node:fs/promises";
import path from "node:path";
import type { TutorialSpec, WordTiming } from "@krama/contracts-ts";
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

/** Per step: scene length and caption word timings (relative to the scene start), from `--scenes`. */
type SceneTimings = Record<string, { duration_ms: number; words?: WordTiming[] }>;

const FPS = 30;
const LEAD_IN_MS = 300; // the voice starts 300 ms into the scene (VideoScene plays the clip from there)
const HOLD_MS = 400; // silence after the voice before the next scene (same as the player, #267)

/**
 * Decision D4 when the backend sent no `--scenes` (it normally does, from `plan_scenes` in the Narrator port):
 * scene = max(recorded action, lead-in + clip + hold), rounded up to whole frames; words move by the lead-in.
 */
function scenesFromManifest(
  workflow: { steps?: { seq: number; start_ms?: number | null; end_ms?: number | null }[] },
  manifest: NarrationManifestData | undefined,
): SceneTimings {
  const scenes: SceneTimings = {};
  for (const clip of manifest?.clips ?? []) {
    const step = workflow.steps?.find((s) => s.seq === clip.step_seq);
    const action = step?.start_ms != null && step?.end_ms != null ? step.end_ms - step.start_ms : 0;
    const wantMs = Math.max(action, LEAD_IN_MS + clip.duration_ms + HOLD_MS, 1);
    const frames = Math.ceil((wantMs * FPS) / 1000);
    scenes[String(clip.step_seq)] = {
      duration_ms: Math.round((frames * 1000) / FPS),
      words: (clip.words ?? []).map((w) => ({
        word: w.word,
        start_ms: w.start_ms + LEAD_IN_MS,
        end_ms: w.end_ms + LEAD_IN_MS,
      })),
    };
  }
  return scenes;
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
  const language = args.language || "en";
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
    const scenes = args.scenes
      ? (JSON.parse(await fs.readFile(path.resolve(args.scenes), "utf-8")) as SceneTimings)
      : scenesFromManifest(workflow, manifest);
    const stepDurations: Record<number, number> = {};
    const wordTimings: Record<number, WordTiming[]> = {};
    for (const [seq, scene] of Object.entries(scenes)) {
      stepDurations[Number(seq)] = scene.duration_ms;
      if (scene.words?.length) wordTimings[Number(seq)] = scene.words;
    }
    spec = compileWorkflow(workflow, {
      fps: 30,
      stepDurations: Object.keys(stepDurations).length > 0 ? stepDurations : undefined,
      wordTimings: Object.keys(wordTimings).length > 0 ? wordTimings : undefined,
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
    language,
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
