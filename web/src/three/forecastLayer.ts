// Shared forecast state for the theater layers (the zone, the in-zone road and its midpoint):
// computed from the `forecast` message and the scene, region meters (§13, §17.3, D-132).
import type { ForecastMsg, Scene } from "../api/messages";
import { forecastPlace } from "../director/captions";
import { clipPolylineToCircle, midpointAlong, roughDistance } from "./forecastMath";
import type { Vec2 } from "./sceneMath";

export interface ZoneRoad {
  name: string;
  parts: Vec2[][];
  /** Midpoint of the longest in-zone part (where the recall beam lands). */
  mid: Vec2 | null;
}

export function zoneRoads(f: ForecastMsg | null, scene: Scene | null): ZoneRoad[] {
  if (!f || !scene) return [];
  const c: Vec2 = [f.center_x_m, f.center_y_m];
  return scene.roads
    .filter((r) => f.roads.includes(r.name))
    .map((r) => {
      const parts = r.lines.flatMap((l) => clipPolylineToCircle(l as Vec2[], c, f.radius_m));
      let best: Vec2[] | null = null;
      let bestLen = -1;
      for (const p of parts) {
        let len = 0;
        for (let i = 1; i < p.length; i++)
          len += Math.hypot(
            (p[i] as Vec2)[0] - (p[i - 1] as Vec2)[0],
            (p[i] as Vec2)[1] - (p[i - 1] as Vec2)[1],
          );
        if (len > bestLen) {
          bestLen = len;
          best = p;
        }
      }
      return { name: r.name, parts, mid: best ? midpointAlong(best) : null };
    })
    .filter((r) => r.parts.length > 0);
}

/** "Predicted recovery zone, 2.2 km northwest, from 3 matches" (computed values, §17.3). */
export function zoneLabel(f: ForecastMsg | null, scene: Scene | null): string | null {
  if (!f) return null;
  const n = f.analogs.length;
  const from = n ? `, from ${n} match${n === 1 ? "" : "es"}` : "";
  const p = forecastPlace(f, scene);
  if (!p) return `Predicted recovery zone${from}`;
  return `Predicted recovery zone, ${roughDistance(p.distance)} ${p.word}${from}`;
}
