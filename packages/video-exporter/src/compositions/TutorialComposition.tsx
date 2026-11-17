import React from "react";
import { Sequence, useVideoConfig } from "remotion";
import type { VideoExportProps } from "../types.js";
import { IntroCard } from "./IntroCard.js";
import { OutroCard } from "./OutroCard.js";
import { VideoScene } from "./VideoScene.js";

/**
 * Calculates the exact total duration in frames for the composition.
 */
export function calculateTotalFrames(
  spec: VideoExportProps["spec"],
  fps = 30,
  introDurationFrames = 60,
  outroDurationFrames = 60,
): number {
  const sceneFrames = spec.scenes.reduce((sum, scene) => {
    return sum + Math.max(1, Math.round((scene.duration_ms / 1000) * fps));
  }, 0);

  return introDurationFrames + sceneFrames + outroDurationFrames;
}

export const TutorialComposition: React.FC<VideoExportProps> = ({
  spec,
  preset,
  screenshots = {},
  audioUrls = {},
  site = "git.local",
  verifiedDate = "2026-11-17",
  introDurationFrames = 60,
  outroDurationFrames = 60,
}) => {
  const { fps } = useVideoConfig();

  let currentFrameOffset = 0;

  return (
    <div
      data-testid="tutorial-composition"
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#07060f",
        position: "relative",
      }}
    >
      {/* 1. Intro Card (2 seconds = 60 frames) */}
      <Sequence from={currentFrameOffset} durationInFrames={introDurationFrames}>
        <IntroCard title={spec.title} site={site} preset={preset} />
      </Sequence>
      {(() => {
        currentFrameOffset += introDurationFrames;
        return null;
      })()}

      {/* 2. Scenes from TutorialSpec */}
      {spec.scenes.map((scene, index) => {
        const stepSeq = scene.step_seq ?? index + 1;
        const sceneDurationFrames = Math.max(1, Math.round((scene.duration_ms / 1000) * fps));
        const sceneStart = currentFrameOffset;
        currentFrameOffset += sceneDurationFrames;

        const screenshotUrl = screenshots?.[stepSeq];
        const audioUrl = audioUrls?.[stepSeq];

        return (
          <Sequence
            key={`scene-${scene.id || stepSeq}-${index}`}
            from={sceneStart}
            durationInFrames={sceneDurationFrames}
          >
            <VideoScene
              scene={scene}
              preset={preset}
              viewport={spec.viewport}
              screenshotUrl={screenshotUrl}
              audioUrl={audioUrl}
            />
          </Sequence>
        );
      })}

      {/* 3. Outro Card (2 seconds = 60 frames) */}
      <Sequence from={currentFrameOffset} durationInFrames={outroDurationFrames}>
        <OutroCard site={site} verifiedDate={verifiedDate} preset={preset} />
      </Sequence>
    </div>
  );
};
