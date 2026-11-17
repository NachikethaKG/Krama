import React from "react";
import type { Cursor, Point, ScrollOffset } from "@krama/contracts-ts";
import { evaluateBezierPoint } from "@krama/tutorial-compiler";

export interface CursorOverlayProps {
  cursor: Cursor | null | undefined;
  currentTimeMs: number;
  scroll: ScrollOffset;
}

export const CursorOverlay: React.FC<CursorOverlayProps> = ({ cursor, currentTimeMs, scroll }) => {
  if (!cursor?.path || cursor.path.length !== 4) {
    return null;
  }

  const { path, start_ms, end_ms } = cursor;
  let targetPoint: Point;

  if (currentTimeMs <= start_ms) {
    targetPoint = path[0];
  } else if (currentTimeMs >= end_ms) {
    targetPoint = path[3];
  } else {
    const duration = Math.max(1, end_ms - start_ms);
    const t = Math.max(0, Math.min(1, (currentTimeMs - start_ms) / duration));
    targetPoint = evaluateBezierPoint(path as [Point, Point, Point, Point], t);
  }

  const x = targetPoint.x - (scroll.x ?? 0);
  const y = targetPoint.y - (scroll.y ?? 0);

  return (
    <div
      data-testid="video-cursor"
      style={{
        position: "absolute",
        left: `${x}px`,
        top: `${y}px`,
        transform: "translate(-2px, -2px)",
        pointerEvents: "none",
        zIndex: 40,
      }}
    >
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          filter: "drop-shadow(0 0 10px rgba(255, 79, 216, 0.85)) drop-shadow(0 2px 4px rgba(0,0,0,0.5))",
        }}
      >
        <path
          d="M4 3L11.5 21L14.5 13.5L22 10.5L4 3Z"
          fill="#ffffff"
          stroke="#07060f"
          strokeWidth="1.75"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
};
