// The DTW workbench's replay (D-189): a pure state machine over a recorded matcher trace. The
// real computation took tens of milliseconds; this replays its record in slow motion, every value
// from the trace (rule 10). Time is the replay's elapsed milliseconds at `rate` candidates per
// second: the shortlist, then one aligned candidate landing every 1 / rate s, then the fusion,
// then done. Reduced motion jumps straight to done.
import type { MatcherTrace, TraceDetail } from "../api/messages";
import { tPlus } from "../lib/format";

export type Stage = "shortlist" | "align" | "fusion" | "done";

export const SHORTLIST_MS = 1500;
export const FUSION_MS = 1500;
export const RATES = [3, 6, 10] as const;
export const DEFAULT_RATE = 6;

/** One aligned candidate with its scalar fields (from the trace's columns, by `order`). */
export interface Aligned {
  order: number;
  detail: TraceDetail;
  track: string;
  /** The incident, with the track when the incident has several (`candidateName`). */
  incident: string;
  startMs: number;
  vectorDistance: number | null;
  distance: number | null;
  dNorm: number | null;
  shapeSim: number | null;
  band: number | null;
  m: number | null;
  ms: number | null;
}

export interface WbState {
  stage: Stage;
  /** Candidates landed so far (0 to `details.length`). */
  step: number;
  /** The candidate on screen: the last landed one, or null before the first. */
  current: Aligned | null;
  /** Landed candidates by shape similarity, best first (ties: computed order). */
  ranking: Aligned[];
}

function at<T>(xs: T[] | undefined, i: number): T | null {
  const v = xs?.[i];
  return v === undefined ? null : v;
}

/** Incidents with more than one track in the shortlist (a swarm's drones). */
export function repeatedIncidents(t: MatcherTrace): Set<string> {
  const seen = new Set<string>();
  const twice = new Set<string>();
  for (const i of t.prefilter.incident_id) (seen.has(i) ? twice : seen).add(i);
  return twice;
}

/** A candidate's name: its incident, plus the track ("T3") when the incident has several
 * tracks in the shortlist, so a swarm's drones are told apart. */
export function candidateName(track: string, incident: string, repeated: Set<string>): string {
  if (!repeated.has(incident)) return incident;
  const tail = track.startsWith(`${incident}-`) ? track.slice(incident.length + 1) : track;
  return `${incident} ${tail}`;
}

/** The trace's replayed candidates in computed order, with their columns. */
export function aligned(t: MatcherTrace): Aligned[] {
  const p = t.prefilter;
  const d = t.dtw;
  const rep = repeatedIncidents(t);
  return d.detail.map((x) => ({
    order: x.order,
    detail: x,
    track: x.track_id,
    incident: candidateName(x.track_id, at(p.incident_id, x.order) ?? "", rep),
    startMs: at(p.start_ts_ms, x.order) ?? 0,
    vectorDistance: at(p.distance, x.order),
    distance: at(d.distance, x.order),
    dNorm: at(d.d_norm, x.order),
    shapeSim: at(d.shape_sim, x.order),
    band: at(d.band, x.order),
    m: at(d.m, x.order),
    ms: at(d.ms_each, x.order),
  }));
}

/** When candidate `i` (0-based) lands, in ms of replay. */
export function landingMs(i: number, rate: number): number {
  return SHORTLIST_MS + (i * 1000) / rate;
}

export function fusionMs(n: number, rate: number): number {
  return landingMs(n, rate);
}

export function endMs(n: number, rate: number): number {
  return fusionMs(n, rate) + FUSION_MS;
}

export function stepAt(elapsed: number, n: number, rate: number): number {
  if (elapsed < SHORTLIST_MS) return 0;
  // the landed count from the landing times themselves, so a candidate has landed exactly at
  // landingMs(i) despite floating-point rounding
  let k = Math.min(n, Math.floor(((elapsed - SHORTLIST_MS) * rate) / 1000) + 1);
  while (k < n && landingMs(k, rate) <= elapsed) k++;
  while (k > 0 && landingMs(k - 1, rate) > elapsed) k--;
  return k;
}

export function rankLanded(items: Aligned[]): Aligned[] {
  return [...items].sort((a, b) => {
    const sa = a.shapeSim ?? -1;
    const sb = b.shapeSim ?? -1;
    return sa === sb ? a.order - b.order : sb - sa;
  });
}

export function stateAt(items: Aligned[], elapsed: number, rate: number): WbState {
  const n = items.length;
  const step = stepAt(elapsed, n, rate);
  const stage: Stage =
    elapsed < SHORTLIST_MS
      ? "shortlist"
      : elapsed < fusionMs(n, rate)
        ? "align"
        : elapsed < endMs(n, rate)
          ? "fusion"
          : "done";
  const landed = items.slice(0, step);
  return {
    stage,
    step,
    current: step > 0 ? (items[step - 1] ?? null) : null,
    ranking: rankLanded(landed),
  };
}

/** The final state (reduced motion, or the end of the replay). */
export function finalState(items: Aligned[], rate: number): WbState {
  return stateAt(items, endMs(items.length, rate), rate);
}

/** The replay time of the next step after `elapsed`: the next landing, then the fusion, then
 * the end. */
export function nextStepMs(elapsed: number, n: number, rate: number): number {
  if (elapsed < SHORTLIST_MS) return SHORTLIST_MS;
  const step = stepAt(elapsed, n, rate);
  if (step < n) return landingMs(step, rate);
  return elapsed < fusionMs(n, rate) ? fusionMs(n, rate) : endMs(n, rate);
}

/** The same step at another rate (changing the speed never jumps the replay). */
export function rescale(elapsed: number, n: number, oldRate: number, newRate: number): number {
  if (elapsed < SHORTLIST_MS) return elapsed;
  const ender = endMs(n, oldRate);
  if (elapsed >= ender) return endMs(n, newRate);
  const fus = fusionMs(n, oldRate);
  if (elapsed >= fus) return fusionMs(n, newRate) + (elapsed - fus);
  const into = (elapsed - SHORTLIST_MS) * (oldRate / 1000); // candidates elapsed (fractional)
  return SHORTLIST_MS + (into * 1000) / newRate;
}

/** What the header says: the real time of the real computation, and what is replayed. */
export function headline(t: MatcherTrace, rate: number): string {
  const n = t.dtw.detail.length;
  const total = t.dtw.distance.length;
  const ms = t.dtw.ms === null ? "–" : `${Math.round(t.dtw.ms)} ms`;
  const extra = n > t.trace_paths ? ` and ${n - t.trace_paths} more of the final top 10` : "";
  const first = Math.min(t.trace_paths, total);
  return (
    `Slow-motion replay of rerun ${tPlus(t.t_s)}: ${total} alignments computed in ${ms}; ` +
    `the first ${first}${extra} replayed at ${rate} per second`
  );
}

/** A curve's value at fraction `f` of its length (linear between samples; null if a neighbor
 * is missing). The curves are PAA views of the full series, so a path index `i` of `n` samples
 * sits at fraction i / (n − 1). */
export function valueAt(curve: (number | null)[], f: number): number | null {
  if (!curve.length) return null;
  const x = Math.min(1, Math.max(0, f)) * (curve.length - 1);
  const a = Math.floor(x);
  const b = Math.min(curve.length - 1, a + 1);
  const va = curve[a];
  const vb = curve[b];
  if (va === null || va === undefined || vb === null || vb === undefined) return null;
  return va + (vb - va) * (x - a);
}
