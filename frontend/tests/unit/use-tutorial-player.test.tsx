import { StrictMode, type ReactNode } from "react";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Scene, TutorialSpec } from "@krama/tutorial-compiler";
import { useTutorialPlayer } from "@/components/player/useTutorialPlayer";

// #319: React may run a state updater twice (always in dev StrictMode). The player advanced scenes from inside
// one, so a long scene followed by a shorter one skipped that one, and the second-to-last ended the tutorial.
function specWith(durations: number[]): TutorialSpec {
  const scenes = durations.map((d, i) => ({ id: `s${i + 1}`, step_seq: i + 1, duration_ms: d }) as unknown as Scene);
  return { scenes, total_duration_ms: durations.reduce((a, b) => a + b, 0) } as unknown as TutorialSpec;
}

let frames = new Map<number, FrameRequestCallback>();
let nextId = 1;
let now = 0;

/** Runs animation frames 16 ms apart until `ms` have passed. */
function advance(ms: number) {
  const end = now + ms;
  while (now < end) {
    now += 16;
    const due = [...frames.values()];
    frames = new Map();
    act(() => due.forEach((cb) => cb(now)));
  }
}

const strict = ({ children }: { children: ReactNode }) => <StrictMode>{children}</StrictMode>;

describe("useTutorialPlayer scene progression (#319)", () => {
  beforeEach(() => {
    frames = new Map();
    now = 0;
    vi.spyOn(performance, "now").mockImplementation(() => now);
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
      frames.set(nextId, cb);
      return nextId++;
    });
    vi.stubGlobal("cancelAnimationFrame", (id: number) => frames.delete(id));
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("plays every scene in order when a long scene is followed by a short one", () => {
    const seen: number[] = [];
    const onComplete = vi.fn();
    const { result } = renderHook(
      () => useTutorialPlayer({ spec: specWith([6000, 1500, 3800, 1000]), onSceneChange: (i) => seen.push(i), onComplete }),
      { wrapper: strict },
    );

    act(() => result.current.play());
    advance(6100);
    expect(result.current.currentSceneIndex).toBe(1);
    advance(1500);
    expect(result.current.currentSceneIndex).toBe(2);
    advance(3800);
    expect(result.current.currentSceneIndex).toBe(3);
    expect(onComplete).not.toHaveBeenCalled();
    advance(1100);

    expect(seen).toEqual([1, 2, 3]);
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(result.current.isPlaying).toBe(false);
  });
});
