import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import {
  BufferGeometry,
  Float32BufferAttribute,
  Line,
  LineBasicMaterial,
  type Mesh,
  type MeshBasicMaterial,
} from "three";

import type { Scene } from "../api/messages";
import { clockNow, replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { glowMaterial, unitRing } from "./geom";
import { color } from "./palette";
import {
  bearingToYaw,
  RF_RING_M,
  RF_RING_S,
  rfRingRadius,
  toScene,
  type Origin,
} from "./sceneMath";

const LINES = 12;
const RINGS = 6;
const LINE_S = 4; // a bearing line stays for 4 replay seconds, fading
const LIVE_S = 1.5;

type Sensor = Scene["sensors"][number];

/**
 * RF detections (§17.3): the measured bearing line of each real detection, noise included, and a
 * ring at the sensor expanding 0 → 300 m over 1.2 s.
 */
export function Rf({ sensor, origin }: { sensor: Sensor; origin: Origin }) {
  const pos = toScene(sensor.x_m, sensor.y_m, 2, origin);
  const len = Math.min(sensor.range_m, 4000);
  const lineObjs = useMemo(
    () =>
      Array.from({ length: LINES }, () => {
        const g = new BufferGeometry();
        g.setAttribute("position", new Float32BufferAttribute([0, 0, 0, 0, 0, -len], 3));
        const m = new LineBasicMaterial({
          color: color("--flash"),
          transparent: true,
          opacity: 0,
          depthWrite: false,
        });
        const l = new Line(g, m);
        l.visible = false;
        return l;
      }),
    [len],
  );
  const ringGeom = useMemo(() => unitRing(0.985), []);
  const ringMats = useMemo(
    () => Array.from({ length: RINGS }, () => glowMaterial("--flash", 0)),
    [],
  );
  const rings = useRef<(Mesh | null)[]>([]);
  const st = useRef({ seq: 0, next: 0, born: new Array<number>(RINGS).fill(-1e9) });

  useFrame(() => {
    const s = replayStore.getState();
    const t = clockNow(s);
    const now = performance.now() / 1000;
    const mine = s.rf.filter((r) => r.sensor_id === sensor.sensor_id && r.bearing_deg !== null);
    const recent = mine.filter((r) => t - r.t_s >= 0 && t - r.t_s <= LINE_S).slice(-LINES);
    lineObjs.forEach((l, i) => {
      const r = recent[i];
      l.visible = r !== undefined;
      if (!r || r.bearing_deg === null) return;
      l.rotation.y = bearingToYaw(r.bearing_deg);
      (l.material as LineBasicMaterial).opacity = 0.55 * (1 - (t - r.t_s) / LINE_S);
    });
    const reduce = reduceMotion(uiStore.getState());
    const k = st.current;
    for (const d of s.detections) {
      if (d.seq <= k.seq) continue;
      k.seq = d.seq;
      if (d.kind !== "rf" || d.sensor !== sensor.sensor_id || d.t_s < t - LIVE_S) continue;
      k.born[k.next] = now;
      k.next = (k.next + 1) % RINGS;
    }
    rings.current.forEach((m, i) => {
      if (!m) return;
      const age = now - (k.born[i] ?? -1e9);
      const r = reduce ? (age <= RF_RING_S ? RF_RING_M : null) : rfRingRadius(age);
      m.visible = r !== null;
      if (r === null) return;
      m.scale.setScalar(Math.max(r, 1));
      (m.material as MeshBasicMaterial).opacity = 0.55 * (1 - age / RF_RING_S);
    });
  });

  return (
    <group position={pos}>
      {lineObjs.map((l, i) => (
        <primitive key={i} object={l} />
      ))}
      {ringMats.map((m, i) => (
        <mesh
          key={i}
          ref={(x) => {
            rings.current[i] = x;
          }}
          geometry={ringGeom}
          material={m}
          visible={false}
        />
      ))}
    </group>
  );
}
