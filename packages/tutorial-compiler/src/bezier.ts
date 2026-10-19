import type { Point } from "./types.js";

/**
 * Rounds a number to at most 1 decimal place.
 */
export function round1(num: number): number {
  return Math.round(num * 10) / 10;
}

export interface BezierOptions {
  /**
   * Upward vertical curvature offset in pixels at t = 1/3.
   * Default: 40.
   */
  curveOffsetY1?: number;

  /**
   * Upward vertical curvature offset in pixels at t = 2/3.
   * Default: 20.
   */
  curveOffsetY2?: number;

  /**
   * If true, suppresses trajectory arc and returns points collapsed onto end.
   */
  reducedMotion?: boolean;
}

/**
 * Generates a cubic Bezier cursor trajectory [P0, P1, P2, P3] between start and end.
 *
 * Emulates human biomechanics: as the wrist/arm travels, the motion arcs slightly
 * upward (in screen coordinates, decreasing Y) before settling onto the target center.
 *
 * @param start Start point (e.g. viewport center or previous element target center)
 * @param end Target end point (e.g. current element center)
 * @param options Trajectory customization options
 * @returns Array of four points [P0, P1, P2, P3]
 */
export function generateCursorTrajectory(
  start: Point,
  end: Point,
  options?: BezierOptions,
): [Point, Point, Point, Point] {
  const p3: Point = { x: round1(end.x), y: round1(end.y) };

  if (options?.reducedMotion) {
    return [{ ...p3 }, { ...p3 }, { ...p3 }, { ...p3 }];
  }

  const p0: Point = { x: round1(start.x), y: round1(start.y) };
  const dx = end.x - start.x;
  const dy = end.y - start.y;

  if (dx === 0 && dy === 0) {
    return [{ ...p0 }, { ...p0 }, { ...p0 }, { ...p0 }];
  }

  const offsetY1 = options?.curveOffsetY1 ?? 40;
  const offsetY2 = options?.curveOffsetY2 ?? 20;

  const p1: Point = {
    x: round1(start.x + dx / 3),
    y: round1(start.y + dy / 3 - offsetY1),
  };

  const p2: Point = {
    x: round1(start.x + (2 * dx) / 3),
    y: round1(start.y + (2 * dy) / 3 - offsetY2),
  };

  return [p0, p1, p2, p3];
}

/**
 * Evaluates a point along a cubic Bezier curve at parametric time t in [0, 1].
 *
 * B(t) = (1-t)^3 * P0 + 3(1-t)^2 * t * P1 + 3(1-t) * t^2 * P2 + t^3 * P3
 */
export function evaluateBezierPoint(
  path: [Point, Point, Point, Point],
  t: number,
): Point {
  const clampedT = Math.max(0, Math.min(1, t));
  const u = 1 - clampedT;
  const tt = clampedT * clampedT;
  const uu = u * u;
  const uuu = uu * u;
  const ttt = tt * clampedT;

  const [p0, p1, p2, p3] = path;

  const x = uuu * p0.x + 3 * uu * clampedT * p1.x + 3 * u * tt * p2.x + ttt * p3.x;
  const y = uuu * p0.y + 3 * uu * clampedT * p1.y + 3 * u * tt * p2.y + ttt * p3.y;

  return {
    x: round1(x),
    y: round1(y),
  };
}

/**
 * Converts a 4-point cubic Bezier path into an SVG path d-string.
 * Example: "M 640 400 C 818 234.7, 996 129.3, 1174 24"
 */
export function bezierToSvgPath(path: [Point, Point, Point, Point]): string {
  const [p0, p1, p2, p3] = path;
  return `M ${p0.x} ${p0.y} C ${p1.x} ${p1.y}, ${p2.x} ${p2.y}, ${p3.x} ${p3.y}`;
}
