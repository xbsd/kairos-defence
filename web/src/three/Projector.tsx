import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import { Vector3 } from "three";

import type { ForecastMsg, Scene } from "../api/messages";
import { revealOf } from "../director/engine";
import { directorStore } from "../state/directorStore";
import { matchStore } from "../state/matchStore";
import { overlayStore } from "../state/overlayStore";
import { zoneRoads } from "./forecastLayer";
import { toScene, type Origin } from "./sceneMath";

const v = new Vector3();

/**
 * Projects the in-zone road segment's midpoint to the screen every frame for the recall beam
 * (§17.8, D-132), writing into overlayStore by mutation (no React state, no notifications).
 */
export function Projector({ scene, origin }: { scene: Scene; origin: Origin }) {
  const seen = useRef<ForecastMsg | null | undefined>(undefined);
  const mid = useRef<[number, number] | null>(null);
  useFrame(({ camera, size }) => {
    const o = overlayStore.getState();
    const road = o.road;
    const f = matchStore.getState().forecast;
    const d = directorStore.getState();
    if (f !== seen.current) {
      seen.current = f;
      const z = zoneRoads(f, scene).find((r) => r.mid);
      mid.current = z?.mid ?? null;
      const name = z?.name ?? null;
      if (name !== o.roadName) o.setRoad(road, name);
    }
    const m = mid.current;
    if (!m || !revealOf(d.active, d.beat).recall) {
      road.on = false;
      return;
    }
    const p = toScene(m[0], m[1], 1.5, origin);
    v.set(p[0], p[1], p[2]).project(camera);
    road.x = ((v.x + 1) / 2) * size.width;
    road.y = ((1 - v.y) / 2) * size.height;
    road.on =
      v.z > -1 &&
      v.z < 1 &&
      road.x >= 0 &&
      road.x <= size.width &&
      road.y >= 0 &&
      road.y <= size.height;
  });
  return null;
}
