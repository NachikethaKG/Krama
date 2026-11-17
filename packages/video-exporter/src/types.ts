import type { TutorialSpec, WordTiming, Scene } from "@krama/contracts-ts";

export type VideoPreset = "landscape" | "portrait";

export interface NarrationClipData {
  step_seq: number;
  audio_key?: string;
  duration_ms: number;
  words?: WordTiming[];
}

export interface NarrationManifestData {
  voice: string;
  sample_rate: number;
  clips: NarrationClipData[];
}

export interface VideoExportProps {
  [key: string]: unknown;
  spec: TutorialSpec;
  preset: VideoPreset;
  manifest?: NarrationManifestData | null;
  /** Audio URL or local file path per step_seq */
  audioUrls?: Record<number, string>;
  /** Screenshot image URL, data URI, or local file path per step_seq */
  screenshots?: Record<number, string>;
  /** The website or host domain the workflow was run on (e.g. "git.local", "github.com") */
  site?: string;
  /** Date string of verification run (e.g. "2026-11-17") */
  verifiedDate?: string;
  /** Frames per second (default: 30) */
  fps?: number;
  /** Duration of intro card in frames (default: 60 = 2 seconds at 30fps) */
  introDurationFrames?: number;
  /** Duration of outro card in frames (default: 60 = 2 seconds at 30fps) */
  outroDurationFrames?: number;
}

export interface VideoChapter {
  title: string;
  startMs: number;
  endMs: number;
}

export interface RenderVideoOptions extends VideoExportProps {
  outputPath: string;
  concurrency?: number;
  crf?: number;
  onProgress?: (percent: number) => void;
  metadataPath?: string;
  vttPath?: string;
}

export interface RenderVideoResult {
  outputPath: string;
  durationMs: number;
  totalFrames: number;
  chapters: VideoChapter[];
  vttPath?: string;
  metadataPath?: string;
}

export { type TutorialSpec, type WordTiming, type Scene };
