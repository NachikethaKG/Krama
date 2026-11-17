import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { VideoPreset } from "../types.js";

export interface IntroCardProps {
  title: string;
  site?: string;
  preset: VideoPreset;
}

export const IntroCard: React.FC<IntroCardProps> = ({ title, site = "git.local", preset }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Opacity fade in (frames 0 to 15), fade out (last 10 frames)
  const fadeIn = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [fps * 2 - 10, fps * 2], [1, 0], { extrapolateLeft: "clamp" });
  const opacity = fadeIn * fadeOut;

  // Scale entrance
  const scale = interpolate(frame, [0, 20], [0.94, 1.0], { extrapolateRight: "clamp" });

  const isPortrait = preset === "portrait";

  return (
    <div
      data-testid="intro-card"
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#07060f",
        backgroundImage: "radial-gradient(ellipse at 50% 40%, #1e1b4b 0%, #07060f 70%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        color: "#ffffff",
        fontFamily: "system-ui, -apple-system, sans-serif",
        padding: isPortrait ? "60px 40px" : "60px 120px",
        textAlign: "center",
        opacity,
        transform: `scale(${scale})`,
        position: "relative",
        boxSizing: "border-box",
      }}
    >
      {/* Verified Badge */}
      <div
        data-testid="intro-verified-badge"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: isPortrait ? "8px 18px" : "10px 24px",
          borderRadius: 999,
          border: "1px solid rgba(16, 185, 129, 0.4)",
          backgroundColor: "rgba(16, 185, 129, 0.15)",
          color: "#34d399",
          fontSize: isPortrait ? 18 : 20,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          marginBottom: isPortrait ? 32 : 36,
          boxShadow: "0 0 24px rgba(16, 185, 129, 0.25)",
        }}
      >
        <span>✓</span>
        <span>Verified Tutorial</span>
      </div>

      {/* Main Title */}
      <h1
        data-testid="intro-title"
        style={{
          fontSize: isPortrait ? 52 : 64,
          fontWeight: 800,
          lineHeight: 1.18,
          margin: 0,
          maxWidth: isPortrait ? 900 : 1400,
          background: "linear-gradient(180deg, #ffffff 30%, #94a3b8 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        {title}
      </h1>

      {/* Site URL Subtitle */}
      <div
        data-testid="intro-site"
        style={{
          marginTop: isPortrait ? 36 : 28,
          fontSize: isPortrait ? 24 : 26,
          color: "#94a3b8",
          display: "flex",
          alignItems: "center",
          gap: 10,
          fontFamily: "monospace",
        }}
      >
        <span style={{ color: "#38bdf8" }}>🌐</span>
        <span>{site}</span>
      </div>

      {/* Footer Engine Brand */}
      <div
        style={{
          position: "absolute",
          bottom: isPortrait ? 80 : 40,
          fontSize: isPortrait ? 20 : 18,
          color: "rgba(255, 255, 255, 0.35)",
          fontWeight: 600,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
        }}
      >
        Powered by Krama
      </div>
    </div>
  );
};
