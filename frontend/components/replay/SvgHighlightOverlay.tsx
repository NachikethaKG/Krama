'use client';

import React from 'react';
import type { Point, TransformedRect } from './types';

export interface SvgHighlightOverlayProps {
  transformedRect?: TransformedRect | null;
  transformedCursor?: Point | null;
  label?: string;
  badgeText?: string;
  status?: 'pending' | 'active' | 'completed' | 'failed';
  containerWidth?: number;
  containerHeight?: number;
  className?: string;
}

const STATUS_COLORS: Record<
  'pending' | 'active' | 'completed' | 'failed',
  { stroke: string; fill: string; glow: string; text: string; badgeBg: string }
> = {
  active: {
    stroke: '#3b82f6', // blue-500
    fill: 'rgba(59, 130, 246, 0.15)',
    glow: 'rgba(59, 130, 246, 0.35)',
    text: '#ffffff',
    badgeBg: '#1d4ed8', // blue-700
  },
  completed: {
    stroke: '#10b981', // emerald-500
    fill: 'rgba(16, 185, 129, 0.15)',
    glow: 'rgba(16, 185, 129, 0.35)',
    text: '#ffffff',
    badgeBg: '#047857', // emerald-700
  },
  failed: {
    stroke: '#ef4444', // red-500
    fill: 'rgba(239, 68, 68, 0.15)',
    glow: 'rgba(239, 68, 68, 0.35)',
    text: '#ffffff',
    badgeBg: '#b91c1c', // red-700
  },
  pending: {
    stroke: '#f59e0b', // amber-500
    fill: 'rgba(245, 158, 11, 0.15)',
    glow: 'rgba(245, 158, 11, 0.35)',
    text: '#ffffff',
    badgeBg: '#b45309', // amber-700
  },
};

/**
 * SvgHighlightOverlay renders a pixel-aligned SVG overlay on top of the rrweb replay canvas.
 * It visualizes target step bounding boxes, step badges, and cursor indicators without intercepting pointer events.
 */
export function SvgHighlightOverlay({
  transformedRect,
  transformedCursor,
  label,
  badgeText,
  status = 'active',
  containerWidth,
  containerHeight,
  className = '',
}: SvgHighlightOverlayProps) {
  const colors = STATUS_COLORS[status] ?? STATUS_COLORS.active;
  const hasValidRect = Boolean(transformedRect && transformedRect.visible);
  const hasValidCursor = Boolean(
    transformedCursor &&
      typeof transformedCursor.x === 'number' &&
      typeof transformedCursor.y === 'number'
  );

  const displayBadge = badgeText || label;

  return (
    <svg
      className={`pointer-events-none absolute inset-0 z-20 w-full h-full overflow-visible ${className}`}
      width={containerWidth ? `${containerWidth}px` : '100%'}
      height={containerHeight ? `${containerHeight}px` : '100%'}
      viewBox={
        containerWidth && containerHeight && containerWidth > 0 && containerHeight > 0
          ? `0 0 ${containerWidth} ${containerHeight}`
          : undefined
      }
      aria-label="Replay Step Highlight Overlay"
      role="presentation"
      data-testid="svg-highlight-overlay"
    >
      <defs>
        {/* Soft shadow filter for the highlight bounding box */}
        <filter id="krama-highlight-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor={colors.glow} />
        </filter>
      </defs>

      {/* Target Step Bounding Box */}
      {hasValidRect && transformedRect && (
        <g data-testid="bounding-box-group" className="transition-all duration-200">
          {/* Subtle glow / outer halo */}
          <rect
            x={transformedRect.x - 2}
            y={transformedRect.y - 2}
            width={transformedRect.width + 4}
            height={transformedRect.height + 4}
            rx={6}
            fill="none"
            stroke={colors.glow}
            strokeWidth={3}
            opacity={0.8}
            filter="url(#krama-highlight-glow)"
          />

          {/* Core highlight rectangle */}
          <rect
            x={transformedRect.x}
            y={transformedRect.y}
            width={transformedRect.width}
            height={transformedRect.height}
            rx={4}
            fill={colors.fill}
            stroke={colors.stroke}
            strokeWidth={2}
            data-testid="highlight-rect"
          />

          {/* Corner accent tick marks for crisp technical visual */}
          <g stroke={colors.stroke} strokeWidth={2.5} strokeLinecap="round">
            {/* Top-left */}
            <path
              d={`M ${transformedRect.x} ${transformedRect.y + 8} L ${transformedRect.x} ${transformedRect.y} L ${transformedRect.x + 8} ${transformedRect.y}`}
            />
            {/* Top-right */}
            <path
              d={`M ${transformedRect.x + transformedRect.width - 8} ${transformedRect.y} L ${transformedRect.x + transformedRect.width} ${transformedRect.y} L ${transformedRect.x + transformedRect.width} ${transformedRect.y + 8}`}
            />
            {/* Bottom-left */}
            <path
              d={`M ${transformedRect.x} ${transformedRect.y + transformedRect.height - 8} L ${transformedRect.x} ${transformedRect.y + transformedRect.height} L ${transformedRect.x + 8} ${transformedRect.y + transformedRect.height}`}
            />
            {/* Bottom-right */}
            <path
              d={`M ${transformedRect.x + transformedRect.width - 8} ${transformedRect.y + transformedRect.height} L ${transformedRect.x + transformedRect.width} ${transformedRect.y + transformedRect.height} L ${transformedRect.x + transformedRect.width} ${transformedRect.y + transformedRect.height - 8}`}
            />
          </g>

          {/* Step Badge / Label */}
          {displayBadge && (
            <g
              data-testid="step-badge"
              transform={`translate(${transformedRect.x}, ${
                transformedRect.y >= 26
                  ? transformedRect.y - 24
                  : transformedRect.y + transformedRect.height + 6
              })`}
            >
              <rect
                x={0}
                y={0}
                width={Math.max(60, displayBadge.length * 7.5 + 16)}
                height={20}
                rx={4}
                fill={colors.badgeBg}
                opacity={0.95}
              />
              <text
                x={8}
                y={14}
                fill={colors.text}
                fontSize={11}
                fontWeight={600}
                fontFamily="ui-sans-serif, system-ui, sans-serif"
              >
                {displayBadge}
              </text>
            </g>
          )}
        </g>
      )}

      {/* Cursor Indicator */}
      {hasValidCursor && transformedCursor && (
        <g
          data-testid="cursor-indicator"
          transform={`translate(${transformedCursor.x}, ${transformedCursor.y})`}
          className="transition-transform duration-100"
        >
          {/* Radar ripple circle */}
          <circle r={12} fill="none" stroke="#f59e0b" strokeWidth={1.5} opacity={0.6}>
            <animate
              attributeName="r"
              from="6"
              to="16"
              dur="1.5s"
              repeatCount="indefinite"
            />
            <animate
              attributeName="opacity"
              from="0.8"
              to="0"
              dur="1.5s"
              repeatCount="indefinite"
            />
          </circle>
          {/* Inner cursor dot */}
          <circle r={4.5} fill="#f59e0b" stroke="#ffffff" strokeWidth={1.5} />
        </g>
      )}
    </svg>
  );
}

export default SvgHighlightOverlay;
