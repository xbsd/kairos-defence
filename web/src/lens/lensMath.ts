// Time-warp lens math (SPEC §17.7, D-126): the cost matrix, the shared time scale and the
// connectors. "Same time" pairs equal sample indices (what the Euclidean distance compares, the
// first `overlap` samples); "Warped" pairs are the real DTW path. Each connector keeps its query
// index i; the morph moves only the candidate end, from i to its path partner j.

export type Pair = [number, number];

/** The `cost` field: float32 little-endian, row-major, base64 → (n, m) values (NaN outside the band). */
export function decodeCost(b64: string, shape: readonly [number, number]): Float32Array {
  const bin = atob(b64);
  const n = shape[0] * shape[1];
  if (bin.length !== n * 4) throw new Error(`cost has ${bin.length / 4} cells, shape says ${n}`);
  const view = new DataView(new ArrayBuffer(bin.length));
  for (let k = 0; k < bin.length; k++) view.setUint8(k, bin.charCodeAt(k));
  const out = new Float32Array(n);
  for (let k = 0; k < n; k++) out[k] = view.getFloat32(k * 4, true);
  return out;
}

/** One x scale for both series: sample k of either sits at the same x, so paces overhang. */
export function lensScale(n: number, m: number, width: number, pad = 8): (k: number) => number {
  const L = Math.max(n, m, 2);
  const span = Math.max(1, width - 2 * pad);
  return (k: number) => pad + (k / (L - 1)) * span;
}

/** Same-time connectors: (i, i) for i below the overlap. */
export function sameTimeConnectors(n: number, m: number, overlap: number): Pair[] {
  const k = Math.min(n, m, overlap);
  return Array.from({ length: Math.max(0, k) }, (_, i) => [i, i] as Pair);
}

/** The DTW path subsampled evenly to at most `max` pairs, first and last always kept. */
export function warpedConnectors(path: readonly Pair[], max = 48): Pair[] {
  if (path.length <= max) return path.map((p) => [p[0], p[1]] as Pair);
  const out: Pair[] = [];
  for (let k = 0; k < max; k++) {
    const idx = Math.round((k * (path.length - 1)) / (max - 1));
    const p = path[idx] as Pair;
    out.push([p[0], p[1]]);
  }
  return out;
}

export interface Connector {
  /** Query (tonight) sample index. */
  i: number;
  /** Candidate index in "Same time" mode (i) and in "Warped" mode (the path partner). */
  j0: number;
  j1: number;
  /** False when tonight's sample i has no same-time partner (i ≥ overlap). */
  same: boolean;
}

export function morphConnectors(path: readonly Pair[], overlap: number, max = 48): Connector[] {
  return warpedConnectors(path, max).map(([i, j]) => ({ i, j0: i, j1: j, same: i < overlap }));
}

/** ease-in-out (the --ease-inout token's curve, close enough for a 1.2 s morph). */
export function easeInOut(t: number): number {
  const u = Math.min(1, Math.max(0, t));
  return u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2;
}

/** Connector endpoints at morph progress t (0 = same time, 1 = warped): [i, j] per connector. */
export function connectorAt(cs: readonly Connector[], t: number): [number, number][] {
  const e = easeInOut(t);
  return cs.map((c) => [c.i, c.j0 + (c.j1 - c.j0) * e]);
}

/** The pace readout: the matcher's own words, capitalized, or "Same pace (within 10%)". */
export function paceWords(text: string | null | undefined): string {
  if (!text) return "Same pace (within 10%)";
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** min and the 95th percentile of the finite values (the matrix's color range). */
export function costRange(v: Float32Array): [number, number] {
  const xs = Array.from(v).filter((x) => Number.isFinite(x));
  if (!xs.length) return [0, 1];
  xs.sort((a, b) => a - b);
  const lo = xs[0] as number;
  const hi = xs[Math.min(xs.length - 1, Math.floor(0.95 * xs.length))] as number;
  return [lo, hi > lo ? hi : lo + 1];
}

/** The y extent shared by both curves (same units). */
export function valueRange(a: readonly number[], b: readonly number[]): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of [...a, ...b]) {
    if (!Number.isFinite(v)) continue;
    lo = Math.min(lo, v);
    hi = Math.max(hi, v);
  }
  if (!Number.isFinite(lo)) return [0, 1];
  return hi > lo ? [lo, hi] : [lo - 1, hi + 1];
}

export const CHANNELS: { key: string; label: string; unit: string }[] = [
  { key: "dist_target_m", label: "Distance", unit: "m" },
  { key: "speed_ms", label: "Speed", unit: "m/s" },
  { key: "alt_m", label: "Altitude", unit: "m" },
  { key: "turn_rate_dps", label: "Turn rate", unit: "°/s" },
  { key: "vspeed_ms", label: "Climb rate", unit: "m/s" },
];

/** Cell centers of the path in canvas pixels (one pixel per cell, row = tonight's sample). */
export function pathCells(path: readonly Pair[]): [number, number][] {
  return path.map(([i, j]) => [j + 0.5, i + 0.5]);
}
