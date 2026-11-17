import React from "react";
import type { Cursor, ScrollOffset } from "@krama/contracts-ts";

export interface RippleOverlayProps {
  cursor: Cursor | null | undefined;
  currentTimeMs: number;
  scroll: ScrollOffset;
}

export const RippleOverlay: React.FC<RippleOverlayProps> = ({ cursor, currentTimeMs, scroll }) => {
  const clickMs = cursor?.click_ms;
  if (
    clickMs === null ||
    clickMs === undefined ||
    !cursor?.ripple ||
    !cursor.path ||
    cursor.path.length !== 4
  ) {
    return null;
  }

  const rippleDuration = 600;
  if (currentTimeMs < clickMs || currentTimeMs >= clickMs + rippleDuration) {
    return null;
  }

  const t = (currentTimeMs - clickMs) / rippleDuration;
  const maxRadius = cursor.ripple.radius ?? 28;
  const radius = Math.max(4, maxRadius * Math.sin((t * Math.PI) / 2));
  const opacity = Math.max(0, 1 - t);

  const centerTarget = cursor.path[3];
  const cx = centerTarget.x - (scroll.x ?? 0);
  const cy = centerTarget.y - (scroll.y ?? 0);

  const rippleColor = cursor.ripple.color || "rgba(255, 122, 26, 0.85)";
  const rippleBg = rippleColor.includes("rgba")
    ? rippleColor
    : "rgba(255, 122, 26, 0.25)";

  return (
    <div
      data-testid="video-click-ripple"
      style={{
        position: "absolute",
        left: `${cx - radius}px`,
        top: `${cy - radius}px`,
        width: `${radius * 2}px`,
        height: `${radius * 2}px`,
        borderRadius: "50%",
        border: `2.5px solid ${rippleColor}`,
        backgroundColor: rippleBg,
        opacity,
        pointerEvents: "none",
        zIndex: 35,
        boxShadow: `0 0 16px ${rippleColor}`,
      }}
    />
  );
};
