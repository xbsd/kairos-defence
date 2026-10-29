// Auto-degrade (SPEC §17.11): if frame time stays above 25 ms for 2 s, drop bloom (level 1);
// another 2 s, halve the packet budget (level 2). The frame time is smoothed (EMA over about ten
// frames) so a single slow frame never degrades; any return below 25 ms restarts the window.

export const SLOW_FRAME_MS = 25;
export const SLOW_FOR_S = 2;
const EMA = 0.1;

export interface PerfState {
  level: 0 | 1 | 2;
  ema: number;
  slowSince: number | null;
}

export const PERF_START: PerfState = { level: 0, ema: 16.7, slowSince: null };

/** Fold one frame (`frameMs`, at wall time `nowS` seconds) into the policy. */
export function stepPerf(s: PerfState, frameMs: number, nowS: number): PerfState {
  const ema = s.ema + EMA * (Math.min(frameMs, 250) - s.ema);
  if (ema <= SLOW_FRAME_MS) return { level: s.level, ema, slowSince: null };
  if (s.slowSince === null) return { level: s.level, ema, slowSince: nowS };
  if (nowS - s.slowSince >= SLOW_FOR_S && s.level < 2) {
    return { level: (s.level + 1) as 1 | 2, ema, slowSince: nowS };
  }
  return { level: s.level, ema, slowSince: s.slowSince };
}

export type PerfLabel = "full" | "no-bloom" | "half-packets" | "reduced";

export function perfLabel(level: 0 | 1 | 2, reduce: boolean): PerfLabel {
  if (reduce) return "reduced";
  return level === 0 ? "full" : level === 1 ? "no-bloom" : "half-packets";
}
