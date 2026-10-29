// Camera shots for the theater presets (§17.3). Scene meters; see sceneMath for the frame.
import type { CameraPreset } from "../state/uiStore";
import { bearingVector, type Vec3 } from "./sceneMath";

export interface Shot {
  position: Vec3;
  target: Vec3;
}

/** Overview: the fence, the 3.5 km radar ring and the core, seen from the south. */
export const OVERVIEW: Shot = { position: [300, 3100, 4500], target: [300, 0, 450] };

/** Static presets; follow, target, memory and forecast depend on the live data. */
export const PRESETS: Record<Exclude<CameraPreset, "follow" | "target">, Shot> = {
  overview: OVERVIEW,
  memory: { position: [0, 9000, 11000], target: [0, 0, 0] }, // until the ghosts are known
  forecast: OVERVIEW, // until the forecast is known
  swarm: OVERVIEW, // phase 9
};

/**
 * A shot that frames every point (scene meters): the bounding sphere seen from the south at
 * `elevationDeg`, far enough that the sphere fits the narrower of the two fields of view, with a
 * `margin` (D-134).
 */
export function frameBox(
  points: Vec3[],
  fovDeg: number,
  aspect: number,
  elevationDeg = 52,
  margin = 1.15,
): Shot | null {
  if (!points.length) return null;
  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  for (const p of points)
    for (let k = 0; k < 3; k++) {
      lo[k] = Math.min(lo[k] as number, p[k] as number);
      hi[k] = Math.max(hi[k] as number, p[k] as number);
    }
  const c: Vec3 = [
    ((lo[0] as number) + (hi[0] as number)) / 2,
    ((lo[1] as number) + (hi[1] as number)) / 2,
    ((lo[2] as number) + (hi[2] as number)) / 2,
  ];
  let r = 1;
  for (const p of points) r = Math.max(r, Math.hypot(p[0] - c[0], p[1] - c[1], p[2] - c[2]));
  const vfov = (fovDeg * Math.PI) / 180;
  const hfov = 2 * Math.atan(Math.tan(vfov / 2) * aspect);
  const half = Math.min(vfov, hfov) / 2;
  const dist = (margin * r) / Math.sin(half);
  const el = (elevationDeg * Math.PI) / 180;
  return {
    position: [c[0], c[1] + dist * Math.sin(el), c[2] + dist * Math.cos(el)],
    target: c,
  };
}

/**
 * The forecast shot: the orbit (tonight's target), the recovery zone and its road (D-134). The
 * framed content sits right of center and a little high, so the report recall overlay at the
 * theater's lower left never covers the zone or the road its beam points to.
 */
export function forecastShot(
  target: Vec3,
  zoneCenter: Vec3,
  zoneRadius: number,
  extra: Vec3[],
  fovDeg: number,
  aspect: number,
): Shot | null {
  const ring: Vec3[] = [0, 1, 2, 3].map((k) => {
    const a = (k * Math.PI) / 2;
    return [zoneCenter[0] + zoneRadius * Math.cos(a), 0, zoneCenter[2] + zoneRadius * Math.sin(a)];
  });
  const shot = frameBox([target, ...ring, ...extra], fovDeg, aspect, 55, 1.55);
  if (!shot) return null;
  const dist = Math.hypot(
    shot.position[0] - shot.target[0],
    shot.position[1] - shot.target[1],
    shot.position[2] - shot.target[2],
  );
  const halfH = dist * Math.tan((fovDeg * Math.PI) / 360);
  const dx = -0.32 * halfH * aspect; // camera left: the content moves right on screen
  const dz = 0.22 * halfH; // camera back (south): the content rises
  return {
    position: [shot.position[0] + dx, shot.position[1], shot.position[2] + dz],
    target: [shot.target[0] + dx, shot.target[1], shot.target[2] + dz],
  };
}

export const FOLLOW_BACK_M = 400;
export const FOLLOW_UP_M = 180;
export const TARGET_M = 900;

/** Chase shot: 400 m behind the drone along its heading, a little above. */
export function followShot(drone: Vec3, headingDeg: number | null): Shot {
  const d = bearingVector(headingDeg ?? 0);
  return {
    position: [
      drone[0] - FOLLOW_BACK_M * d[0],
      drone[1] + FOLLOW_UP_M,
      drone[2] - FOLLOW_BACK_M * d[2],
    ],
    target: drone,
  };
}

/** Target shot: 900 m from the target asset, from the south at about 35° elevation. */
export function targetShot(at: Vec3): Shot {
  const el = (35 * Math.PI) / 180;
  return {
    position: [at[0], TARGET_M * Math.sin(el), at[2] + TARGET_M * Math.cos(el)],
    target: [at[0], 0, at[2]],
  };
}
