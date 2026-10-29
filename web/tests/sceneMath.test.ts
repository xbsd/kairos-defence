import { describe, expect, it } from "vitest";

import { followShot, targetShot } from "../src/three/camera";
import {
  arcPoint,
  bearingDeg,
  bearingVector,
  CORE_POSITION,
  hatchSegments,
  PACKET_LEG1_S,
  PACKET_LEG2_S,
  packetPosition,
  quatrefoil,
  rfRingRadius,
  screenScale,
  sweepAngleDeg,
  toScene,
  trailAlpha,
  type Vec3,
} from "../src/three/sceneMath";

const O = { x: 22000, y: -6000 };

describe("toScene", () => {
  it("puts the installation origin at 0 and maps y_m to −z, altitude to y", () => {
    expect(toScene(22000, -6000, 0, O)).toEqual([0, 0, -0]);
    expect(toScene(22100, -5900, 90, O)).toEqual([100, 90, -100]); // north-east is −z
    expect(toScene(21900, -6200, 5, O)).toEqual([-100, 5, 200]);
  });
});

describe("bearings", () => {
  it("is clockwise from north", () => {
    expect(bearingDeg([0, 0], [0, 10])).toBeCloseTo(0);
    expect(bearingDeg([0, 0], [10, 0])).toBeCloseTo(90);
    expect(bearingDeg([0, 0], [0, -10])).toBeCloseTo(180);
    expect(bearingDeg([0, 0], [-10, 0])).toBeCloseTo(270);
    const v = bearingVector(90);
    expect(v[0]).toBeCloseTo(1);
    expect(v[2]).toBeCloseTo(0);
    expect(bearingVector(0)[2]).toBeCloseTo(-1); // north is −z
  });
});

describe("sweepAngleDeg", () => {
  it("equals the detection's bearing at the detection time", () => {
    expect(sweepAngleDeg(334.9, 1, 12, 12)).toBeCloseTo(334.9);
  });
  it("advances 360° × rate per replay second and stands still when the clock does", () => {
    expect(sweepAngleDeg(10, 1, 12.25, 12)).toBeCloseTo(100);
    expect(sweepAngleDeg(10, 0.5, 12.5, 12)).toBeCloseTo(100);
    expect(sweepAngleDeg(10, 1, 13, 12)).toBeCloseTo(10); // back on the drone a second later
    expect(sweepAngleDeg(10, 1, 11, 12)).toBeCloseTo(10); // never before the detection
  });
});

describe("packets", () => {
  const drone: Vec3 = [-300, 90, -1100];
  const sensor: Vec3 = [226, 4, -105];
  it("arc endpoints are the two ends", () => {
    expect(arcPoint(drone, sensor, 0, 50)).toEqual(drone);
    const end = arcPoint(drone, sensor, 1, 50);
    end.forEach((v, i) => expect(v).toBeCloseTo(sensor[i] as number));
    expect(arcPoint(drone, sensor, 0.5, 50)[1]).toBeGreaterThan(90); // curved, above the chord
  });
  it("travels drone → sensor in 0.9 s, then sensor → core in 0.6 s", () => {
    expect(packetPosition(drone, sensor, CORE_POSITION, 0)).toEqual(drone);
    const atSensor = packetPosition(drone, sensor, CORE_POSITION, PACKET_LEG1_S) as Vec3;
    atSensor.forEach((v, i) => expect(v).toBeCloseTo(sensor[i] as number));
    const atCore = packetPosition(
      drone,
      sensor,
      CORE_POSITION,
      PACKET_LEG1_S + PACKET_LEG2_S,
    ) as Vec3;
    atCore.forEach((v, i) => expect(v).toBeCloseTo(CORE_POSITION[i] as number));
    expect(packetPosition(drone, sensor, CORE_POSITION, 1.6)).toBeNull();
    expect(packetPosition(drone, sensor, CORE_POSITION, -0.1)).toBeNull();
  });
  it("puts the core 2.4 km south-east at 120 m", () => {
    expect(Math.hypot(CORE_POSITION[0], CORE_POSITION[2])).toBeCloseTo(2400);
    expect(CORE_POSITION[1]).toBe(120);
    expect(bearingDeg([0, 0], [CORE_POSITION[0], -CORE_POSITION[2]])).toBeCloseTo(135);
  });
});

describe("trail and rings", () => {
  it("trail alpha goes 1 → 0 over 60 s", () => {
    expect(trailAlpha(0)).toBe(1);
    expect(trailAlpha(30)).toBeCloseTo(0.5);
    expect(trailAlpha(60)).toBe(0);
    expect(trailAlpha(90)).toBe(0);
    expect(trailAlpha(-1)).toBe(1);
  });
  it("RF ring grows 0 → 300 m over 1.2 s", () => {
    expect(rfRingRadius(0)).toBe(0);
    expect(rfRingRadius(0.6)).toBeCloseTo(150);
    expect(rfRingRadius(1.2)).toBeCloseTo(300);
    expect(rfRingRadius(1.3)).toBeNull();
  });
});

describe("quatrefoil", () => {
  it("is closed and symmetric under quarter turns and mirroring", () => {
    const n = 96;
    const q = quatrefoil(n, 1);
    expect(q[0]?.[0]).toBeCloseTo(q[n]?.[0] as number);
    expect(q[0]?.[1]).toBeCloseTo(q[n]?.[1] as number);
    const r = q.map(([x, y]) => Math.hypot(x, y));
    for (let i = 0; i < n; i++) {
      expect(r[i]).toBeCloseTo(r[(i + n / 4) % n] as number); // 90° symmetry
      expect(r[i]).toBeCloseTo(r[(n - i) % n] as number); // mirror
    }
    expect(Math.max(...r)).toBeCloseTo(1);
  });
});

describe("helpers", () => {
  it("screenScale gives the world size of a pixel height", () => {
    // at 1000 m with a 90° fov and 1000 px, 1 px is 2 m
    expect(screenScale(1000, 90, 1000, 1)).toBeCloseTo(2);
  });
  it("hatches a square with evenly spaced segments inside it", () => {
    const sq: [number, number][] = [
      [0, 0],
      [100, 0],
      [100, 100],
      [0, 100],
      [0, 0],
    ];
    const segs = hatchSegments(sq, 10, 0);
    expect(segs.length).toBe(10);
    for (const [a, b] of segs) {
      for (const p of [a, b]) {
        expect(p[0]).toBeGreaterThanOrEqual(-1e-9);
        expect(p[0]).toBeLessThanOrEqual(100 + 1e-9);
      }
      expect(a[1]).toBeCloseTo(b[1]);
    }
  });
  it("camera shots: follow sits 400 m behind the heading, target 900 m from the asset", () => {
    const f = followShot([0, 90, 0], 90); // flying east
    expect(f.position[0]).toBeCloseTo(-400);
    expect(f.position[1]).toBeCloseTo(270);
    const t = targetShot([650, 0, -170]);
    const d = Math.hypot(t.position[0] - 650, t.position[1], t.position[2] + 170);
    expect(d).toBeCloseTo(900);
  });
});
