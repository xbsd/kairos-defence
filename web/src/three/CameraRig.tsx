import { CameraControls } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useEffect, useRef } from "react";

import type { Scene } from "../api/messages";
import { useThrottledStore } from "../lib/useThrottledStore";
import { replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { followShot, PRESETS, targetShot } from "./camera";
import { toScene, type Origin, type Vec3 } from "./sceneMath";

/**
 * Camera presets with 1.2 s damped transitions (instant in reduce motion) and free orbit
 * otherwise (§17.3). Follow tracks the latest real detection; target frames the identified asset.
 */
export function CameraRig({ scene, origin }: { scene: Scene | null; origin: Origin | null }) {
  const ref = useRef<CameraControls>(null);
  const aimed = useRef<string | null>(null);
  const first = useRef(true);
  const preset = useThrottledStore(uiStore, (s) => s.camera, 10);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    c.smoothTime = 0.35; // ≈ 1.2 s to settle
    const smooth = !first.current && !reduceMotion(uiStore.getState());
    first.current = false;
    aimed.current = null;
    if (preset === "follow" || preset === "target") return; // from the live data, below
    const s = PRESETS[preset];
    void c.setLookAt(...s.position, ...s.target, smooth);
  }, [preset]);

  useFrame(() => {
    const c = ref.current;
    if (!c || !origin || (preset !== "follow" && preset !== "target")) return;
    const s = replayStore.getState();
    const smooth = !reduceMotion(uiStore.getState());
    const f = s.features[s.features.length - 1];
    if (preset === "follow") {
      const id = s.hello?.tracks[0];
      const pts = id ? s.tracks[id] : undefined;
      const last = pts?.[pts.length - 1];
      if (!last) return;
      const shot = followShot(toScene(last.x, last.y, last.alt, origin), f?.heading_deg ?? null);
      void c.setLookAt(...shot.position, ...shot.target, smooth);
      return;
    }
    const asset = scene?.assets.find((a) => a.asset_id === f?.target_asset_id);
    const at = asset
      ? toScene(asset.centroid_x_m, asset.centroid_y_m, 0, origin)
      : ([0, 0, 0] as Vec3);
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
