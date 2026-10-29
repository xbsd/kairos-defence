import { describe, expect, it } from "vitest";

import type { SwarmFlight, SwarmResponse } from "../src/api/messages";
import {
  centroidOf,
  daysBetween,
  droneAt,
  extent,
  ghostAt,
  localYmd,
  matchSecond,
  nearestEdges,
  resampleAligned,
  rowAt,
  swarmFacts,
  tableRows,
  weeksWord,
  type P3,
} from "../src/swarm/swarmMath";
import { playRange, swarmStore } from "../src/state/swarmStore";

/** A flight whose drones sit at `offsets` around a centroid moving east at `v` m/s. */
function flight(
  id: string,
  inst: string,
  region: string,
  start: string,
  n: number,
  offsets: [number, number][],
  v = 5,
): SwarmFlight {
  const t = Array.from({ length: n }, (_, i) => i);
  const nan = () => t.map(() => null);
  return {
    incident_id: id,
    installation_id: inst,
    region_id: region,
    start_ts: start,
    n_drones: offsets.length,
    track_ids: offsets.map((_, k) => `${id}-T${k + 1}`),
    is_swarm: true,
    together_s: n,
    target: { asset_id: `${inst}-hq`, kind: "hq", x_m: 0, y_m: 0 },
    curves: {
      t_s: t,
      n_drones: t.map(() => offsets.length),
      spread_m: t.map((s) => 10 + s),
      pd_q25_m: nan(),
      pd_q50_m: nan(),
      pd_q75_m: nan(),
      rot_rate_dps: nan(),
      centroid_speed_ms: t.map(() => v),
      axis_angle_deg: nan(),
      centroid_x_rel_m: t.map((s) => v * s),
      centroid_y_rel_m: t.map(() => 0),
    },
    t_s: t,
    positions: offsets.map(([dx, dy]) => t.map((s) => [v * s + dx, dy, 80])),
  };
}

const LINE: [number, number][] = [
  [-40, 0],
  [0, 0],
  [40, 0],
];
const TRI: [number, number][] = [
  [0, 30],
  [-25, -15],
  [25, -15],
];

function doc(aligned: number[]): SwarmResponse {
  const q = flight("Q", "ECHO", "PLAINS", "2026-06-15T03:50:06.000Z", 10, LINE);
  const m = flight("M", "GOLF", "DESERT", "2026-05-04T05:10:06.000Z", 20, TRI, 10);
  return {
    incident_id: "Q",
    at_s: null,
    observed_s: 9,
    model_version: "swarm-dtw-v1",
    query: q,
    matches: [
      {
        rank: 1,
        incident_id: "M",
        installation_id: "GOLF",
        region_id: "DESERT",
        start_ts: m.start_ts,
        n_drones: 3,
        duration_s: 20,
        distance: 1.1,
        similarity: 1 / 2.1,
        warp_ratio: 2,
        matched_s: 20,
      },
    ],
    match: m,
    match_rank: 1,
    aligned,
    path: aligned.map((j, i) => [i, j]),
    elapsed_ms: 1,
  };
}

