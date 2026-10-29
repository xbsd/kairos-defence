// Camera shots for the theater presets (§17.3). Scene meters; see sceneMath for the frame.
import type { CameraPreset } from "../state/uiStore";
import { bearingVector, type Vec3 } from "./sceneMath";

export interface Shot {
  position: Vec3;
  target: Vec3;
}

/** Overview: the fence, the 3.5 km radar ring and the core, seen from the south. */
export const OVERVIEW: Shot = { position: [300, 3100, 4500], target: [300, 0, 450] };

/** Static presets; follow and target depend on the live data. */
export const PRESETS: Record<Exclude<CameraPreset, "follow" | "target">, Shot> = {
  overview: OVERVIEW,
  memory: { position: [0, 9000, 11000], target: [0, 0, 0] }, // phase 8: frames the ghosts
  swarm: OVERVIEW, // phase 9
};

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
