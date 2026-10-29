import { describe, expect, it } from "vitest";

import { beamGlow } from "../src/three/beams";
import {
  alignedIndex,
  dissolveAlpha,
  isFenceTarget,
  mapGhost,
  segmentHash,
  STAGGER_MS,
} from "../src/three/ghostMath";
import { HISTORY } from "./real";

describe("ghost mapping (D-128)", () => {
  it("places the target-relative path at tonight's target centroid (translation only)", () => {
    const pts = mapGhost(
      {
        ...HISTORY,
        points: [
          [0, 10, -20, 50],
          [1, null, 5, 60],
          [2, -100, 200, null],
        ],
      },
      [22649, -5831],
    );
    expect(pts).toEqual([
      { t: 0, x: 22659, y: -5851, alt: 50 },
      { t: 2, x: 22549, y: -5631, alt: 0 },
    ]);
  });

  it("maps the real DELTA flight point by point", () => {
    const pts = mapGhost(HISTORY, [0, 0]);
    const first = HISTORY.points.find((p) => p[1] !== null && p[2] !== null);
    expect(pts[0]?.x).toBe(first?.[1]);
    expect(pts.length).toBeGreaterThan(100);
  });

  it("draws no ghost while tonight's target is the fence pseudo-target", () => {
    expect(isFenceTarget("BRAVO-fence")).toBe(true);
    expect(isFenceTarget(null)).toBe(true);
    expect(isFenceTarget("BRAVO-fuel_farm")).toBe(false);
  });

  it("clamps the aligned index", () => {
    const pts = [0, 1, 2, 3].map((t) => ({ t, x: 0, y: 0, alt: 0 }));
    expect(alignedIndex(pts, 2.5)).toBe(2);
    expect(alignedIndex(pts, -5)).toBe(0);
    expect(alignedIndex(pts, 99)).toBe(3);
    expect(alignedIndex([], 1)).toBe(-1);
  });

  it("dissolves deterministically, staggered per ghost, fully in after 1.2 s", () => {
    expect(segmentHash(3)).toBe(segmentHash(3));
    expect(dissolveAlpha(5, 0, 0)).toBe(0);
    expect(dissolveAlpha(5, 0, 1200)).toBe(1);
    expect(dissolveAlpha(5, 2, 250)).toBe(0); // the third ghost starts 300 ms later
    expect(dissolveAlpha(5, 2, 1200 + 2 * STAGGER_MS)).toBe(1);
    const mid = Array.from({ length: 50 }, (_, k) => dissolveAlpha(k, 0, 600));
    expect(new Set(mid).size).toBeGreaterThan(2); // a dissolve, not a uniform fade
  });

  it("lights a core beam only behind its head", () => {
    expect(beamGlow(0.8, 0.5)).toBe(0);
    expect(beamGlow(0.5, 0.5)).toBeGreaterThan(beamGlow(0.2, 0.5));
  });
});
