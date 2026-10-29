import { PerspectiveCamera, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import { forecastShot, frameBox } from "../src/three/camera";
import type { Vec3 } from "../src/three/sceneMath";

function inFrustum(shot: { position: Vec3; target: Vec3 }, pts: Vec3[], aspect: number): boolean {
  const cam = new PerspectiveCamera(45, aspect, 5, 100000);
  cam.position.set(...shot.position);
  cam.lookAt(new Vector3(...shot.target));
  cam.updateMatrixWorld();
  return pts.every((p) => {
    const v = new Vector3(...p).project(cam);
    return Math.abs(v.x) <= 1 && Math.abs(v.y) <= 1 && v.z < 1;
  });
}

describe("computed camera shots (D-134)", () => {
  const ghosts: Vec3[] = [
    [-2500, 100, -1200],
    [800, 60, 400],
    [-1800, 120, 900],
    [300, 30, -2200],
  ];

  it("frameBox keeps every point inside the frustum at both aspect ratios", () => {
    for (const aspect of [16 / 9, 1.1]) {
      const shot = frameBox(ghosts, 45, aspect);
      if (!shot) throw new Error("no shot");
      expect(inFrustum(shot, ghosts, aspect)).toBe(true);
    }
    expect(frameBox([], 45, 1)).toBeNull();
  });

  it("forecastShot frames the target, the zone's edge and the path", () => {
    const target: Vec3 = [650, 0, -170];
    const zone: Vec3 = [-750, 0, -1820];
    const path: Vec3[] = [
      [400, 25, -400],
      [-600, 25, -1600],
    ];
    const shot = forecastShot(target, zone, 370, path, 45, 16 / 9);
    if (!shot) throw new Error("no shot");
    const edge: Vec3[] = [
      [zone[0] + 370, 0, zone[2]],
      [zone[0] - 370, 0, zone[2]],
      [zone[0], 0, zone[2] - 370],
    ];
    expect(inFrustum(shot, [target, ...edge, ...path], 16 / 9)).toBe(true);
  });
});
