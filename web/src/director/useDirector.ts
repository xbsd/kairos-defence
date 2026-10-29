// Drives Director mode from the replay clock (SPEC §17.10, D-122 to D-125): reads the stores at
// most 10 times a second, activates the beat the clock (or the presenter's page) is on, sets its
// camera shot and lens choice, and logs when each beat began. Mounted once, by App.
import { useEffect } from "react";

import { controls } from "../state/controls";
import { directorStore } from "../state/directorStore";
import { DEFAULT_CHANNEL, farthestWarp, matchStore } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { uiStore } from "../state/uiStore";
import { BEATS } from "./beats";
import { localHM } from "./captions";
import { beatAt } from "./engine";

const HZ_MS = 100;
/** How long the lens holds "Same time" before the morph to "Warped" in the time-warp beat. */
export const MORPH_HOLD_MS = 1500;

function onLive(): boolean {
  return window.location.pathname.startsWith("/live/");
}

/** "21:41:36" from the replay clock (UTC) at the installation's offset. */
function localClock(): string | null {
  const r = replayStore.getState();
  if (!r.clock || !r.hello) return null;
  const t = Date.parse(r.clock.ts);
  if (!Number.isFinite(t)) return null;
  const hm = localHM(r.clock.ts, r.hello.utc_offset_hours);
  const s = new Date(t + r.hello.utc_offset_hours * 3600_000).getUTCSeconds();
  return hm ? `${hm}:${String(s).padStart(2, "0")}` : null;
}

/** Point the lens at the top-3 match whose pace differs most (D-127). */
export function selectLensForWarp(): void {
  const m = matchStore.getState().match;
  const pick = farthestWarp(m) ?? m?.matches[0] ?? null;
  if (!pick) return;
  const st = matchStore.getState();
  if (st.lensSel?.track === pick.track_id && st.lensSel.channel === DEFAULT_CHANNEL) return;
  st.setLensSel({ track: pick.track_id, channel: DEFAULT_CHANNEL });
  controls.dtw(pick.track_id, DEFAULT_CHANNEL);
}

export function createDirectorDriver(now: () => number = () => performance.now()) {
  let seekTarget: number | null = null;
  let lensT = -1;
  let morph: ReturnType<typeof setTimeout> | null = null;

  function activate(i: number): void {
    const beat = BEATS[i];
    if (!beat) return;
    const r = replayStore.getState();
    directorStore.getState().activate(i, {
      beat: beat.id,
      t_s: beat.kind === "clock" ? (r.clock?.t_s ?? null) : null,
      local: beat.kind === "clock" ? localClock() : null,
      wall: now(),
    });
    if (beat.camera) uiStore.getState().setCamera(beat.camera);
    if (beat.id === "time-warp") {
      lensT = -1;
      matchStore.getState().setLensMode("same");
      if (morph) clearTimeout(morph);
      morph = setTimeout(() => matchStore.getState().setLensMode("warped"), MORPH_HOLD_MS);
    }
  }

  function evaluate(): void {
    const d = directorStore.getState();
    const r = replayStore.getState();
    if (d.pendingSeek !== null && r.status === "open" && r.hello && controls.connected()) {
      seekTarget = d.pendingSeek;
      controls.seek(d.pendingSeek);
      if (d.pendingPlay) controls.play();
      d.requestSeek(null);
      return;
    }
    if (!d.active) return;
    let i: number;
    if (d.page !== null) i = d.page;
    else {
      if (!onLive() || !r.clock || r.status !== "open") return;
      if (seekTarget !== null) {
        if (Math.abs(r.clock.t_s - seekTarget) > 2) return; // the seek has not landed yet
        seekTarget = null;
      }
      i = beatAt(r.clock.t_s);
    }
    if (i !== d.beat) activate(i);
    const m = matchStore.getState().match;
    if (BEATS[i]?.id === "time-warp" && m && m.t_s !== lensT) {
      lensT = m.t_s;
      selectLensForWarp();
    }
  }

  return {
    evaluate,
    dispose: () => {
      if (morph) clearTimeout(morph);
    },
  };
}

export function useDirector(): void {
  useEffect(() => {
    const driver = createDirectorDriver();
    let timer: ReturnType<typeof setTimeout> | null = null;
    let last = 0;
    const schedule = () => {
      if (timer !== null) return;
      const wait = Math.max(0, last + HZ_MS - performance.now());
      timer = setTimeout(() => {
        timer = null;
        last = performance.now();
        driver.evaluate();
      }, wait);
    };
    const unsubs = [
      replayStore.subscribe(schedule),
      matchStore.subscribe(schedule),
      directorStore.subscribe(schedule),
    ];
    schedule();
    return () => {
      unsubs.forEach((u) => u());
      if (timer !== null) clearTimeout(timer);
      driver.dispose();
    };
  }, []);
}
