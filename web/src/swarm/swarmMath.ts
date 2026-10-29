// Pure helpers for the Swarm view (SPEC §14, §17.9, D-154). Positions are the API's
// target-relative meters [x east, y north, altitude] per drone and second; `aligned[i]` maps the
// query's curves row i to the match's curves row (the DTW path). Nothing here invents data: the
// only in-between values are linear between two recorded seconds while the playhead moves.
import type { SwarmFlight, SwarmResponse } from "../api/messages";
import { baseName, localDate } from "../lib/format";

export type P3 = [number, number, number];
type Track = readonly (readonly (number | null)[])[];

function sample(track: Track, i: number): P3 | null {
  const p = track[i];
  if (!p) return null;
  const [x, y, a] = p;
  if (x === null || x === undefined || y === null || y === undefined) return null;
  return [x, y, a ?? 0];
}

/** One drone at a fractional second (index = second − first second): linear between the two
 * recorded seconds around it; null when either is missing or `s` is outside the track. */
export function droneAt(track: Track, s: number, t0 = 0): P3 | null {
  const u = s - t0;
  if (!Number.isFinite(u) || u < 0 || u > track.length - 1) return null;
  const i = Math.floor(u);
  const f = u - i;
  const a = sample(track, i);
  if (f < 1e-9 || i + 1 >= track.length) return a;
  const b = sample(track, i + 1);
  if (!a || !b) return f < 0.5 ? a : b;
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

/** Every drone of a flight at second `s`. */
export function dronesAt(f: SwarmFlight, s: number): (P3 | null)[] {
  const t0 = f.t_s[0] ?? 0;
  return f.positions.map((track) => droneAt(track, s, t0));
}

/** Mean of the present drones (null when none). */
export function centroidOf(pts: readonly (P3 | null)[]): P3 | null {
  let n = 0;
  const c: P3 = [0, 0, 0];
  for (const p of pts) {
    if (!p) continue;
    c[0] += p[0];
    c[1] += p[1];
    c[2] += p[2];
    n += 1;
  }
  return n ? [c[0] / n, c[1] / n, c[2] / n] : null;
}

/** Formation edges (§17.9): each present drone to its nearest present neighbor (horizontal
 * distance), as unique pairs [i, j] with i < j, sorted. */
export function nearestEdges(pts: readonly (P3 | null)[]): [number, number][] {
  const seen = new Set<string>();
  const out: [number, number][] = [];
  pts.forEach((p, i) => {
    if (!p) return;
    let best = -1;
    let bestD = Infinity;
    pts.forEach((q, j) => {
      if (!q || j === i) return;
      const d = Math.hypot(p[0] - q[0], p[1] - q[1]);
      if (d < bestD) {
        bestD = d;
        best = j;
      }
    });
    if (best < 0) return;
    const pair: [number, number] = i < best ? [i, best] : [best, i];
    const key = `${pair[0]}-${pair[1]}`;
    if (!seen.has(key)) {
      seen.add(key);
      out.push(pair);
    }
  });
  return out.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
}

/** The last row of `tS` (ascending seconds) at or before `s`; −1 before the first. */
export function rowAt(tS: readonly number[], s: number): number {
  let lo = 0;
  let hi = tS.length - 1;
  if (hi < 0 || s < (tS[0] as number)) return -1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if ((tS[mid] as number) <= s) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

/** The matched flight's (fractional) second aligned with query second `s` by the DTW path,
 * linear between the aligned rows around `s`; null without a match. */
export function matchSecond(doc: SwarmResponse, s: number): number | null {
  const m = doc.match;
  const qt = doc.query.curves.t_s;
  if (!m || !doc.aligned.length) return null;
  const i = rowAt(qt, s);
  if (i < 0) return null;
  const mt = m.curves.t_s;
  const at = (k: number): number | null => {
    const j = doc.aligned[Math.min(k, doc.aligned.length - 1)];
    return j === undefined ? null : (mt[Math.min(j, mt.length - 1)] ?? null);
  };
  const a = at(i);
  if (a === null) return null;
  const qa = qt[i] as number;
  const qb = qt[i + 1];
  const b = qb === undefined ? null : at(i + 1);
  if (qb === undefined || b === null || qb <= qa) return a;
  return a + ((s - qa) / (qb - qa)) * (b - a);
}

/** The ghost (§17.9): the matched formation at its DTW-aligned second, re-centered on tonight's
 * centroid at `s`, so the two formations are compared in place. */
export function ghostAt(doc: SwarmResponse, s: number): (P3 | null)[] {
  const m = doc.match;
  if (!m) return [];
  const ms = matchSecond(doc, s);
  const c = centroidOf(dronesAt(doc.query, s));
  if (ms === null || !c) return m.positions.map(() => null);
  const pts = dronesAt(m, ms);
  const mc = centroidOf(pts);
  if (!mc) return pts.map(() => null);
  return pts.map((p) => (p ? [c[0] + p[0] - mc[0], c[1] + p[1] - mc[1], p[2]] : null));
}

/** The match's descriptor on the query's rows through `aligned` (§14 output). */
export function resampleAligned(
  values: readonly (number | null)[],
  aligned: readonly number[],
): (number | null)[] {
  return aligned.map((j) => values[j] ?? null);
}

/** [min, max] over every finite value of the series ([0, 1] when there is none). */
export function extent(...series: readonly (readonly (number | null)[])[]): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const s of series)
    for (const v of s)
      if (v !== null && Number.isFinite(v)) {
        lo = Math.min(lo, v);
        hi = Math.max(hi, v);
      }
  if (!Number.isFinite(lo)) return [0, 1];
  if (hi - lo < 1e-9) return [lo - 1, hi + 1];
  return [lo, hi];
}

