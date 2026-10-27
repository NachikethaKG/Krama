"use client";

import { RunStatusBanners, type RunStatusBannersProps } from "./RunStatusBanners";

export type RunActionPanelProps = RunStatusBannersProps;

/**
 * Action Card / Modals Component (`RunActionPanel`) per PRD §27.
 *
 * Renders actionable states:
 * - When status is `paused`:
 *   - Displays danger-zone confirmation or barrier notice with context.
 *   - Provides action buttons "Allow & Resume" and "Abort Run" (sending X-Krama: 1).
 * - When status is `completed`:
 *   - Shows success banner with CTA button "Open Interactive Tutorial".
 * - When status is `failed`:
 *   - Shows failure banner with Expected vs Observed mismatch details.
 */
export function RunActionPanel(props: RunActionPanelProps) {
  return (
    <div data-testid="run-action-panel">
      <RunStatusBanners {...props} />
    </div>
  );
}
