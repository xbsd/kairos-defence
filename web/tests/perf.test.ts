import { describe, expect, it } from "vitest";

import { PERF_START, perfLabel, stepPerf, type PerfState } from "../src/three/perf";

function run(s: PerfState, frameMs: number, seconds: number, t0: number): [PerfState, number] {
  let st = s;
  let t = t0;
  const n = Math.round((seconds * 1000) / frameMs);
  for (let i = 0; i < n; i++) {
    t += frameMs / 1000;
    st = stepPerf(st, frameMs, t);
  }
  return [st, t];
}

describe("auto-degrade (§17.11)", () => {
  it("drops bloom after 2 s above 25 ms, then halves packets after 2 more", () => {
    let [s, t] = run(PERF_START, 16, 3, 0);
    expect(s.level).toBe(0);
    [s, t] = run(s, 34, 1.5, t);
    expect(s.level).toBe(0);
    [s, t] = run(s, 34, 1.2, t);
    expect(s.level).toBe(1);
    [s, t] = run(s, 34, 2.2, t);
    expect(s.level).toBe(2);
    [s] = run(s, 34, 5, t);
    expect(s.level).toBe(2); // never beyond level 2
  });

  it("does not degrade on short spikes", () => {
    let s = PERF_START;
    let t = 0;
    for (let i = 0; i < 20; i++) {
      [s, t] = run(s, 16, 0.5, t);
      t += 0.12;
      s = stepPerf(s, 120, t); // one 120 ms hitch every half second
    }
    expect(s.level).toBe(0);
  });

  it("restarts the window when frames recover", () => {
    let [s, t] = run(PERF_START, 34, 1.8, 0);
    [s, t] = run(s, 16, 1, t);
    [s] = run(s, 34, 1.8, t);
    expect(s.level).toBe(0);
  });

  it("labels the level for data-perf", () => {
    expect(perfLabel(0, false)).toBe("full");
    expect(perfLabel(1, false)).toBe("no-bloom");
    expect(perfLabel(2, false)).toBe("half-packets");
    expect(perfLabel(0, true)).toBe("reduced");
  });
});
