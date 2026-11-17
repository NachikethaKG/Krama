import React from "react";
import { Composition } from "remotion";
import type { VideoExportProps } from "../types.js";
import { calculateTotalFrames, TutorialComposition } from "./TutorialComposition.js";

const DEFAULT_SPEC: VideoExportProps["spec"] = {
  version: "1.0",
  workflow_id: "default-workflow",
  title: "Krama Tutorial",
  viewport: { width: 1280, height: 800 },
  total_duration_ms: 3000,
  scenes: [
    {
      id: "scene-1",
      step_seq: 1,
      title: "Overview",
      start_ms: 0,
      duration_ms: 3000,
      action: { type: "navigate", value: "https://git.local" },
      recording: { start_ms: 0, end_ms: 3000 },
      caption: { text: "Welcome to the tutorial." },
    },
  ],
};

export const RemotionRoot: React.FC = () => {
  const fps = 30;
  const defaultDuration = calculateTotalFrames(DEFAULT_SPEC, fps);

  return (
    <>
      <Composition<any, any>
        id="TutorialLandscape"
        component={TutorialComposition}
        durationInFrames={defaultDuration}
        fps={fps}
        width={1920}
        height={1080}
        defaultProps={{
          spec: DEFAULT_SPEC,
          preset: "landscape",
        }}
        calculateMetadata={({ props }) => {
          const p = props as unknown as Partial<VideoExportProps>;
          const spec = p.spec ?? DEFAULT_SPEC;
          const intro = p.introDurationFrames ?? 60;
          const outro = p.outroDurationFrames ?? 60;
          return {
            durationInFrames: calculateTotalFrames(spec, fps, intro, outro),
            width: 1920,
            height: 1080,
            fps,
          };
        }}
      />
      <Composition<any, any>
        id="TutorialPortrait"
        component={TutorialComposition}
        durationInFrames={defaultDuration}
        fps={fps}
        width={1080}
        height={1920}
        defaultProps={{
          spec: DEFAULT_SPEC,
          preset: "portrait",
        }}
        calculateMetadata={({ props }) => {
          const p = props as unknown as Partial<VideoExportProps>;
          const spec = p.spec ?? DEFAULT_SPEC;
          const intro = p.introDurationFrames ?? 60;
          const outro = p.outroDurationFrames ?? 60;
          return {
            durationInFrames: calculateTotalFrames(spec, fps, intro, outro),
            width: 1080,
            height: 1920,
            fps,
          };
        }}
      />
    </>
  );
};
