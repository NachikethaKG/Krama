import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReplayViewer, SAMPLE_RRWEB_EVENTS, SAMPLE_REPLAY_STEPS } from '@/components/replay';

// Mock rrweb-player to avoid WebGL/Canvas/Svelte browser runtime dependencies in jsdom
vi.mock('rrweb-player', () => {
  return {
    default: class MockRRWebPlayer {
      target: HTMLElement;
      props: Record<string, unknown>;
      constructor({ target, props }: { target: HTMLElement; props: Record<string, unknown> }) {
        this.target = target;
        this.props = props;
        const div = document.createElement('div');
        div.className = 'rr-player-mock';
        target.appendChild(div);
      }
      goto = vi.fn();
      pause = vi.fn();
      play = vi.fn();
      $destroy = vi.fn();
    },
  };
});

describe('ReplayViewer component', () => {
  it('renders friendly empty state when events array is empty', () => {
    render(<ReplayViewer events={[]} />);

    expect(screen.getByTestId('replay-empty-state')).toBeInTheDocument();
    expect(
      screen.getByText('No recorded session events available for replay.')
    ).toBeInTheDocument();
  });

  it('renders player mount, SVG overlay, and timeline navigation when events and steps are provided', () => {
    render(
      <ReplayViewer
        events={SAMPLE_RRWEB_EVENTS}
        steps={SAMPLE_REPLAY_STEPS}
        currentStepIndex={0}
      />
    );

    expect(screen.getByTestId('replay-viewer')).toBeInTheDocument();
    expect(screen.getByTestId('player-mount')).toBeInTheDocument();
    expect(screen.getByTestId('svg-highlight-overlay')).toBeInTheDocument();
    expect(screen.getByTestId('step-navigation-bar')).toBeInTheDocument();
    expect(screen.getByText('Step 1 of 3')).toBeInTheDocument();
  });

  it('navigates through steps using next/prev buttons and fires onStepChange callback', () => {
    const onStepChange = vi.fn();

    render(
      <ReplayViewer
        events={SAMPLE_RRWEB_EVENTS}
        steps={SAMPLE_REPLAY_STEPS}
        currentStepIndex={0}
        onStepChange={onStepChange}
      />
    );

    const prevBtn = screen.getByTestId('prev-step-btn');
    const nextBtn = screen.getByTestId('next-step-btn');

    // On step 1, Prev is disabled
    expect(prevBtn).toBeDisabled();
    expect(nextBtn).not.toBeDisabled();

    // Click Next -> step 2
    fireEvent.click(nextBtn);
    expect(onStepChange).toHaveBeenCalledWith(1);
  });

  it('jumps to step when clicking step pill indicators', () => {
    const onStepChange = vi.fn();

    render(
      <ReplayViewer
        events={SAMPLE_RRWEB_EVENTS}
        steps={SAMPLE_REPLAY_STEPS}
        currentStepIndex={0}
        onStepChange={onStepChange}
      />
    );

    const pill3 = screen.getByTestId('step-pill-2');
    fireEvent.click(pill3);
    expect(onStepChange).toHaveBeenCalledWith(2);
  });

  it('disables next button when on the final step', () => {
    render(
      <ReplayViewer
        events={SAMPLE_RRWEB_EVENTS}
        steps={SAMPLE_REPLAY_STEPS}
        currentStepIndex={2}
      />
    );

    expect(screen.getByText('Step 3 of 3')).toBeInTheDocument();
    const nextBtn = screen.getByTestId('next-step-btn');
    expect(nextBtn).toBeDisabled();
  });

  it('gracefully handles missing steps array without rendering navigation bar', () => {
    render(<ReplayViewer events={SAMPLE_RRWEB_EVENTS} steps={[]} />);

    expect(screen.getByTestId('replay-viewer')).toBeInTheDocument();
    expect(screen.queryByTestId('step-navigation-bar')).not.toBeInTheDocument();
  });

  it('allows disabling controls or overlay via props', () => {
    const { rerender } = render(
      <ReplayViewer
        events={SAMPLE_RRWEB_EVENTS}
        steps={SAMPLE_REPLAY_STEPS}
        showControls={false}
      />
    );

    expect(screen.queryByTestId('step-navigation-bar')).not.toBeInTheDocument();
    expect(screen.getByTestId('svg-highlight-overlay')).toBeInTheDocument();

    rerender(
      <ReplayViewer
        events={SAMPLE_RRWEB_EVENTS}
        steps={SAMPLE_REPLAY_STEPS}
        showOverlay={false}
      />
    );

    expect(screen.queryByTestId('svg-highlight-overlay')).not.toBeInTheDocument();
  });
});
