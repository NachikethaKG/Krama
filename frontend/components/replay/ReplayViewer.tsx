'use client';

import React, { useSyncExternalStore, useRef } from 'react';
import type { ReplayViewerProps } from './types';

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

/**
 * ReplayViewer: Component skeleton for rrweb replay with SVG overlay support.
 */
export function ReplayViewer(props: ReplayViewerProps) {
  const {
    events,
    steps = [],
    currentStepIndex = 0,
    width = '100%',
    height = 540,
    className = '',
  } = props;
  const containerRef = useRef<HTMLDivElement>(null);
  const playerMountRef = useRef<HTMLDivElement>(null);
  const isClient = useIsClient();

  const currentStep = steps[currentStepIndex] ?? null;

  if (!isClient) {
    return (
      <div
        className={`flex items-center justify-center bg-slate-900 text-slate-400 rounded-lg ${className}`}
        style={{ width, height }}
      >
        <span className="text-sm font-medium">Initializing replay environment...</span>
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <div
        className={`flex flex-col items-center justify-center bg-slate-900 border border-slate-800 text-slate-400 rounded-lg p-6 ${className}`}
        style={{ width, height }}
      >
        <p className="text-sm font-medium">No recorded session events available for replay.</p>
        <p className="text-xs text-slate-500 mt-1">Provide a valid rrweb event stream to inspect execution.</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={`relative overflow-hidden bg-slate-950 rounded-lg border border-slate-800 shadow-xl ${className}`}
      style={{ width, height }}
      data-testid="replay-viewer"
    >
      <div ref={playerMountRef} className="w-full h-full" data-testid="player-mount" />
      {currentStep && (
        <div className="absolute bottom-2 left-2 text-xs text-slate-400 bg-slate-900/80 px-2 py-1 rounded">
          Step: {currentStep.instruction ?? currentStepIndex + 1}
        </div>
      )}
    </div>
  );
}

export default ReplayViewer;
