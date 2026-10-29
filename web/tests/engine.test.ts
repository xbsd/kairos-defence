import { describe, expect, it } from "vitest";

import { BEATS } from "../src/director/beats";
import {
  beatAt,
  currentBeat,
  dimmedIn,
  nextBeat,
  prevBeat,
  revealOf,
} from "../src/director/engine";

const id = (i: number) => BEATS[i]?.id;

describe("Director engine (D-122, D-123)", () => {
  it("has one beat per §1.2 row, the swarm encore last (phase 9)", () => {
    expect(BEATS.map((b) => b.id)).toEqual([
      "detection",
      "recording",
      "recognition",
      "time-warp",
      "forecast",
      "recall",
      "known",
      "evidence",
      "encore",
    ]);
    const encore = BEATS[8];
    expect(encore).toMatchObject({ kind: "page", route: "swarm", key: "swarm-ghost" });
    expect(encore?.start).toBeNull();
  });

  it("finds the clock beat for a replay second", () => {
    const want: [number, string][] = [
      [0, "detection"],
      [14.9, "detection"],
      [15, "recording"],
      [44.9, "recording"],
      [45, "recognition"],
      [89.9, "recognition"],
      [90, "time-warp"],
      [104.9, "time-warp"],
      [105, "forecast"],
      [119, "forecast"],
      [120, "recall"],
      [130, "recall"],
      [515, "recall"], // page beats never auto-advance
    ];
    for (const [t, b] of want) expect(id(beatAt(t))).toBe(b);
    expect(id(beatAt(-5))).toBe("detection");
  });

  it("steps forward and back across the clock and page boundary", () => {
    expect(nextBeat(0)).toEqual({ kind: "seek", t: 15 });
    expect(nextBeat(4)).toEqual({ kind: "seek", t: 120 });
    expect(nextBeat(5)).toEqual({ kind: "page", index: 6 });
    expect(nextBeat(6)).toEqual({ kind: "page", index: 7 });
    expect(nextBeat(7)).toEqual({ kind: "page", index: 8 }); // the encore (phase 9)
    expect(nextBeat(8)).toEqual({ kind: "none" });
    expect(prevBeat(8)).toEqual({ kind: "page", index: 7 });
    expect(prevBeat(7)).toEqual({ kind: "page", index: 6 });
    expect(prevBeat(6)).toEqual({ kind: "live", index: 5, t: 120 });
    expect(prevBeat(3)).toEqual({ kind: "seek", t: 45 });
    expect(prevBeat(0)).toEqual({ kind: "none" });
    expect(currentBeat(100, null)).toBe(3);
    expect(currentBeat(100, 6)).toBe(6);
  });

  it("reveals layers cumulatively in Director, everything without it", () => {
    expect(revealOf(false, 0)).toEqual({ ghosts: true, lens: true, forecast: true, recall: true });
    expect(revealOf(true, 2)).toEqual({
      ghosts: false,
      lens: false,
      forecast: false,
      recall: false,
    });
    expect(revealOf(true, 3)).toEqual({ ghosts: true, lens: true, forecast: false, recall: false });
    expect(revealOf(true, 4).forecast).toBe(true);
    expect(revealOf(true, 5).recall).toBe(true);
  });

  it("dims the panels a Live watch beat does not feature", () => {
    expect(dimmedIn("lens", true, 0, null)).toBe(true);
    expect(dimmedIn("stream", true, 0, null)).toBe(false);
    expect(dimmedIn("lens", false, 0, null)).toBe(false);
    expect(dimmedIn("lens", true, 6, 6)).toBe(false);
  });
});
