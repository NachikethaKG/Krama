'use client';

import React, { useSyncExternalStore, useRef, useEffect, useState, useMemo } from 'react';
import { useTranslations } from 'next-intl';
import type { ReplayViewerProps } from './types';
import { extractRecordedDimensions } from './coordinateTransform';
import { useCoordinateTransform } from './useCoordinateTransform';
import { SvgHighlightOverlay } from './SvgHighlightOverlay';

function subscribe() {
  return () => {};
}

function useIsClient(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false
  );
}

// Minimal interface for rrweb-player instance
interface PlayerInstance {
  goto?: (timeOffset: number, play?: boolean) => void;
  pause?: (timeOffset?: number) => void;
  play?: () => void;
  $destroy?: () => void;
  destroy?: () => void;
  getReplayer?: () => unknown;
}

/**
 * ReplayViewer: Interactive rrweb session player with a responsive SVG step highlight overlay.
 *
 * Features:
 * - Dynamic browser-only instantiation of `rrweb-player` with safe teardown.
 * - Responsive SVG overlay tracking step bounding boxes and cursor positions.
 * - Automatic extraction of recorded viewport dimensions from rrweb Meta events.
 * - Interactive step timeline navigation and highlight trigger buttons.
 */
export function ReplayViewer({
  events,
  steps = [],
  currentStepIndex = 0,
  onStepChange,
  width = '100%',
  height = 540,
  autoPlay = false,
  className = '',
  showControls = true,
  showOverlay = true,
}: ReplayViewerProps) {
  const t = useTranslations('runs');
  const containerRef = useRef<HTMLDivElement>(null);
  const playerMountRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<PlayerInstance | null>(null);

  const isClient = useIsClient();
  const [prevPropIndex, setPrevPropIndex] = useState(currentStepIndex);
  const [internalIndex, setInternalIndex] = useState(currentStepIndex);

  if (currentStepIndex !== prevPropIndex) {
    setPrevPropIndex(currentStepIndex);
    setInternalIndex(currentStepIndex);
  }

  const activeIndex = Math.max(
    0,
    Math.min(
      steps.length > 0 ? steps.length - 1 : 0,
      onStepChange !== undefined ? currentStepIndex : internalIndex
    )
  );
  const currentStep = steps[activeIndex] ?? null;

  // Extract recorded dimensions from events (type 4 meta event)
  const recordedDim = useMemo(() => extractRecordedDimensions(events), [events]);

  // Transform coordinates for current active step
  const { containerSize, transformedRect, transformedCursor } = useCoordinateTransform({
    containerRef,
    bbox: currentStep?.bbox,
    cursorPosition: currentStep?.cursorPosition,
    recordedWidth: recordedDim.width,
    recordedHeight: recordedDim.height,
  });

  // Initialize and mount rrweb-player
  useEffect(() => {
    let playerInstance: PlayerInstance | null = null;
    let isDisposed = false;

    const mountEl = playerMountRef.current;
    if (!mountEl || !events || events.length === 0) return;

    mountEl.innerHTML = '';

    const setupPlayer = async () => {
      try {
        const rrwebMod = await import('rrweb-player');
        if (isDisposed || !playerMountRef.current) return;

        // Account for default vs named export formats across module loaders
        const PlayerCtor =
          (rrwebMod as unknown as { default: { default?: unknown; Player?: unknown } }).default?.default ??
          (rrwebMod as unknown as { default: unknown }).default ??
          (rrwebMod as unknown as { Player: unknown }).Player;

        if (typeof PlayerCtor === 'function') {
          playerInstance = new (PlayerCtor as new (opts: unknown) => PlayerInstance)({
            target: playerMountRef.current,
            props: {
              events,
              autoPlay,
              width: typeof width === 'number' ? width : undefined,
              height: typeof height === 'number' ? height : undefined,
              showController: true,
              mouseTail: false, // hide default mouse tail so our cursor overlay takes precedence
            },
          });
          playerRef.current = playerInstance;

          // Seek to current active step offset if available
          const initStep = steps[activeIndex];
          if (initStep && typeof playerInstance.goto === 'function') {
            playerInstance.goto(initStep.timeOffset, false);
          }
        }
      } catch (err) {
        // Player load error handled gracefully (e.g. in non-DOM test environments)
        console.warn('rrweb-player initialization notice:', err);
      }
    };

    setupPlayer();

    return () => {
      isDisposed = true;
      if (playerInstance) {
        try {
          if (typeof playerInstance.$destroy === 'function') {
            playerInstance.$destroy();
          } else if (typeof playerInstance.destroy === 'function') {
            playerInstance.destroy();
          }
        } catch {
          // ignore cleanup errors
        }
        playerRef.current = null;
      }
      if (mountEl) {
        mountEl.innerHTML = '';
      }
    };
  }, [events, autoPlay, width, height, steps, activeIndex]);

  // Synchronize playback position on step change
  useEffect(() => {
    const player = playerRef.current;
    if (!player) return;
    const step = steps[activeIndex];
    if (!step) return;

    try {
      if (typeof player.goto === 'function') {
        player.goto(step.timeOffset, false);
      } else if (typeof player.pause === 'function') {
        player.pause(step.timeOffset);
      }
    } catch {
      // Seek error ignored
    }
  }, [activeIndex, steps]);

  const handleStepSelect = (newIndex: number) => {
    if (newIndex < 0 || newIndex >= steps.length) return;
    setInternalIndex(newIndex);
    onStepChange?.(newIndex);
  };

  if (!isClient) {
    return (
      <div
        className={`flex items-center justify-center bg-white/[0.04] text-ink-400 rounded-lg ${className}`}
        style={{ width, height }}
      >
        <span className="text-sm font-medium">{t('replay.initializing')}</span>
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <div
        className={`flex flex-col items-center justify-center bg-white/[0.04] border border-white/10 text-ink-400 rounded-lg p-6 ${className}`}
        style={{ width, height }}
        data-testid="replay-empty-state"
      >
        <p className="text-sm font-medium">{t('replay.emptyTitle')}</p>
        <p className="text-xs text-ink-400 mt-1">{t('replay.emptyBody')}</p>
      </div>
    );
  }

  const handleTimelineKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'ArrowRight' && activeIndex < steps.length - 1) {
      e.preventDefault();
      handleStepSelect(activeIndex + 1);
    } else if (e.key === 'ArrowLeft' && activeIndex > 0) {
      e.preventDefault();
      handleStepSelect(activeIndex - 1);
    }
  };

  return (
    <div
      ref={containerRef}
      className={`relative overflow-hidden bg-ink-900/70 rounded-lg border border-white/10 shadow-xl ${className}`}
      style={{ width, height }}
      data-testid="replay-viewer"
    >
      {/* rrweb-player Mount Container */}
      <div
        ref={playerMountRef}
        className="w-full h-full flex items-center justify-center"
        data-testid="player-mount"
      />

      {/* SVG Highlight & Cursor Overlay */}
      {showOverlay && (
        <SvgHighlightOverlay
          transformedRect={transformedRect}
          transformedCursor={transformedCursor}
          label={currentStep?.instruction}
          badgeText={currentStep ? t('replay.stepBadge', { seq: currentStep.seq ?? activeIndex + 1 }) : undefined}
          status={currentStep?.status ?? 'active'}
          containerWidth={containerSize.width}
          containerHeight={containerSize.height}
        />
      )}

      {/* Interactive Step Timeline Bar */}
      {showControls && steps.length > 0 && (
        <div
          className="absolute bottom-3 left-3 right-3 z-30 flex items-center justify-between bg-white/[0.04] backdrop-blur border border-white/10 rounded-md px-3 py-2 text-xs text-ink-300 focus:outline-hidden focus:ring-1 focus:ring-run/40"
          data-testid="step-navigation-bar"
          tabIndex={0}
          role="region"
          aria-label={t('replay.timelineAria')}
          onKeyDown={handleTimelineKeyDown}
        >
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => handleStepSelect(activeIndex - 1)}
              disabled={activeIndex === 0}
              className="px-2 py-1 rounded bg-white/10 hover:bg-learn/30 disabled:opacity-40 disabled:hover:bg-white/10 transition font-medium focus-visible:ring-2 focus-visible:ring-run/40 focus-visible:outline-hidden"
              data-testid="prev-step-btn"
            >
              ← {t('replay.prev')}
            </button>
            <span className="font-semibold text-white">
              {t('replay.stepOf', { current: activeIndex + 1, total: steps.length })}
            </span>
            <button
              type="button"
              onClick={() => handleStepSelect(activeIndex + 1)}
              disabled={activeIndex === steps.length - 1}
              className="px-2 py-1 rounded bg-white/10 hover:bg-learn/30 disabled:opacity-40 disabled:hover:bg-white/10 transition font-medium focus-visible:ring-2 focus-visible:ring-run/40 focus-visible:outline-hidden"
              data-testid="next-step-btn"
            >
              {t('replay.next')} →
            </button>
          </div>

          {currentStep && (
            <div className="hidden sm:block truncate max-w-[50%] text-ink-400 font-mono text-[11px]" data-testid="current-step-label">
              {currentStep.instruction ?? t('replay.stepBadge', { seq: activeIndex + 1 })}
            </div>
          )}

          {/* Step Pill Selectors */}
          <div className="flex items-center space-x-1.5" data-testid="step-pills">
            {steps.map((step, idx) => (
              <button
                key={step.id ?? idx}
                type="button"
                onClick={() => handleStepSelect(idx)}
                className={`w-3 h-3 rounded-full transition-all ${
                  idx === activeIndex
                    ? 'bg-blue-500 ring-2 ring-blue-400/50 scale-110'
                    : 'bg-white/20 hover:bg-learn/60'
                }`}
                title={t('replay.jumpTitle', { seq: idx + 1, instruction: step.instruction ?? '' })}
                data-testid={`step-pill-${idx}`}
                aria-label={t('replay.jumpAria', { seq: idx + 1 })}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ReplayViewer;
