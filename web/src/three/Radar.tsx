import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import {
  AdditiveBlending,
  BufferGeometry,
  Float32BufferAttribute,
  type Group,
  Line,
  LineBasicMaterial,
  type Mesh,
  type MeshBasicMaterial,
  SphereGeometry,
} from "three";

import type { Scene } from "../api/messages";
import { clockNow, replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { circleLine, glowMaterial, sweepWedge } from "./geom";
import { color } from "./palette";
import {
  bearingDeg,
  bearingToYaw,
  screenScale,
  sweepAngleDeg,
  toScene,
  type Origin,
} from "./sceneMath";

const FLASHES = 6;
const FLASH_S = 0.6;
const LIVE_S = 1.5; // only detections this close to the clock flash (not a seek's catch-up)

type Sensor = Scene["sensors"][number];

/**
 * The radar's true range ring and its sweep (§17.3). The beam's bearing is the last detection's
 * plus 360° × rate per replay second since it: it crosses the drone at each real detection and
 * stands still when the replay is paused. Each detection flashes where the beam meets the drone.
 */
export function Radar({ sensor, origin }: { sensor: Sensor; origin: Origin }) {
  const pos = toScene(sensor.x_m, sensor.y_m, 0, origin);
  const ring = useMemo(() => circleLine(sensor.range_m, 192, 1), [sensor.range_m]);
  const wedge = useMemo(() => sweepWedge(sensor.range_m, 28, 24, 0.4), [sensor.range_m]);
  const beam = useMemo(() => {
    const g = new BufferGeometry();
    g.setAttribute("position", new Float32BufferAttribute([0, 0, 0, 0, 0, -sensor.range_m], 3));
    return new Line(
      g,
      new LineBasicMaterial({
        color: color("--flash"),
        transparent: true,
        opacity: 0.55,
        depthWrite: false,
      }),
    );
  }, [sensor.range_m]);
  const sweep = useRef<Group>(null);
  const flashes = useRef<(Mesh | null)[]>([]);
  const state = useRef({ seq: 0, next: 0, born: new Array<number>(FLASHES).fill(-1e9) });
  const sphere = useMemo(() => new SphereGeometry(1, 16, 12), []);
  const mats = useMemo(() => Array.from({ length: FLASHES }, () => glowMaterial("--flash", 0)), []);
  const rate = sensor.rate_hz ?? 1;

  useFrame(({ camera, size }) => {
    const s = replayStore.getState();
    const t = clockNow(s);
    const now = performance.now() / 1000;
    let last = null;
    for (let i = s.detections.length - 1; i >= 0; i--) {
      const d = s.detections[i];
      if (d && d.kind === "radar" && d.x !== null && d.y !== null) {
        last = d;
        break;
      }
    }
    const g = sweep.current;
    if (g) {
      // the beam spins once per detection interval of replay time (5 Hz at 5×): not in reduce motion
      g.visible = last !== null && !reduceMotion(uiStore.getState());
      if (last && last.x !== null && last.y !== null) {
        const b = bearingDeg([sensor.x_m, sensor.y_m], [last.x, last.y]);
        g.rotation.y = bearingToYaw(sweepAngleDeg(b, rate, t, last.t_s));
      }
    }
    // spawn flashes for new live detections
    const st = state.current;
    for (const d of s.detections) {
      if (d.seq <= st.seq) continue;
      st.seq = d.seq;
      if (d.kind !== "radar" || d.x === null || d.y === null || d.t_s < t - LIVE_S) continue;
      const m = flashes.current[st.next];
      if (m) {
        const [x, y, z] = toScene(d.x, d.y, d.alt ?? 0, origin);
        m.position.set(x, y, z);
        st.born[st.next] = now;
      }
      st.next = (st.next + 1) % FLASHES;
    }
    flashes.current.forEach((m, i) => {
      if (!m) return;
      const age = now - (st.born[i] ?? -1e9);
      const k = Math.max(0, 1 - age / FLASH_S);
      m.visible = k > 0;
      (m.material as MeshBasicMaterial).opacity = k * 0.8;
      const px = 6 + 8 * (1 - k);
      m.scale.setScalar(
        screenScale(camera.position.distanceTo(m.position), 45, size.height, px) / 2,
      );
    });
  });

  return (
    <group>
      <group position={pos}>
        <line>
          <primitive object={ring} attach="geometry" />
          <lineBasicMaterial color={color("--flash")} transparent opacity={0.28} />
        </line>
        <group ref={sweep} visible={false} position={[0, 1.5, 0]}>
          <mesh geometry={wedge}>
            <meshBasicMaterial
              vertexColors
              transparent
              depthWrite={false}
              blending={AdditiveBlending}
            />
          </mesh>
          <primitive object={beam} />
        </group>
      </group>
      {mats.map((mat, i) => (
        <mesh
          key={i}
          ref={(m) => {
            flashes.current[i] = m;
          }}
          geometry={sphere}
          material={mat}
          visible={false}
        />
      ))}
    </group>
  );
}
