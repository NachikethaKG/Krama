import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { addMp4Chapters } from "../src/metadata/mp4-chapters";

// A real 1 s H.264 + AAC MP4 with moov before mdat (contracts fixture for the mock export queue).
const TINY = fs.readFileSync(path.resolve(__dirname, "../../../contracts/fixtures/exports/tiny.mp4"));

interface Box {
  type: string;
  start: number;
  end: number;
}

function boxes(buf: Buffer, from: number, to: number): Box[] {
  const out: Box[] = [];
  for (let i = from; i + 8 <= to; ) {
    const size = buf.readUInt32BE(i);
    out.push({ type: buf.toString("latin1", i + 4, i + 8), start: i, end: i + size });
    i += size;
  }
  return out;
}

function find(buf: Buffer, pathTypes: string[]): Box[] {
  let level: Box[] = boxes(buf, 0, buf.length);
  for (const [n, type] of pathTypes.entries()) {
    const matches = level.filter((b) => b.type === type);
    if (n === pathTypes.length - 1) return matches;
    level = matches.flatMap((b) => boxes(buf, b.start + 8, b.end));
  }
  return [];
}

/** Every chunk offset of every track (stco). */
function chunkOffsets(buf: Buffer): number[] {
  return find(buf, ["moov", "trak", "mdia", "minf", "stbl", "stco"]).flatMap((b) => {
    const count = buf.readUInt32BE(b.start + 12);
    return Array.from({ length: count }, (_, k) => buf.readUInt32BE(b.start + 16 + 4 * k));
  });
}

function chapters(buf: Buffer): { startMs: number; title: string }[] {
  const [chpl] = find(buf, ["moov", "udta", "chpl"]);
  const count = buf.readUInt8(chpl.start + 16);
  const out = [];
  let p = chpl.start + 17;
  for (let k = 0; k < count; k++) {
    const start = buf.readBigUInt64BE(p);
    const len = buf.readUInt8(p + 8);
    out.push({ startMs: Number(start / 10_000n), title: buf.toString("utf-8", p + 9, p + 9 + len) });
    p += 9 + len;
  }
  return out;
}

const CHAPTERS = [
  { title: "Intro", startMs: 0, endMs: 2000 },
  { title: "Step 1: Go to the “Labels” page", startMs: 2000, endMs: 3700 },
  { title: "Done", startMs: 3700, endMs: 5700 },
];

describe("addMp4Chapters", () => {
  it("writes chapters that read back with their times and titles", () => {
    const out = Buffer.from(addMp4Chapters(TINY, CHAPTERS));
    expect(chapters(out)).toEqual(CHAPTERS.map(({ startMs, title }) => ({ startMs, title })));
  });

  it("keeps moov in front and every chunk offset on the same media bytes", () => {
    const out = Buffer.from(addMp4Chapters(TINY, CHAPTERS));
    const before = chunkOffsets(TINY);
    const after = chunkOffsets(out);
    const types = boxes(out, 0, out.length).map((b) => b.type);

    expect(types.indexOf("moov")).toBeLessThan(types.indexOf("mdat"));
    expect(after).toHaveLength(before.length);
    const delta = out.length - TINY.length;
    expect(delta).toBeGreaterThan(0);
    for (const [k, offset] of before.entries()) {
      expect(after[k]).toBe(offset + delta);
      expect(out.subarray(after[k], after[k] + 16)).toEqual(TINY.subarray(offset, offset + 16));
    }
  });

  it("replaces earlier chapters instead of adding a second set", () => {
    const once = Buffer.from(addMp4Chapters(TINY, CHAPTERS));
    const twice = Buffer.from(addMp4Chapters(once, CHAPTERS.slice(0, 1)));
    expect(find(twice, ["moov", "udta", "chpl"])).toHaveLength(1);
    expect(chapters(twice)).toEqual([{ startMs: 0, title: "Intro" }]);
  });

  it("refuses a file that isn't an MP4", () => {
    expect(() => addMp4Chapters(Buffer.from("not a video at all"), CHAPTERS)).toThrow();
  });
});
