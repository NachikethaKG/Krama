import { describe, expect, it } from "vitest";
import type { TutorialSpec } from "@krama/contracts-ts";
import { buildTutorialChapters, formatFFMetadata } from "../src/metadata/chapters.js";

const MOCK_SPEC: TutorialSpec = {
  version: "1.0",
  workflow_id: "wf-1",
  title: "Create Gitea Repo",
  viewport: { width: 1280, height: 800 },
  total_duration_ms: 7500,
  scenes: [
    {
      id: "s1",
      step_seq: 1,
      title: "Click New Repo",
      start_ms: 0,
      duration_ms: 3500,
      action: { type: "click" },
      recording: { start_ms: 0, end_ms: 3500 },
      caption: { text: "Click the New Repository button." },
    },
    {
      id: "s2",
      step_seq: 2,
      title: "Fill Repo Name",
      start_ms: 3500,
      duration_ms: 4000,
      action: { type: "fill", value: "my-repo" },
      recording: { start_ms: 3500, end_ms: 7500 },
      caption: { text: "Type the repository name." },
    },
  ],
};

describe("Chapters and FFMETADATA (Decision D12)", () => {
  it("builds chapters with Intro (2s), step chapters, and Done (2s)", () => {
    const chapters = buildTutorialChapters(MOCK_SPEC, 2000, 2000);

    expect(chapters).toHaveLength(4);

    // Intro
    expect(chapters[0]).toEqual({
      title: "Intro",
      startMs: 0,
      endMs: 2000,
    });

    // Step 1
    expect(chapters[1]).toEqual({
      title: "Step 1: Click New Repo",
      startMs: 2000,
      endMs: 5500,
    });

    // Step 2
    expect(chapters[2]).toEqual({
      title: "Step 2: Fill Repo Name",
      startMs: 5500,
      endMs: 9500,
    });

    // Done
    expect(chapters[3]).toEqual({
      title: "Done",
      startMs: 9500,
      endMs: 11500,
    });
  });

  it("formats chapters into valid FFMETADATA1 syntax with escaping", () => {
    const chapters = [
      { title: "Intro", startMs: 0, endMs: 2000 },
      { title: "Step 1: Type name=repo; fast #1", startMs: 2000, endMs: 5000 },
    ];

    const metadata = formatFFMetadata("Special Title: Test=1", chapters);

    expect(metadata).toContain(";FFMETADATA1");
    expect(metadata).toContain("title=Special Title\\: Test\\=1");
    expect(metadata).toContain("[CHAPTER]");
    expect(metadata).toContain("TIMEBASE=1/1000");
    expect(metadata).toContain("START=0");
    expect(metadata).toContain("END=2000");
    expect(metadata).toContain("title=Intro");
    expect(metadata).toContain("START=2000");
    expect(metadata).toContain("END=5000");
    expect(metadata).toContain("title=Step 1\\: Type name\\=repo\\; fast \\#1");
  });
});
