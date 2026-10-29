import { describe, expect, it } from "vitest";

import {
  connectorAt,
  costRange,
  decodeCost,
  lensScale,
  morphConnectors,
  paceWords,
  pathCells,
  sameTimeConnectors,
  warpedConnectors,
  type Pair,
} from "../src/lens/lensMath";
import { T090 } from "./real";

/** Float32 little-endian base64, as match/lens.encode_f32 writes it. */
function encode(values: number[]): string {
  const view = new DataView(new ArrayBuffer(values.length * 4));
  values.forEach((v, i) => view.setFloat32(i * 4, v, true));
  let bin = "";
  for (let i = 0; i < view.byteLength; i++) bin += String.fromCharCode(view.getUint8(i));
  return btoa(bin);
}

describe("lens math (SPEC §17.7)", () => {
  it("decodes the float32 cost matrix, NaN outside the band", () => {
    const v = decodeCost(encode([1, 2.5, Number.NaN, 4, 5, 6]), [2, 3]);
    expect(Array.from(v.slice(0, 2))).toEqual([1, 2.5]);
    expect(Number.isNaN(v[2])).toBe(true);
    expect(v[5]).toBe(6);
    expect(() => decodeCost(encode([1, 2]), [2, 3])).toThrow();
  });

  it("decodes the real T+90 payload to its shape, the last cell being the DTW distance", () => {
    const d = T090.dtw;
    const [n, m] = d.shape;
    const v = decodeCost(d.cost, [n, m]);
    expect(v.length).toBe(n * m);
    expect(v[n * m - 1]).toBeCloseTo(d.dtw_distance, 1);
    const [lo, hi] = costRange(v);
    expect(hi).toBeGreaterThan(lo);
  });

  it("pairs equal indices in same-time mode", () => {
    expect(sameTimeConnectors(4, 6, 4)).toEqual([
      [0, 0],
      [1, 1],
      [2, 2],
      [3, 3],
    ]);
    expect(sameTimeConnectors(6, 3, 3)).toHaveLength(3);
  });

  it("subsamples the warped path, keeping the first and last pairs", () => {
    const path = T090.dtw.path as Pair[];
    const w = warpedConnectors(path);
    expect(w.length).toBeLessThanOrEqual(48);
    expect(w[0]).toEqual(path[0]);
    expect(w[w.length - 1]).toEqual(path[path.length - 1]);
    const keys = new Set(path.map((p) => p.join(",")));
    for (const p of w) expect(keys.has(p.join(","))).toBe(true);
    expect(
      warpedConnectors([
        [0, 0],
        [1, 2],
      ]),
    ).toEqual([
      [0, 0],
      [1, 2],
    ]);
  });

  it("morphs only the candidate end: same time at 0, the DTW path at 1", () => {
    const d = T090.dtw;
    const cs = morphConnectors(d.path as Pair[], d.overlap);
    const at0 = connectorAt(cs, 0);
    const at1 = connectorAt(cs, 1);
    const want = warpedConnectors(d.path as Pair[]);
    expect(at1).toEqual(want.map(([i, j]) => [i, j]));
    expect(at0).toEqual(want.map(([i]) => [i, i]));
    const mid = connectorAt(cs, 0.5);
    mid.forEach(([i], k) => expect(i).toBe(want[k]?.[0]));
    expect(cs.every((c) => c.same === c.i < d.overlap)).toBe(true);
  });

  it("puts both series on one time scale", () => {
    const x = lensScale(60, 120, 400, 10);
    expect(x(0)).toBe(10);
    expect(x(119)).toBeCloseTo(390);
    // sample 59 of tonight and sample 59 of the past flight share an x: the overhang shows pace
    expect(x(59)).toBeCloseTo(10 + (59 / 119) * 380);
  });

  it("maps path pairs to matrix cells one to one", () => {
    expect(
      pathCells([
        [0, 0],
        [3, 7],
      ]),
    ).toEqual([
      [0.5, 0.5],
      [7.5, 3.5],
    ]);
  });

  it("writes the pace in the matcher's words", () => {
    expect(paceWords("flown 19% faster")).toBe("Flown 19% faster");
    expect(paceWords(null)).toBe("Same pace (within 10%)");
    expect(paceWords(T090.dtw.warp_text)).toBe("Flown 19% faster");
  });
});
