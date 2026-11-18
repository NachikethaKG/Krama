import type { VideoChapter } from "../types.js";

/**
 * Adds chapter markers to an MP4 as a Nero chapter box (`moov/udta/chpl`), the format ffmpeg, VLC and mpv read.
 *
 * Remotion's bundled ffmpeg can't read FFMETADATA files, so chapters are written into the file directly: the
 * `moov` box grows by the size of the new box, and every chunk offset (`stco` / `co64`) that points past it is
 * moved by the same amount. Media data is never touched, and `moov` stays where it was (faststart stays).
 */
export function addMp4Chapters(mp4: Uint8Array, chapters: VideoChapter[]): Uint8Array {
  const data = Buffer.from(mp4);
  const top = readBoxes(data, 0, data.length);
  const moov = top.find((b) => b.type === "moov");
  if (!moov) throw new Error("not an MP4: no moov box");

  const chpl = chplBox(chapters);
  const moovBody = data.subarray(moov.start + moov.header, moov.end);
  const children = readBoxes(moovBody, 0, moovBody.length);
  const udta = children.find((b) => b.type === "udta");

  // New moov body: every child as is, the udta with any old chpl replaced by the new one.
  const parts: Buffer[] = [];
  for (const child of children) {
    const bytes = moovBody.subarray(child.start, child.end);
    if (child !== udta) {
      parts.push(Buffer.from(bytes));
      continue;
    }
    const inner = readBoxes(bytes, child.header, bytes.length)
      .filter((b) => b.type !== "chpl")
      .map((b) => bytes.subarray(b.start, b.end));
    parts.push(box("udta", Buffer.concat([...inner, chpl])));
  }
  if (!udta) parts.push(box("udta", chpl));
  const newMoov = box("moov", Buffer.concat(parts));

  const delta = newMoov.length - (moov.end - moov.start);
  if (delta !== 0) shiftChunkOffsets(newMoov, moov.end, delta);

  return Buffer.concat([data.subarray(0, moov.start), newMoov, data.subarray(moov.end)]);
}

interface Box {
  type: string;
  start: number;
  end: number;
  header: number;
}

const CONTAINERS = new Set(["moov", "trak", "mdia", "minf", "stbl", "edts", "dinf"]);

function readBoxes(buf: Buffer, from: number, to: number): Box[] {
  const out: Box[] = [];
  let i = from;
  while (i + 8 <= to) {
    let size = buf.readUInt32BE(i);
    const type = buf.toString("latin1", i + 4, i + 8);
    let header = 8;
    if (size === 1) {
      size = Number(buf.readBigUInt64BE(i + 8));
      header = 16;
    } else if (size === 0) {
      size = to - i;
    }
    if (size < header || i + size > to) throw new Error(`broken MP4 box ${type} at ${i}`);
    out.push({ type, start: i, end: i + size, header });
    i += size;
  }
  return out;
}

function box(type: string, body: Buffer): Buffer {
  const head = Buffer.alloc(8);
  head.writeUInt32BE(8 + body.length, 0);
  head.write(type, 4, "latin1");
  return Buffer.concat([head, body]);
}

/** Nero chapters, version 1: start times in 100 ns units, titles up to 255 UTF-8 bytes, at most 255 entries. */
function chplBox(chapters: VideoChapter[]): Buffer {
  const list = chapters.slice(0, 255);
  const parts: Buffer[] = [Buffer.from([1, 0, 0, 0, 0, 0, 0, 0, list.length])];
  for (const chapter of list) {
    let title = Buffer.from(chapter.title, "utf-8");
    if (title.length > 255) title = Buffer.from(title.subarray(0, 255).toString("utf-8").replace(/�$/, ""));
    const entry = Buffer.alloc(9);
    entry.writeBigUInt64BE(BigInt(Math.max(0, Math.round(chapter.startMs))) * 10_000n, 0);
    entry.writeUInt8(title.length, 8);
    parts.push(entry, title);
  }
  return box("chpl", Buffer.concat(parts));
}

/** Moves every chunk offset at or past `boundary` (the old end of moov) by `delta`. */
function shiftChunkOffsets(moov: Buffer, boundary: number, delta: number): void {
  const walk = (from: number, to: number) => {
    for (const b of readBoxes(moov, from, to)) {
      if (CONTAINERS.has(b.type)) {
        walk(b.start + b.header, b.end);
      } else if (b.type === "stco" || b.type === "co64") {
        const wide = b.type === "co64";
        const count = moov.readUInt32BE(b.start + b.header + 4);
        let p = b.start + b.header + 8;
        for (let n = 0; n < count; n++, p += wide ? 8 : 4) {
          if (wide) {
            const v = moov.readBigUInt64BE(p);
            if (v >= BigInt(boundary)) moov.writeBigUInt64BE(v + BigInt(delta), p);
          } else {
            const v = moov.readUInt32BE(p);
            if (v >= boundary) moov.writeUInt32BE(v + delta, p);
          }
        }
      }
    }
  };
  walk(8, moov.length);
}
