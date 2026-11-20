import React from "react";
import { TEXT_FONT } from "../i18n.js";
import type { Caption, WordTiming } from "@krama/contracts-ts";
import type { VideoPreset } from "../types.js";

export interface CaptionsOverlayProps {
  caption: Caption | null | undefined;
  currentTimeMs: number;
  preset: VideoPreset;
}

export const CaptionsOverlay: React.FC<CaptionsOverlayProps> = ({
  caption,
  currentTimeMs,
  preset,
}) => {
  const text = caption?.text?.trim();
  if (!text) {
    return null;
  }

  const isPortrait = preset === "portrait";
  const words = caption?.words;

  return (
    <div
      data-testid="video-caption-container"
      style={{
        position: "absolute",
        left: "50%",
        bottom: isPortrait ? 160 : 48,
        transform: "translateX(-50%)",
        zIndex: 50,
        maxWidth: isPortrait ? "90%" : "80%",
        backgroundColor: "rgba(7, 6, 15, 0.88)",
        border: "1.5px solid rgba(168, 85, 247, 0.4)",
        boxShadow: "0 0 35px -5px rgba(168, 85, 247, 0.3), 0 10px 25px -5px rgba(0, 0, 0, 0.6)",
        borderRadius: isPortrait ? 24 : 20,
        padding: isPortrait ? "18px 28px" : "16px 32px",
        textAlign: "center",
        color: "#ffffff",
        fontFamily: TEXT_FONT,
        fontSize: isPortrait ? 26 : 24,
        fontWeight: 600,
        lineHeight: 1.35,
        boxSizing: "border-box",
        backdropFilter: "blur(12px)",
        pointerEvents: "none",
      }}
    >
      {words && words.length > 0 ? (
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: "0.25em 0.35em" }}>
          {words.map((wordObj: WordTiming, index: number) => {
            const isActive = currentTimeMs >= wordObj.start_ms && currentTimeMs < wordObj.end_ms;
            const isSpoken = currentTimeMs >= wordObj.end_ms;

            return (
              <span
                key={`${wordObj.word}-${index}`}
                style={{
                  color: isActive ? "#38bdf8" : isSpoken ? "#ffffff" : "rgba(255, 255, 255, 0.45)",
                  fontWeight: isActive ? 800 : isSpoken ? 700 : 500,
                  textShadow: isActive ? "0 0 16px rgba(56, 189, 248, 0.85)" : "none",
                  textDecoration: isActive ? "underline" : "none",
                  textDecorationColor: "#a855f7",
                  textDecorationThickness: 3,
                  textUnderlineOffset: 4,
                  transition: "color 100ms ease",
                }}
              >
                {wordObj.word}
              </span>
            );
          })}
        </div>
      ) : (
        <span>{text}</span>
      )}
    </div>
  );
};
