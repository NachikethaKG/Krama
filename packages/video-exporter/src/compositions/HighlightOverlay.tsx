import React from "react";
import type { Highlight, ScrollOffset } from "@krama/contracts-ts";

export interface HighlightOverlayProps {
  highlight: Highlight | null | undefined;
  scroll: ScrollOffset;
  actionType?: string;
  clickMs?: number | null;
  currentTimeMs: number;
}

export const HighlightOverlay: React.FC<HighlightOverlayProps> = ({
  highlight,
  scroll,
  actionType,
  clickMs,
  currentTimeMs,
}) => {
  const bbox = highlight?.bbox;
  if (!bbox || bbox.length !== 4) {
    return null;
  }

  // After a click or press, the result page may have loaded and the clicked element is gone
  const hidesAfterClick =
    (actionType === "click" || actionType === "press") &&
    clickMs !== null &&
    clickMs !== undefined &&
    currentTimeMs >= clickMs + 80;

  if (hidesAfterClick) {
    return null;
  }

  const padding = highlight.padding ?? 8;
  const color = highlight.color ?? "#4f46e5";

  const x = bbox[0] - (scroll.x ?? 0) - padding;
  const y = bbox[1] - (scroll.y ?? 0) - padding;
  const w = bbox[2] + padding * 2;
  const h = bbox[3] + padding * 2;

  return (
    <div
      data-testid="video-target-highlight"
      style={{
        position: "absolute",
        left: `${x}px`,
        top: `${y}px`,
        width: `${w}px`,
        height: `${h}px`,
        borderRadius: 8,
        border: `3px solid ${color}`,
        backgroundColor: `${color}18`,
        boxShadow: `0 0 0 4px ${color}30, 0 0 24px ${color}80`,
        pointerEvents: "none",
        zIndex: 30,
        boxSizing: "border-box",
      }}
    />
  );
};
