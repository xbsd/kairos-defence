import { describe, expect, it } from "vitest";

import {
  aligned,
  DEFAULT_RATE,
  endMs,
  finalState,
  fusionMs,
  headline,
  landingMs,
  nextStepMs,
  RATES,
  rescale,
  SHORTLIST_MS,
  stateAt,
} from "../src/workbench/workbenchMachine";
import { workbenchStore } from "../src/workbench/workbenchStore";
import { makeTrace, SIMS } from "./workbenchFixtures";

const msg = makeTrace();
const items = aligned(msg.trace);
const tracks = (xs: { track: string }[]) => xs.map((x) => x.track);

describe("the workbench replay machine (D-189)", () => {
  it("replays the traced candidates in computed order with their columns", () => {
    expect(items.map((a) => a.order)).toEqual([0, 1, 2, 3, 6]);
    const six = items[4];
    expect(six?.track).toBe("T6");
    expect(six?.shapeSim).toBe(SIMS[6]);
    expect(six?.incident).toBe("INC-T6");
    expect(six?.m).toBe(47);
    expect(six?.vectorDistance).toBeCloseTo(0.7);
  });

  it("goes shortlist, align, fusion, done over time", () => {
    const r = DEFAULT_RATE;
    expect(stateAt(items, 0, r).stage).toBe("shortlist");
    expect(stateAt(items, SHORTLIST_MS - 1, r).stage).toBe("shortlist");
    expect(stateAt(items, SHORTLIST_MS, r).stage).toBe("align");
    expect(stateAt(items, fusionMs(items.length, r) - 1, r).stage).toBe("align");
    expect(stateAt(items, fusionMs(items.length, r), r).stage).toBe("fusion");
    expect(stateAt(items, endMs(items.length, r), r).stage).toBe("done");
    expect(stateAt(items, 0, r).current).toBeNull();
  });

  it("lands one candidate every 1 / rate seconds", () => {
    for (const r of RATES) {
      for (let i = 0; i < items.length; i++) {
        const t = landingMs(i, r);
        expect(t - SHORTLIST_MS).toBeCloseTo((i * 1000) / r);
        expect(stateAt(items, t, r).step).toBe(i + 1);
        expect(stateAt(items, t, r).current?.order).toBe(items[i]?.order);
        if (i > 0) expect(stateAt(items, t - 1, r).step).toBe(i);
      }
    }
  });

  it("re-sorts the ranking by shape similarity as each lands, ties in computed order", () => {
    const r = 6;
    const at = (i: number) => tracks(stateAt(items, landingMs(i, r), r).ranking);
    expect(at(0)).toEqual(["T0"]);
    expect(at(1)).toEqual(["T1", "T0"]);
    expect(at(2)).toEqual(["T1", "T2", "T0"]);
    expect(at(3)).toEqual(["T1", "T3", "T2", "T0"]); // T1 and T3 tie at 0.61: T1 was first
    expect(at(4)).toEqual(["T6", "T1", "T3", "T2", "T0"]);
  });

  it("changes speed without jumping the replay", () => {
    const at = landingMs(2, 3) + 100; // between the 3rd and 4th landing at 3 per second
    const s3 = stateAt(items, at, 3);
    for (const r of RATES) {
      const e = rescale(at, items.length, 3, r);
      expect(stateAt(items, e, r).step).toBe(s3.step);
    }
    expect(rescale(500, items.length, 3, 10)).toBe(500); // still in the shortlist
    const end = endMs(items.length, 3);
    expect(rescale(end, items.length, 3, 10)).toBe(endMs(items.length, 10));
    const fus = fusionMs(items.length, 3) + 200;
    expect(rescale(fus, items.length, 3, 10)).toBe(fusionMs(items.length, 10) + 200);
  });

  it("steps to the next landing, then the fusion, then the end", () => {
    const r = 6;
    const n = items.length;
    let t = 0;
    const seen: string[] = [];
    for (let k = 0; k < n + 3; k++) {
      t = nextStepMs(t, n, r);
      const s = stateAt(items, t, r);
      seen.push(`${s.stage}:${s.step}`);
    }
    expect(seen).toEqual([
      "align:1",
      "align:2",
      "align:3",
      "align:4",
      "align:5",
      "fusion:5",
      "done:5",
      "done:5",
    ]);
  });

  it("ends with every candidate aligned and the trace's fused top 5", () => {
    const f = finalState(items, DEFAULT_RATE);
    expect(f.stage).toBe("done");
    expect(f.step).toBe(items.length);
    expect(msg.trace.ranking.slice(0, 5).map((x) => x.track_id)).toEqual([
      "T6",
      "T1",
      "T3",
      "T2",
      "T0",
    ]);
  });

  it("says what it replays, from the trace's own numbers", () => {
    expect(headline(msg.trace, 6)).toBe(
      "Slow-motion replay of rerun T+90: 8 alignments computed in 23 ms; " +
        "the first 4 and 1 more of the final top 10 replayed at 6 per second",
    );
  });
});

describe("the workbench store", () => {
  it("pins the trace it opened with; reduced motion opens at the end", () => {
    const st = workbenchStore.getState();
    st.openWith(msg, "stream", false);
    expect(workbenchStore.getState()).toMatchObject({ open: true, elapsed: 0, playing: true });
    workbenchStore.getState().tick(SHORTLIST_MS + 10);
    expect(
      stateAt(workbenchStore.getState().items, workbenchStore.getState().elapsed, 6).step,
    ).toBe(1);
    workbenchStore.getState().setPlaying(false);
    const paused = workbenchStore.getState().elapsed;
    workbenchStore.getState().tick(5000);
    expect(workbenchStore.getState().elapsed).toBe(paused); // paused means paused
    workbenchStore.getState().step();
    expect(workbenchStore.getState().elapsed).toBe(landingMs(1, DEFAULT_RATE));
    expect(workbenchStore.getState().msg).toBe(msg);
    workbenchStore.getState().openWith(msg, "fetch", true);
    const s = workbenchStore.getState();
    expect(s.playing).toBe(false);
    expect(s.elapsed).toBe(endMs(s.items.length, s.rate));
    expect(stateAt(s.items, s.elapsed, s.rate).stage).toBe("done");
    s.setPlaying(true); // play at the end starts over
    expect(workbenchStore.getState().elapsed).toBe(0);
    workbenchStore.getState().tick(1e6);
    expect(workbenchStore.getState().playing).toBe(false); // stops at the end
    workbenchStore.getState().close();
    expect(workbenchStore.getState().open).toBe(false);
  });
});
