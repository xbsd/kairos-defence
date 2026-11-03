// The DTW workbench's state (D-189): the pinned trace and the replay clock. A newer trace from the
// stream never replaces the pinned one by itself; `pin` does, on the user's click. The clock is
// advanced from requestAnimationFrame (`useWorkbenchClock`), never per React render (§17.11).
import { createStore } from "zustand/vanilla";

import type { MatcherTraceMsg } from "../api/messages";
import {
  aligned,
  DEFAULT_RATE,
  endMs,
  nextStepMs,
  rescale,
  type Aligned,
} from "./workbenchMachine";

export interface WorkbenchState {
  open: boolean;
  msg: MatcherTraceMsg | null;
  items: Aligned[];
  elapsed: number;
  rate: number;
  playing: boolean;
  /** Where the trace came from: the stream (Live page, Live watch) or a fetch (Match explainer). */
  source: "stream" | "fetch";
  version: number;
}

export interface WorkbenchActions {
  openWith: (msg: MatcherTraceMsg, source: "stream" | "fetch", reduce: boolean) => void;
  pin: (msg: MatcherTraceMsg, reduce: boolean) => void;
  close: () => void;
  tick: (dtMs: number) => void;
  setPlaying: (playing: boolean) => void;
  step: () => void;
  replay: (reduce: boolean) => void;
  setRate: (rate: number) => void;
}

export const workbenchStore = createStore<WorkbenchState & WorkbenchActions>()((set, get) => {
  const bump = (patch: Partial<WorkbenchState>) => set({ ...patch, version: get().version + 1 });
  const start = (msg: MatcherTraceMsg, reduce: boolean) => {
    const items = aligned(msg.trace);
    const rate = get().rate;
    // reduced motion shows the final state at once (§17.11)
    return { msg, items, elapsed: reduce ? endMs(items.length, rate) : 0, playing: !reduce };
  };
  return {
    open: false,
    msg: null,
    items: [],
    elapsed: 0,
    rate: DEFAULT_RATE,
    playing: false,
    source: "stream",
    version: 0,
    openWith: (msg, source, reduce) => bump({ open: true, source, ...start(msg, reduce) }),
    pin: (msg, reduce) => bump(start(msg, reduce)),
    close: () => bump({ open: false, playing: false }),
    tick: (dtMs) => {
      const s = get();
      if (!s.playing || !s.open) return;
      const end = endMs(s.items.length, s.rate);
      const elapsed = Math.min(end, s.elapsed + dtMs);
      bump({ elapsed, playing: elapsed < end });
    },
    setPlaying: (playing) => {
      const s = get();
      const end = endMs(s.items.length, s.rate);
      // Play at the end starts over
      bump(playing && s.elapsed >= end ? { playing, elapsed: 0 } : { playing });
    },
    step: () => {
      const s = get();
      bump({ playing: false, elapsed: nextStepMs(s.elapsed, s.items.length, s.rate) });
    },
    replay: (reduce) => {
      const s = get();
      bump({ elapsed: reduce ? endMs(s.items.length, s.rate) : 0, playing: !reduce });
    },
    setRate: (rate) => {
      const s = get();
      bump({ rate, elapsed: rescale(s.elapsed, s.items.length, s.rate, rate) });
    },
  };
});

/** The replay clock: requestAnimationFrame while the dialog is open (§17.11). */
export function startWorkbenchClock(): () => void {
  let raf = 0;
  let last = performance.now();
  const step = (now: number) => {
    workbenchStore.getState().tick(Math.min(250, now - last));
    last = now;
    raf = requestAnimationFrame(step);
  };
  raf = requestAnimationFrame(step);
  return () => cancelAnimationFrame(raf);
}
