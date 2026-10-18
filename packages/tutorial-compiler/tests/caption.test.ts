import { describe, expect, it } from "vitest";
import { generateHeuristicWordTimings } from "../src/caption.js";

describe("generateHeuristicWordTimings", () => {
  it("returns empty array for empty or whitespace text", () => {
    expect(generateHeuristicWordTimings("")).toEqual([]);
    expect(generateHeuristicWordTimings("   ")).toEqual([]);
  });

  it("generates sequential word timings matching heuristic pacing", () => {
    const text = "Open the menu.";
    const timings = generateHeuristicWordTimings(text);

    expect(timings).toHaveLength(3);

    expect(timings[0].word).toBe("Open");
    expect(timings[0].start_ms).toBe(100);
    // duration for "Open" (len 4): max(180, 180) = 180ms
    expect(timings[0].end_ms).toBe(280);

    // After "Open", inter-word gap is 40ms -> start_ms = 320
    expect(timings[1].word).toBe("the");
    expect(timings[1].start_ms).toBe(320);
    expect(timings[1].end_ms).toBe(500);

    // After "the", gap is 40ms -> start_ms = 540
    expect(timings[2].word).toBe("menu.");
    expect(timings[2].start_ms).toBe(540);
    // "menu." (len 5): 5 * 45 = 225ms
    expect(timings[2].end_ms).toBe(765);
  });

  it("handles punctuation pauses appropriately", () => {
    const commaText = "First, second.";
    const timings = generateHeuristicWordTimings(commaText);

    expect(timings).toHaveLength(2);
    // "First," ends with comma -> gap + 150ms pause
    // First: start 100, end 100 + 270 (6 * 45 = 270) = 370
    // Pause: 40 + 150 = 190 -> next start = 560
    expect(timings[0].word).toBe("First,");
    expect(timings[1].word).toBe("second.");
    expect(timings[1].start_ms).toBe(timings[0].end_ms + 40 + 150);
  });
});
