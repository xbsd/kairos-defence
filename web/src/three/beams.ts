// Core beam math (SPEC §17.3, D-129): where the three beams go and how bright each point of a
// beam is as its head travels from the core.
import type { Scene } from "../api/messages";
import { matchStore } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { currentGhosts } from "./ghostLayer";
import { alignedIndex, isFenceTarget } from "./ghostMath";
import { toScene, type Origin, type Vec3 } from "./sceneMath";

export const BEAM_MS = 1200;

/** Brightness along a beam (u ∈ [0, 1] from the core) when its head is at `head`. */
export function beamGlow(u: number, head: number): number {
  if (u > head) return 0;
  return Math.exp(-(((head - u) / 0.12) ** 2)) * 0.9 + 0.15 * (1 - (head - u));
}

/** Where the three beams go: each top-3 ghost's point at the matched moment, else the target. */
export function beamTargets(scene: Scene, origin: Origin): Vec3[] {
  const m = matchStore.getState().match;
  if (!m) return [];
  const g = currentGhosts(scene);
  const out: Vec3[] = [];
  for (const x of m.matches.slice(0, 3)) {
    const spec = g.ghosts.find((s) => s.track === x.track_id);
    const w = Number(x.features["window_s"] ?? 0);
    if (spec) {
      const p = spec.points[alignedIndex(spec.points, x.window_offset_s + w)];
      if (p) {
        out.push(toScene(p.x, p.y, p.alt, origin));
        continue;
      }
    }
    const f = replayStore.getState().features;
    const tid = m.target_asset_id ?? f[f.length - 1]?.target_asset_id;
    const a = isFenceTarget(tid) ? null : scene.assets.find((s) => s.asset_id === tid);
    out.push(a ? toScene(a.centroid_x_m, a.centroid_y_m, 60, origin) : [0, 60, 0]);
  }
  return out;
}
