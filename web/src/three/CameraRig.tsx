import { CameraControls } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import type { PerspectiveCamera } from "three";

import type { Scene } from "../api/messages";
import { useThrottledStore } from "../lib/useThrottledStore";
import { matchStore } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { followShot, forecastShot, frameBox, PRESETS, targetShot, type Shot } from "./camera";
import { isFenceTarget } from "./ghostMath";
import { currentGhosts, ghostsKey } from "./ghostLayer";
import { toScene, type Origin, type Vec3 } from "./sceneMath";

function targetAt(
  scene: Scene | null,
  origin: Origin,
  assetId: string | null | undefined,
): Vec3 | null {
  if (!scene || isFenceTarget(assetId)) return null;
  const a = scene.assets.find((x) => x.asset_id === assetId);
  return a ? toScene(a.centroid_x_m, a.centroid_y_m, 0, origin) : null;
}

/** The memory shot: every ghost point (sampled) and tonight's target (D-134). */
function memoryShot(scene: Scene | null, origin: Origin, fov: number, aspect: number): Shot | null {
  if (!scene) return null;
  const g = currentGhosts(scene);
  if (!g.ghosts.length) return null;
  const pts: Vec3[] = [];
  for (const s of g.ghosts)
    for (let i = 0; i < s.points.length; i += 5) {
      const p = s.points[i];
      if (p) pts.push(toScene(p.x, p.y, p.alt, origin));
    }
  const t = targetAt(scene, origin, matchStore.getState().match?.target_asset_id);
  if (t) pts.push(t);
  return frameBox(pts, fov, aspect, 50, 1.1);
}

function forecastFrame(
  scene: Scene | null,
  origin: Origin,
  fov: number,
  aspect: number,
): Shot | null {
  const f = matchStore.getState().forecast;
  if (!f || !scene) return null;
  const t = targetAt(scene, origin, f.target_asset_id) ?? [0, 0, 0];
  const c = toScene(f.center_x_m, f.center_y_m, 0, origin);
  const path = f.path.filter((_, i) => i % 6 === 0).map(([x, y]) => toScene(x, y, 25, origin));
  return forecastShot(t, c, f.radius_m, path, fov, aspect);
}

function forecastKey(f: { center_x_m: number; center_y_m: number; radius_m: number } | null) {
  if (!f) return "";
  return [f.center_x_m / 100, f.center_y_m / 100, f.radius_m / 50].map(Math.round).join(",");
}

/**
 * Camera presets with 1.2 s damped transitions (instant in reduce motion) and free orbit
 * otherwise (§17.3). Follow tracks the latest real detection; target frames the identified
 * asset; memory frames the ghosts and forecast the orbit, zone and road, both recomputed when
 * their data changes (D-134).
 */
export function CameraRig({ scene, origin }: { scene: Scene | null; origin: Origin | null }) {
  const ref = useRef<CameraControls>(null);
  const first = useRef(true);
  const aimedKey = useRef<string>("");
  const preset = useThrottledStore(uiStore, (s) => s.camera, 10);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    c.smoothTime = 0.35; // ≈ 1.2 s to settle
    const smooth = !first.current && !reduceMotion(uiStore.getState());
    first.current = false;
    aimedKey.current = "";
    if (preset === "follow" || preset === "target" || preset === "memory" || preset === "forecast")
      return; // from the live data, below
    const s = PRESETS[preset];
    void c.setLookAt(...s.position, ...s.target, smooth);
  }, [preset]);

  useFrame(({ camera, size }) => {
    const c = ref.current;
    if (!c || !origin) return;
    const smooth = !reduceMotion(uiStore.getState());
    const s = replayStore.getState();
    const f = s.features[s.features.length - 1];
    if (preset === "memory" || preset === "forecast") {
      const ms = matchStore.getState();
      const key =
        preset === "memory"
          ? `m:${ghostsKey()}:${size.width}x${size.height}`
          : // re-aim only when the zone moves by about 100 m (not on every 5 s rerun)
            `f:${forecastKey(ms.forecast)}:${size.width}x${size.height}`;
      if (key === aimedKey.current) return;
      aimedKey.current = key; // once per change of the data (or the viewport)
      const fov = (camera as PerspectiveCamera).fov ?? 45;
      const aspect = size.width / Math.max(1, size.height);
      const shot =
        preset === "memory"
          ? memoryShot(scene, origin, fov, aspect)
          : forecastFrame(scene, origin, fov, aspect);
      const use = shot ?? PRESETS[preset];
      void c.setLookAt(...use.position, ...use.target, smooth);
      return;
    }
    if (preset !== "follow" && preset !== "target") return;
    if (preset === "follow") {
      const id = s.hello?.tracks[0];
      const pts = id ? s.tracks[id] : undefined;
      const last = pts?.[pts.length - 1];
      if (!last) return;
      const shot = followShot(toScene(last.x, last.y, last.alt, origin), f?.heading_deg ?? null);
      void c.setLookAt(...shot.position, ...shot.target, smooth);
      return;
    }
    const at = targetAt(scene, origin, f?.target_asset_id) ?? ([0, 0, 0] as Vec3);
    const shot = targetShot(at);
    void c.setLookAt(...shot.position, ...shot.target, smooth);
  });

  return (
    <CameraControls
      ref={ref}
      makeDefault
      minDistance={80}
      maxDistance={16000}
      maxPolarAngle={(84 * Math.PI) / 180}
      dollySpeed={0.6}
    />
  );
}
