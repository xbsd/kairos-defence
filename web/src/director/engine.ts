// The Director's pure rules (§17.10, D-123): which beat is current, and what → and ← do.
import { BEATS, REVEAL_ALL, type Beat, type PanelId, type Reveal } from "./beats";

/** The last clock beat whose start is at or before replay second `t` (0 before T+0). */
export function beatAt(t: number, beats: readonly Beat[] = BEATS): number {
  let i = 0;
  beats.forEach((b, k) => {
    if (b.kind === "clock" && b.start !== null && b.start <= t + 1e-6) i = k;
  });
  return i;
}

/** The current beat: a page beat once the presenter moved there, else the clock's. */
export function currentBeat(
  t: number,
  page: number | null,
  beats: readonly Beat[] = BEATS,
): number {
  return page ?? beatAt(t, beats);
}

/** What a → or ← does from beat `i`. */
export type Step =
  | { kind: "seek"; t: number } // stay on Live watch, jump the replay clock
  | { kind: "page"; index: number } // open a page beat
  | { kind: "live"; index: number; t: number } // back from a page to Live watch at a clock beat
  | { kind: "none" };

function stepTo(from: number, to: number, beats: readonly Beat[]): Step {
  const a = beats[from];
  const b = beats[to];
  if (!a || !b || from === to) return { kind: "none" };
  if (b.kind === "page") return { kind: "page", index: to };
  if (a.kind === "page") return { kind: "live", index: to, t: b.start ?? 0 };
  return { kind: "seek", t: b.start ?? 0 };
}

export function nextBeat(i: number, beats: readonly Beat[] = BEATS): Step {
  return stepTo(i, Math.min(i + 1, beats.length - 1), beats);
}

export function prevBeat(i: number, beats: readonly Beat[] = BEATS): Step {
  return stepTo(i, Math.max(i - 1, 0), beats);
}

/** Layers shown: everything as soon as its data exists when Director is off (D-124). */
export function revealOf(active: boolean, i: number, beats: readonly Beat[] = BEATS): Reveal {
  if (!active) return REVEAL_ALL;
  return beats[i]?.reveal ?? REVEAL_ALL;
}

/** True when Director is on a Live watch beat that does not feature this panel (§17.10). */
export function dimmedIn(id: string, active: boolean, beat: number, page: number | null): boolean {
  if (!active || page !== null) return false;
  const b = BEATS[beat];
  return !!b && b.focus.length > 0 && !b.focus.includes(id as PanelId);
}
