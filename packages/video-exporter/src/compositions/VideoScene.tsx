import React from "react";
import { Audio, Img, useCurrentFrame, useVideoConfig } from "remotion";
import type { Scene, WorkflowViewport } from "@krama/contracts-ts";
import type { VideoPreset } from "../types.js";
import { computeLandscapeFraming } from "../framing/landscape.js";
import { computePortraitFraming } from "../framing/portrait.js";
import { CursorOverlay } from "./CursorOverlay.js";
import { HighlightOverlay } from "./HighlightOverlay.js";
import { RippleOverlay } from "./RippleOverlay.js";
import { CaptionsOverlay } from "./CaptionsOverlay.js";

export interface VideoSceneProps {
  scene: Scene;
  preset: VideoPreset;
  viewport?: WorkflowViewport;
  screenshotUrl?: string;
  audioUrl?: string;
}

export const VideoScene: React.FC<VideoSceneProps> = ({
  scene,
  preset,
  viewport = { width: 1280, height: 800 },
  screenshotUrl,
  audioUrl,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentTimeMs = (frame / fps) * 1000;
  const isPortrait = preset === "portrait";

  const canvasWidth = isPortrait ? 1080 : 1920;
  const canvasHeight = isPortrait ? 1920 : 1080;

  const framing = isPortrait
    ? computePortraitFraming(scene, viewport, { width: canvasWidth, height: canvasHeight })
    : computeLandscapeFraming(scene, viewport, { width: canvasWidth, height: canvasHeight });

  const scroll = scene.scroll ?? { x: 0, y: 0 };

  // Lead-in for audio (300ms from decision D4)
  const audioLeadInFrames = Math.round((300 / 1000) * fps);

  return (
    <div
      data-testid="video-scene"
      style={{
        width: canvasWidth,
        height: canvasHeight,
        backgroundColor: "#07060f",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* Transformed Stage Container */}
      <div
        data-testid="scene-stage-canvas"
        style={{
          width: `${viewport.width}px`,
          height: `${viewport.height}px`,
          position: "absolute",
          top: 0,
          left: 0,
          transformOrigin: "top left",
          transform: `translate(${framing.panX}px, ${framing.panY}px) scale(${framing.scale})`,
        }}
      >
        {/* Real Screenshot Backdrop or Clean Mock Canvas */}
        {screenshotUrl ? (
          <Img
            data-testid="scene-screenshot"
            src={screenshotUrl}
            style={{
              width: `${viewport.width}px`,
              height: `${viewport.height}px`,
              display: "block",
              backgroundColor: "#ffffff",
            }}
          />
        ) : (
          <div
            data-testid="scene-mock-backdrop"
            style={{
              width: `${viewport.width}px`,
              height: `${viewport.height}px`,
              backgroundColor: "#0f172a",
              color: "#ffffff",
              display: "flex",
              flexDirection: "column",
              fontFamily: "system-ui, sans-serif",
            }}
          >
            {/* Header Chrome */}
            <div
              style={{
                height: 44,
                backgroundColor: "#090d16",
                borderBottom: "1px solid rgba(255,255,255,0.1)",
                display: "flex",
                alignItems: "center",
                padding: "0 16px",
                gap: 12,
              }}
            >
              <div style={{ display: "flex", gap: 6 }}>
                <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#ef4444" }} />
                <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#f59e0b" }} />
                <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#10b981" }} />
              </div>
              <div
                style={{
                  height: 26,
                  flex: 1,
                  maxWidth: 420,
                  backgroundColor: "rgba(255,255,255,0.06)",
                  borderRadius: 999,
                  display: "flex",
                  alignItems: "center",
                  padding: "0 12px",
                  fontSize: 12,
                  color: "#94a3b8",
                  fontFamily: "monospace",
                }}
              >
                🔒 https://git.local
              </div>
            </div>
            {/* Body */}
            <div
              style={{
                flex: 1,
                padding: 32,
                display: "flex",
                flexDirection: "column",
                gap: 20,
              }}
            >
              <div
                style={{
                  height: 32,
                  width: 300,
                  backgroundColor: "rgba(255,255,255,0.1)",
                  borderRadius: 6,
                }}
              />
              <div
                style={{
                  height: 120,
                  width: "100%",
                  backgroundColor: "rgba(255,255,255,0.04)",
                  borderRadius: 8,
                }}
              />
            </div>
          </div>
        )}

        {/* Vector Overlays (matching web player exactly) */}
        <HighlightOverlay
          highlight={scene.highlight}
          scroll={scroll}
          actionType={scene.action?.type}
          clickMs={scene.cursor?.click_ms}
          currentTimeMs={currentTimeMs}
        />

        <RippleOverlay
          cursor={scene.cursor}
          currentTimeMs={currentTimeMs}
          scroll={scroll}
        />

        <CursorOverlay
          cursor={scene.cursor}
          currentTimeMs={currentTimeMs}
          scroll={scroll}
        />
      </div>

      {/* Burned-in Subtitle Captions */}
      <CaptionsOverlay
        caption={scene.caption}
        currentTimeMs={currentTimeMs}
        preset={preset}
      />

      {/* Spoken Narration Audio (starts at 300ms lead-in) */}
      {audioUrl && frame >= audioLeadInFrames && (
        <Audio src={audioUrl} />
      )}
    </div>
  );
};
