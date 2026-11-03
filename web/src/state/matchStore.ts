// Matcher results from the stream (SPEC §16.3): match, forecast, recall and the lens.
import { createStore } from "zustand/vanilla";

import type { DtwMsg, ForecastMsg, MatchMsg, MatcherTraceMsg, RecallMsg } from "../api/messages";

export type Decision = "approved" | "rejected";
export type LensMode = "same" | "warped";

/** A lens selection: one of the current matches and a channel (§17.7). */
export interface LensSel {
  track: string;
  channel: string;
}

export const DEFAULT_CHANNEL = "dist_target_m";

export function dtwKey(track: string, channel: string): string {
  return `${track}|${channel}`;
}

export interface MatchState {
  match: MatchMsg | null;
  forecast: ForecastMsg | null;
  recall: RecallMsg | null;
  dtw: DtwMsg | null;
  /** Every lens payload received, by `dtwKey` (the stream's top match and requested ones). */
  dtwBy: Record<string, DtwMsg>;
  /** performance.now() when the last `match` arrived (core beams, §17.3). */
  matchWall: number;
  /** The match entry under the pointer or focus (its ghost brightens, §17.3). */
  hovered: string | null;
  /** The lens's chosen match and channel; null follows the top match. */
  lensSel: LensSel | null;
  lensMode: LensMode;
  /** Bumps only when the top-3 set changes: entries appear once, as a discovery (§17.8). */
  entrance: number;
  top3: string;
  /** Decisions made in this session, by proposal seq (the next `match` carries the ledger's). */
  decisions: Record<number, Decision>;
  busy: Record<number, boolean>;
  error: string | null;
  /** The latest rerun's matcher trace (the DTW workbench, D-188). */
  trace: MatcherTraceMsg | null;
}

export interface MatchActions {
  apply: (m: MatchMsg | ForecastMsg | RecallMsg | DtwMsg | MatcherTraceMsg, now?: number) => void;
  clear: () => void;
  setBusy: (seq: number, busy: boolean) => void;
  decide: (seq: number, d: Decision) => void;
  setError: (e: string | null) => void;
  setHovered: (track: string | null) => void;
  setLensSel: (sel: LensSel | null) => void;
  setLensMode: (mode: LensMode) => void;
}

export function top3Key(m: MatchMsg | null): string {
  return m
    ? m.matches
        .slice(0, 3)
        .map((x) => x.incident_id)
        .sort()
        .join("|")
    : "";
}

export const matchStore = createStore<MatchState & MatchActions>()((set, get) => ({
  match: null,
  forecast: null,
  recall: null,
  dtw: null,
  dtwBy: {},
  matchWall: 0,
  hovered: null,
  lensSel: null,
  lensMode: "warped",
  entrance: 0,
  top3: "",
  decisions: {},
  busy: {},
  error: null,
  trace: null,
  apply: (m, now = performance.now()) => {
    switch (m.type) {
      case "match": {
        const key = top3Key(m);
        const s = get();
        set({
          match: m,
          top3: key,
          matchWall: now,
          entrance: key !== s.top3 ? s.entrance + 1 : s.entrance,
        });
        return;
      }
      case "forecast":
        set({ forecast: m });
        return;
      case "recall":
        set({ recall: m });
        return;
      case "matcher_trace":
        set({ trace: m });
        return;
      case "dtw": {
        const s = get();
        const dtwBy = { ...s.dtwBy, [dtwKey(m.match_track_id, m.channel)]: m };
        const top = s.match?.matches[0]?.track_id;
        // the stream's own lens is the top match on the default channel
        const isTop =
          m.channel === DEFAULT_CHANNEL && (top === undefined || top === m.match_track_id);
        set(isTop || s.dtw === null ? { dtw: m, dtwBy } : { dtwBy });
        return;
      }
    }
  },
  clear: () =>
    set({
      match: null,
      forecast: null,
      recall: null,
      dtw: null,
      dtwBy: {},
      top3: "",
      matchWall: 0,
      trace: null,
    }),
  setBusy: (seq, busy) => set({ busy: { ...get().busy, [seq]: busy } }),
  decide: (seq, d) => set({ decisions: { ...get().decisions, [seq]: d } }),
  setError: (error) => set({ error }),
  setHovered: (hovered) => set({ hovered }),
  setLensSel: (lensSel) => set({ lensSel }),
  setLensMode: (lensMode) => set({ lensMode }),
}));

/** The lens payload to show: the selection's when it has arrived, else the stream's top. */
export function lensDtw(s: MatchState): DtwMsg | null {
  if (s.lensSel) {
    const hit = s.dtwBy[dtwKey(s.lensSel.track, s.lensSel.channel)];
    if (hit) return hit;
  }
  return s.dtw;
}

/** The current top-3 match whose pace differs most from tonight's (|log warp|), or null. */
export function farthestWarp(m: MatchMsg | null): MatchMsg["matches"][number] | null {
  let best: MatchMsg["matches"][number] | null = null;
  let score = 0;
  for (const x of m?.matches.slice(0, 3) ?? []) {
    const k = x.warp_ratio;
    if (k === null || !Number.isFinite(k) || k <= 0) continue;
    const d = Math.abs(Math.log(k));
    if (d > score) {
      score = d;
      best = x;
    }
  }
  return best;
}

/** The decision for a match entry: this session's click, else what the ledger said. */
export function decisionOf(
  s: MatchState,
  seq: number | null,
  server: Decision | null,
): Decision | null {
  if (seq === null) return null;
  return s.decisions[seq] ?? server;
}
