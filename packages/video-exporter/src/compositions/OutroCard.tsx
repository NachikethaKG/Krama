import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { TEXT_FONT, videoStrings } from "../i18n.js";
import type { VideoPreset } from "../types.js";

export interface OutroCardProps {
  site?: string;
  verifiedDate?: string;
  preset: VideoPreset;
  language?: string;
}

export const OutroCard: React.FC<OutroCardProps> = ({
  site = "git.local",
  verifiedDate = "2026-11-17",
  preset,
  language,
}) => {
  const words = videoStrings(language);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Opacity fade in
  const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const scale = interpolate(frame, [0, 20], [0.94, 1.0], { extrapolateRight: "clamp" });

  const isPortrait = preset === "portrait";

  return (
    <div
      data-testid="outro-card"
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#07060f",
        backgroundImage: "radial-gradient(ellipse at 50% 45%, #111827 0%, #07060f 75%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        color: "#ffffff",
        fontFamily: TEXT_FONT,
        padding: isPortrait ? "60px 40px" : "60px 120px",
        textAlign: "center",
        opacity,
        transform: `scale(${scale})`,
        position: "relative",
        boxSizing: "border-box",
      }}
    >
      {/* Success Icon */}
      <div
        data-testid="outro-check-icon"
        style={{
          width: isPortrait ? 96 : 88,
          height: isPortrait ? 96 : 88,
          borderRadius: "50%",
          backgroundColor: "rgba(16, 185, 129, 0.15)",
          border: "2px solid rgba(16, 185, 129, 0.6)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: isPortrait ? 48 : 42,
          color: "#34d399",
          marginBottom: isPortrait ? 36 : 28,
          boxShadow: "0 0 40px rgba(16, 185, 129, 0.35)",
        }}
      >
        ✓
      </div>

      {/* Verified Notice (Decision D9) */}
      <h2
        data-testid="outro-verified-notice"
        style={{
          fontSize: isPortrait ? 40 : 44,
          fontWeight: 800,
          margin: 0,
          color: "#ffffff",
        }}
      >
        {words.verifiedOn(site)}
      </h2>

      <p
        data-testid="outro-date"
        style={{
          marginTop: 14,
          fontSize: isPortrait ? 22 : 24,
          color: "#94a3b8",
          fontFamily: "monospace",
        }}
      >
        {verifiedDate}
      </p>

      {/* Brand Signoff */}
      <div
        data-testid="outro-brand"
        style={{
          marginTop: isPortrait ? 44 : 36,
          fontSize: isPortrait ? 26 : 28,
          fontWeight: 700,
          letterSpacing: "0.04em",
          color: "#a855f7",
          textShadow: "0 0 20px rgba(168, 85, 247, 0.4)",
        }}
      >
        {words.madeWith}
      </div>
      {words.voiceCredit ? (
        <p data-testid="outro-voice-credit" style={{ marginTop: 18, fontSize: 18, color: "#94a3b8" }}>
          {words.voiceCredit}
        </p>
      ) : null}
    </div>
  );
};
