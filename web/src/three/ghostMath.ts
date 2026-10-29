// Afterglow ghost mapping (SPEC §17.3, D-128): a past flight's target-relative path placed at
// tonight's target-asset centroid (translation only), in region meters.
import type { HistoryPath } from "../api/pages";
import type { Vec2 } from "./sceneMath";

/** Tonight's pseudo-target before an asset is identified (D-081, D-115): no ghosts there. */
export function isFenceTarget(assetId: string | null | undefined): boolean {
  return !assetId || assetId.endsWith("-fence");
}

export interface GhostPoint {
  t: number;
  x: number;
  y: number;
  alt: number;
}

/** The path's points mapped to tonight: centroid + (x_rel, y_rel); rows with a gap are skipped. */
export function mapGhost(path: HistoryPath, centroid: Vec2): GhostPoint[] {
  const out: GhostPoint[] = [];
  for (const [t, x, y, alt] of path.points) {
    if (x === null || y === null) continue;
    out.push({ t, x: centroid[0] + x, y: centroid[1] + y, alt: alt ?? 0 });
  }
  return out;
}

/** The index of the ghost point where that flight was at the matched moment (clamped). */
export function alignedIndex(points: GhostPoint[], tAligned: number): number {
  if (!points.length) return -1;
  let best = 0;
  for (let k = 0; k < points.length; k++) {
    if ((points[k] as GhostPoint).t <= tAligned) best = k;
    else break;
  }
  return Math.min(points.length - 1, Math.max(0, best));
}

/** A fixed hash in [0, 1) for a segment index (the dissolve order, deterministic). */
export function segmentHash(k: number): number {
  const s = Math.sin((k + 1) * 12.9898) * 43758.5453;
  return s - Math.floor(s);
}

export const DISSOLVE_MS = 1200;
export const STAGGER_MS = 150;

/** A segment's alpha `age` ms after the ghost began to dissolve (ghost `g` of the set). */
export function dissolveAlpha(k: number, g: number, age: number): number {
  const u = (age - g * STAGGER_MS) / DISSOLVE_MS;
  if (u <= 0) return 0;
  if (u >= 1) return 1;
  const thr = segmentHash(k) * 0.8;
  return Math.min(1, Math.max(0, (u - thr) / 0.2));
}

/** Ghost end points closer than this share one label anchor (meters, D-166). */
export const LABEL_CLUSTER_M = 400;

/**
 * Where each ghost's label goes (§17.13, D-166): ghosts whose end points lie within `radiusM` of
 * an earlier ghost's end point share that ghost's end point as their anchor and stack one row
 * apart (`slot`), so labels never overprint when the recovery points sit close but not on top of
 * each other. A ghost with no end point gets `anchor: -1`.
 */
export function labelSlots(
  ends: (GhostPoint | null | undefined)[],
  radiusM = LABEL_CLUSTER_M,
): { anchor: number; slot: number }[] {
  const out: { anchor: number; slot: number }[] = [];
  const used = new Map<number, number>();
  ends.forEach((e, i) => {
    if (!e) {
      out.push({ anchor: -1, slot: 0 });
      return;
    }
    let anchor = i;
    for (const [root] of used) {
      const r = ends[root];
      if (r && Math.hypot(e.x - r.x, e.y - r.y) <= radiusM) {
        anchor = root;
        break;
      }
    }
    const slot = used.get(anchor) ?? 0;
    used.set(anchor, slot + 1);
    out.push({ anchor, slot });
  });
  return out;
}
