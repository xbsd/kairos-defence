// Matcher results from the stream (SPEC §16.3): match, forecast, recall and the lens.
import { createStore } from "zustand/vanilla";

import type { DtwMsg, ForecastMsg, MatchMsg, RecallMsg } from "../api/messages";

export type Decision = "approved" | "rejected";

export interface MatchState {
  match: MatchMsg | null;
  forecast: ForecastMsg | null;
  recall: RecallMsg | null;
  dtw: DtwMsg | null;
  /** Bumps only when the top-3 set changes: entries appear once, as a discovery (§17.8). */
  entrance: number;
  top3: string;
  /** Decisions made in this session, by proposal seq (the next `match` carries the ledger's). */
  decisions: Record<number, Decision>;
  busy: Record<number, boolean>;
  error: string | null;
}

export interface MatchActions {
  apply: (m: MatchMsg | ForecastMsg | RecallMsg | DtwMsg) => void;
  clear: () => void;
  setBusy: (seq: number, busy: boolean) => void;
  decide: (seq: number, d: Decision) => void;
  setError: (e: string | null) => void;
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
  entrance: 0,
  top3: "",
  decisions: {},
  busy: {},
  error: null,
  apply: (m) => {
    switch (m.type) {
      case "match": {
        const key = top3Key(m);
        const s = get();
        set({ match: m, top3: key, entrance: key !== s.top3 ? s.entrance + 1 : s.entrance });
        return;
      }
      case "forecast":
        set({ forecast: m });
        return;
      case "recall":
        set({ recall: m });
        return;
      case "dtw":
        set({ dtw: m });
        return;
    }
  },
  clear: () => set({ match: null, forecast: null, recall: null, dtw: null, top3: "" }),
  setBusy: (seq, busy) => set({ busy: { ...get().busy, [seq]: busy } }),
  decide: (seq, d) => set({ decisions: { ...get().decisions, [seq]: d } }),
  setError: (error) => set({ error }),
}));

/** The decision for a match entry: this session's click, else what the ledger said. */
export function decisionOf(
  s: MatchState,
  seq: number | null,
  server: Decision | null,
): Decision | null {
  if (seq === null) return null;
  return s.decisions[seq] ?? server;
}
