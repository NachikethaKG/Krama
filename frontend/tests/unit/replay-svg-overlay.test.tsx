import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SvgHighlightOverlay } from '@/components/replay';
import type { TransformedRect } from '@/components/replay';

describe('SvgHighlightOverlay component', () => {
  const sampleRect: TransformedRect = {
    x: 100,
    y: 150,
    width: 250,
    height: 60,
    scaleX: 1,
    scaleY: 1,
    visible: true,
  };

  it('renders SVG container element with accessible role', () => {
    render(
      <SvgHighlightOverlay
        containerWidth={800}
        containerHeight={600}
      />
    );

    const overlay = screen.getByTestId('svg-highlight-overlay');
    expect(overlay).toBeInTheDocument();
    expect(overlay).toHaveAttribute('role', 'presentation');
    expect(overlay).toHaveAttribute('viewBox', '0 0 800 600');
  });

  it('renders highlight bounding box and corner tick marks when transformedRect is visible', () => {
    render(
      <SvgHighlightOverlay
        transformedRect={sampleRect}
        containerWidth={800}
        containerHeight={600}
      />
    );

    const highlight = screen.getByTestId('highlight-rect');
    expect(highlight).toBeInTheDocument();
    expect(highlight).toHaveAttribute('x', '100');
    expect(highlight).toHaveAttribute('y', '150');
    expect(highlight).toHaveAttribute('width', '250');
    expect(highlight).toHaveAttribute('height', '60');
    expect(screen.getByTestId('bounding-box-group')).toBeInTheDocument();
  });

  it('renders step badge and label above or below the bounding box', () => {
    render(
      <SvgHighlightOverlay
        transformedRect={sampleRect}
        badgeText="Step 2"
        containerWidth={800}
        containerHeight={600}
      />
    );

    const badge = screen.getByTestId('step-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent('Step 2');
  });

  it('renders cursor indicator when transformedCursor coordinates are provided', () => {
    render(
      <SvgHighlightOverlay
        transformedCursor={{ x: 120, y: 175 }}
        containerWidth={800}
        containerHeight={600}
      />
    );

    const cursor = screen.getByTestId('cursor-indicator');
    expect(cursor).toBeInTheDocument();
    expect(cursor).toHaveAttribute('transform', 'translate(120, 175)');
  });

  it('gracefully renders empty overlay without crashing when transformedRect is missing or not visible', () => {
    const { rerender } = render(
      <SvgHighlightOverlay
        transformedRect={null}
        containerWidth={800}
        containerHeight={600}
      />
    );

    expect(screen.getByTestId('svg-highlight-overlay')).toBeInTheDocument();
    expect(screen.queryByTestId('highlight-rect')).not.toBeInTheDocument();
    expect(screen.queryByTestId('cursor-indicator')).not.toBeInTheDocument();

    rerender(
      <SvgHighlightOverlay
        transformedRect={{ ...sampleRect, visible: false }}
        containerWidth={800}
        containerHeight={600}
      />
    );

    expect(screen.queryByTestId('highlight-rect')).not.toBeInTheDocument();
  });

  it('supports different step statuses (active, completed, failed, pending)', () => {
    const { rerender } = render(
      <SvgHighlightOverlay
        transformedRect={sampleRect}
        status="completed"
        badgeText="Completed"
        containerWidth={800}
        containerHeight={600}
      />
    );

    const rect = screen.getByTestId('highlight-rect');
    expect(rect).toHaveAttribute('stroke', '#10b981'); // emerald-500

    rerender(
      <SvgHighlightOverlay
        transformedRect={sampleRect}
        status="failed"
        badgeText="Failed"
        containerWidth={800}
        containerHeight={600}
      />
    );

    expect(screen.getByTestId('highlight-rect')).toHaveAttribute('stroke', '#ef4444'); // red-500
  });
});