describe("swarm math (§14, §17.9)", () => {
  it("interpolates a drone only between two recorded seconds", () => {
    const track = [
      [0, 0, 10],
      [10, 0, 20],
      [null, null, null],
      [30, 0, 40],
    ];
    expect(droneAt(track, 0.5)).toEqual([5, 0, 15]);
    expect(droneAt(track, 1)).toEqual([10, 0, 20]);
    expect(droneAt(track, 1.2)).toEqual([10, 0, 20]); // next second missing: nearest real one
    expect(droneAt(track, 1.8)).toBeNull();
    expect(droneAt(track, -1)).toBeNull();
    expect(droneAt(track, 9)).toBeNull();
  });

  it("finds formation edges to each drone's nearest neighbor, unique pairs", () => {
    const pts: (P3 | null)[] = [[0, 0, 0], [10, 0, 0], [100, 0, 0], null, [104, 3, 0]];
    expect(nearestEdges(pts)).toEqual([
      [0, 1],
      [2, 4],
    ]);
    expect(nearestEdges([[0, 0, 0]])).toEqual([]);
    expect(centroidOf([[0, 0, 0], null, [10, 20, 30]])).toEqual([5, 10, 15]);
    expect(centroidOf([null])).toBeNull();
  });

  it("looks up rows and the DTW-aligned matched second", () => {
    expect(rowAt([2, 3, 5, 9], 1)).toBe(-1);
    expect(rowAt([2, 3, 5, 9], 5)).toBe(2);
    expect(rowAt([2, 3, 5, 9], 8.9)).toBe(2);
    expect(rowAt([2, 3, 5, 9], 99)).toBe(3);
    const d = doc([0, 2, 4, 6, 8, 10, 12, 14, 16, 18]);
    expect(matchSecond(d, 3)).toBe(6);
    expect(matchSecond(d, 3.5)).toBe(7); // linear between aligned rows
    expect(matchSecond(d, 9)).toBe(18);
    expect(matchSecond({ ...d, match: null }, 3)).toBeNull();
  });

  it("re-centers the matched formation on tonight's centroid (the ghost)", () => {
    const d = doc([0, 2, 4, 6, 8, 10, 12, 14, 16, 18]);
    const g = ghostAt(d, 4) as P3[];
    const c = centroidOf(g) as P3;
    const tonight = centroidOf(d.query.positions.map((p) => p[4] as unknown as P3)) as P3;
    expect(c[0]).toBeCloseTo(tonight[0]);
    expect(c[1]).toBeCloseTo(tonight[1]);
    // the matched triangle keeps its shape: apex 30 m north of its centroid
    expect((g[0] as P3)[1] - c[1]).toBeCloseTo(30 - (30 - 15 - 15) / 3);
    expect(ghostAt({ ...d, match: null }, 4)).toEqual([]);
  });

  it("resamples the match onto tonight's rows and takes extents", () => {
    expect(resampleAligned([5, 6, 7, null], [0, 0, 2, 3, 9])).toEqual([5, 5, 7, null, null]);
    expect(extent([3, null, 9], [1])).toEqual([1, 9]);
    expect(extent([null])).toEqual([0, 1]);
    expect(extent([4, 4])).toEqual([3, 5]);
  });

  it("computes the encore facts from the dates, bases and regions", () => {
    expect(localYmd("2026-06-15T03:50:06Z", -5)).toBe("2026-06-14");
    expect(daysBetween("2026-05-03", "2026-06-14")).toBe(42);
    expect(weeksWord(6)).toBe("six weeks");
    expect(weeksWord(1)).toBe("one week");
    expect(weeksWord(14)).toBe("14 weeks");
    const f = swarmFacts(doc([0]), { ECHO: -5, GOLF: -7 });
    expect(f).toEqual({
      queryBase: "Echo",
      queryDay: "Jun 14",
      matchBase: "Golf",
      matchDay: "May 3",
      weeks: 6,
      otherRegion: true,
      sameBase: false,
    });
    expect(swarmFacts(doc([0]), { ECHO: -5 })).toBeNull(); // no offset, no caption fact
    expect(swarmFacts({ ...doc([0]), match: null }, { ECHO: -5, GOLF: -7 })).toBeNull();
  });

  it("keeps table rows every 30 s and the playhead inside the described seconds", () => {
    const d = doc([0]);
    expect(tableRows(d, 3)).toEqual([0, 3, 6, 9]);
    expect(playRange(d)).toEqual([0, 9]);
    swarmStore.getState().setDoc(d);
    swarmStore.getState().setPlayhead(50);
    expect(swarmStore.getState().playhead).toBe(9);
    swarmStore.getState().play(); // from the end it starts over
    expect(swarmStore.getState().playhead).toBe(0);
    swarmStore.getState().setSpeed(5);
    swarmStore.getState().tick(1);
    expect(swarmStore.getState().playhead).toBe(5);
    swarmStore.getState().tick(10);
    expect(swarmStore.getState()).toMatchObject({ playhead: 9, playing: false });
  });
});