/** "2026-06-14", the local calendar day of a UTC time at an offset (hours). */
export function localYmd(iso: string | null | undefined, offsetH: number): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  return new Date(t + offsetH * 3600_000).toISOString().slice(0, 10);
}

/** Whole days from one "YYYY-MM-DD" to another (absolute). */
export function daysBetween(a: string, b: string): number {
  return Math.round(Math.abs(Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`)) / 864e5);
}

const WORDS = [
  "zero",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
  "eleven",
  "twelve",
];

/** "six weeks", "one week", "13 weeks". */
export function weeksWord(n: number): string {
  const w = WORDS[n] ?? String(n);
  return `${w} week${n === 1 ? "" : "s"}`;
}

/** What the encore caption says (D-155), computed from the swarm result. */
export interface SwarmFacts {
  queryBase: string;
  queryDay: string;
  matchBase: string;
  matchDay: string;
  weeks: number;
  otherRegion: boolean;
  sameBase: boolean;
}

/** The encore facts from a §14 result and the installations' UTC offsets; null without a match
 * or a known offset (a caption never shows a placeholder). */
export function swarmFacts(
  doc: SwarmResponse | null,
  offsets: Record<string, number>,
): SwarmFacts | null {
  const q = doc?.query;
  const m = doc?.match;
  if (!q || !m) return null;
  const oq = offsets[q.installation_id];
  const om = offsets[m.installation_id];
  if (oq === undefined || om === undefined) return null;
  const dq = localYmd(q.start_ts, oq);
  const dm = localYmd(m.start_ts, om);
  if (!dq || !dm) return null;
  return {
    queryBase: baseName(q.installation_id),
    queryDay: localDate(dq),
    matchBase: baseName(m.installation_id),
    matchDay: localDate(dm),
    weeks: Math.round(daysBetween(dm, dq) / 7),
    otherRegion: q.region_id !== m.region_id,
    sameBase: q.installation_id === m.installation_id,
  };
}

/** The descriptor rows of the text table: every `step` seconds of the query. */
export function tableRows(doc: SwarmResponse, step = 30): number[] {
  const t = doc.query.curves.t_s;
  const out: number[] = [];
  let next = -Infinity;
  t.forEach((s, i) => {
    if (s >= next) {
      out.push(i);
      next = s + step;
    }
  });
  return out;
}
