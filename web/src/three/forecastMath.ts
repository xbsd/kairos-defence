// Pure geometry for the forecast layers and captions (SPEC §13, §17.3, D-132): road clipping to
// the recovery zone, distance and bearing, the compass word, point in polygon. Region meters;
// bearings clockwise from north in [0, 360).
import { bearingDeg, type Vec2 } from "./sceneMath";

const DIRECTIONS = [
  "north",
  "northeast",
  "east",
  "southeast",
  "south",
  "southwest",
  "west",
  "northwest",
] as const;

/** Eight-point compass word for a bearing: the same rule as Python's sim/lexicon.compass8. */
export function compass8(deg: number): (typeof DIRECTIONS)[number] {
  const d = ((deg % 360) + 360) % 360;
  return DIRECTIONS[Math.floor((d + 22.5) / 45) % 8] ?? "north";
}

/** Distance (m) and bearing (°) from one point to another. */
export function distanceBearing(from: Vec2, to: Vec2): { distance: number; bearing: number } {
  return {
    distance: Math.hypot(to[0] - from[0], to[1] - from[1]),
    bearing: bearingDeg(from, to),
  };
}

/** "2.2 km" at 1 km and above, else meters to the nearest 10 ("370 m"). */
export function roughDistance(m: number): string {
  if (!Number.isFinite(m)) return "";
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m / 10) * 10} m`;
}

/** Parameters t in [0, 1] where segment a→b crosses the circle (sorted). */
function crossings(a: Vec2, b: Vec2, c: Vec2, r: number): number[] {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const fx = a[0] - c[0];
  const fy = a[1] - c[1];
  const A = dx * dx + dy * dy;
  if (A === 0) return [];
  const B = 2 * (fx * dx + fy * dy);
  const C = fx * fx + fy * fy - r * r;
  const disc = B * B - 4 * A * C;
  if (disc <= 0) return []; // a miss or a tangent touch
  const s = Math.sqrt(disc);
  return [(-B - s) / (2 * A), (-B + s) / (2 * A)].filter((t) => t > 0 && t < 1);
}

/**
 * The parts of a polyline inside a circle, as polylines (region meters). A tangent touch gives
 * nothing; a chord through gives one two-point part.
 */
export function clipPolylineToCircle(line: Vec2[], center: Vec2, r: number): Vec2[][] {
  const inside = (p: Vec2) => Math.hypot(p[0] - center[0], p[1] - center[1]) < r;
  const out: Vec2[][] = [];
  let cur: Vec2[] | null = null;
  for (let i = 0; i < line.length; i++) {
    const p = line[i] as Vec2;
    if (i === 0) {
      if (inside(p)) cur = [p];
      continue;
    }
    const a = line[i - 1] as Vec2;
    const at = (t: number): Vec2 => [a[0] + t * (p[0] - a[0]), a[1] + t * (p[1] - a[1])];
    for (const t of crossings(a, p, center, r)) {
      if (cur) {
        cur.push(at(t));
        out.push(cur);
        cur = null;
      } else cur = [at(t)];
    }
    if (cur && inside(p)) cur.push(p);
  }
  if (cur && cur.length > 1) out.push(cur);
  return out.filter((part) => part.length > 1);
}

/** The point halfway along a polyline (by length). */
export function midpointAlong(line: Vec2[]): Vec2 | null {
  if (line.length === 0) return null;
  let total = 0;
  for (let i = 1; i < line.length; i++)
    total += Math.hypot(
      (line[i] as Vec2)[0] - (line[i - 1] as Vec2)[0],
      (line[i] as Vec2)[1] - (line[i - 1] as Vec2)[1],
    );
  let left = total / 2;
  for (let i = 1; i < line.length; i++) {
    const a = line[i - 1] as Vec2;
    const b = line[i] as Vec2;
    const d = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (d >= left && d > 0)
      return [a[0] + ((b[0] - a[0]) * left) / d, a[1] + ((b[1] - a[1]) * left) / d];
    left -= d;
  }
  return line[line.length - 1] ?? null;
}

/** Even-odd point in polygon (one ring; the closing vertex may repeat the first). */
export function pointInPolygon(p: Vec2, poly: Vec2[]): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i] as Vec2;
    const b = poly[j] as Vec2;
    if (
      a[1] > p[1] !== b[1] > p[1] &&
      p[0] < ((b[0] - a[0]) * (p[1] - a[1])) / (b[1] - a[1]) + a[0]
    )
      inside = !inside;
  }
  return inside;
}

export function pointInPolygons(p: Vec2, polys: Vec2[][]): boolean {
  return polys.some((poly) => pointInPolygon(p, poly));
}
