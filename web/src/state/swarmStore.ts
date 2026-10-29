// The Swarm view's state (SPEC §17.9, §17.11, D-154): the §14 result and the playhead. The
// playhead changes every animation frame while playing, so the 3D scene reads it inside useFrame
// and the DOM reads it through useThrottledStore (≤ 10 Hz): never per-frame React state.
import { createStore } from "zustand/vanilla";

import type { SwarmResponse } from "../api/messages";

export const SWARM_SPEEDS = [5, 10, 20] as const;
export type SwarmSpeed = (typeof SWARM_SPEEDS)[number];

export interface SwarmState {
  doc: SwarmResponse | null;
  /** Seconds since the query swarm's first radar point (fractional while playing). */
  playhead: number;
  playing: boolean;
  /** Recorded seconds per wall second. */
  speed: SwarmSpeed;
}

export interface SwarmActions {
  setDoc: (doc: SwarmResponse | null) => void;
  setPlayhead: (t: number) => void;
  play: () => void;
  pause: () => void;
  setSpeed: (v: SwarmSpeed) => void;
  /** Advance the playhead by `dtS` wall seconds (the rAF loop); stops at the last second. */
  tick: (dtS: number) => void;
}

/** First and last second the playhead may take: the query's described seconds. */
export function playRange(doc: SwarmResponse | null): [number, number] {
  const t = doc?.query.curves.t_s ?? [];
  if (!t.length) return [0, doc?.observed_s ?? 0];
  return [t[0] as number, t[t.length - 1] as number];
}

function clamp(doc: SwarmResponse | null, t: number): number {
  const [lo, hi] = playRange(doc);
  return Math.min(hi, Math.max(lo, Number.isFinite(t) ? t : lo));
}

export const swarmStore = createStore<SwarmState & SwarmActions>()((set, get) => ({
  doc: null,
  playhead: 0,
  playing: false,
  speed: 10,
  setDoc: (doc) => set({ doc, playhead: playRange(doc)[0], playing: false }),
  setPlayhead: (t) => set({ playhead: clamp(get().doc, t) }),
  play: () => {
    const s = get();
    const [lo, hi] = playRange(s.doc);
    // from the end, play starts over (the presenter's second run)
    set({ playing: true, playhead: s.playhead >= hi ? lo : s.playhead });
  },
  pause: () => set({ playing: false }),
  setSpeed: (speed) => set({ speed }),
  tick: (dtS) => {
    const s = get();
    if (!s.playing || !s.doc) return;
    const hi = playRange(s.doc)[1];
    const t = s.playhead + dtS * s.speed;
    if (t >= hi) set({ playhead: hi, playing: false });
    else set({ playhead: t });
  },
}));
