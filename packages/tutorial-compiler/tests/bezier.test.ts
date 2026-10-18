import { describe, expect, it } from "vitest";
import {
  bezierToSvgPath,
  evaluateBezierPoint,
  generateCursorTrajectory,
  round1,
} from "../src/bezier.js";
import type { Point } from "../src/types.js";

describe("generateCursorTrajectory", () => {
  it("calculates a natural upward-arcing cubic Bezier trajectory", () => {
    const start: Point = { x: 640, y: 400 };
    const end: Point = { x: 1174, y: 24 };

    const trajectory = generateCursorTrajectory(start, end);

    expect(trajectory).toHaveLength(4);
    const [p0, p1, p2, p3] = trajectory;

    // P0 matches start
    expect(p0).toEqual({ x: 640, y: 400 });
    // P3 matches end
    expect(p3).toEqual({ x: 1174, y: 24 });

    // X coordinates are partitioned by thirds:
    // dx = 534, dx / 3 = 178
    expect(p1.x).toBe(818);
    expect(p2.x).toBe(996);

    // Y coordinates arc upward (screen Y decreases by 40 at 1/3, and 20 at 2/3):
    // dy = -376, dy / 3 = -125.333
    // y1 = 400 - 125.333 - 40 = 234.667 -> 234.7
    // y2 = 400 - 250.667 - 20 = 129.333 -> 129.3
    expect(p1.y).toBe(234.7);
    expect(p2.y).toBe(129.3);
  });

  it("handles identical start and end points without NaN", () => {
    const point: Point = { x: 500, y: 300 };
    const trajectory = generateCursorTrajectory(point, point);

    expect(trajectory).toEqual([point, point, point, point]);
  });

  it("collapses all control points to the target under reduced motion", () => {
    const start: Point = { x: 100, y: 100 };
    const end: Point = { x: 800, y: 600 };

    const trajectory = generateCursorTrajectory(start, end, { reducedMotion: true });

    expect(trajectory).toEqual([end, end, end, end]);
  });

  it("supports custom curve offsets", () => {
    const start: Point = { x: 0, y: 0 };
    const end: Point = { x: 300, y: 300 };

    const trajectory = generateCursorTrajectory(start, end, {
      curveOffsetY1: 50,
      curveOffsetY2: 25,
    });

    const [, p1, p2] = trajectory;
    expect(p1).toEqual({ x: 100, y: 50 }); // 0 + 100 - 50 = 50
    expect(p2).toEqual({ x: 200, y: 175 }); // 0 + 200 - 25 = 175
  });
});

describe("evaluateBezierPoint", () => {
  const path: [Point, Point, Point, Point] = [
    { x: 0, y: 0 },
    { x: 100, y: 200 },
    { x: 200, y: 200 },
    { x: 300, y: 0 },
  ];

  it("returns P0 at t = 0", () => {
    expect(evaluateBezierPoint(path, 0)).toEqual({ x: 0, y: 0 });
  });

  it("returns P3 at t = 1", () => {
    expect(evaluateBezierPoint(path, 1)).toEqual({ x: 300, y: 0 });
  });

  it("clamps t below 0 and above 1", () => {
    expect(evaluateBezierPoint(path, -0.5)).toEqual({ x: 0, y: 0 });
    expect(evaluateBezierPoint(path, 1.5)).toEqual({ x: 300, y: 0 });
  });

  it("evaluates intermediate point at t = 0.5 symmetrically", () => {
    const mid = evaluateBezierPoint(path, 0.5);
    expect(mid.x).toBe(150);
    expect(mid.y).toBe(150);
  });
});

describe("bezierToSvgPath", () => {
  it("formats into an SVG cubic bezier path string", () => {
    const path: [Point, Point, Point, Point] = [
      { x: 640, y: 400 },
      { x: 818, y: 234.7 },
      { x: 996, y: 129.3 },
      { x: 1174, y: 24 },
    ];

    expect(bezierToSvgPath(path)).toBe(
      "M 640 400 C 818 234.7, 996 129.3, 1174 24",
    );
  });
});

describe("round1", () => {
  it("rounds to 1 decimal place", () => {
    expect(round1(234.6666)).toBe(234.7);
    expect(round1(129.3333)).toBe(129.3);
    expect(round1(100)).toBe(100);
  });
});
