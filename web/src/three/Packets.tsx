import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import { AdditiveBlending, type InstancedMesh, Object3D, OctahedronGeometry, Vector3 } from "three";

import type { Scene } from "../api/messages";
import { clockNow, replayStore } from "../state/replayStore";
import { PACKET_BUDGET, packetBudget, uiStore } from "../state/uiStore";
import { color } from "./palette";
import {
  CORE_POSITION,
  PACKET_LEG1_S,
  PACKET_LEG2_S,
  packetPosition,
  screenScale,
  toScene,
  type Origin,
  type Vec3,
} from "./sceneMath";

const LIVE_S = 1.5; // a seek's catch-up does not launch packets
const PACKET_PX = 5;

interface Packet {
  from: Vec3;
  sensor: Vec3;
  born: number;
}

/**
 * Data packets (§17.3): one per real detection, drone → detecting sensor → Kairos core along
 * curved arcs (0.9 s + 0.6 s). One instanced mesh; at most the packet budget in flight.
 */
export function Packets({ scene, origin }: { scene: Scene; origin: Origin }) {
  const mesh = useRef<InstancedMesh>(null);
  const geom = useMemo(() => new OctahedronGeometry(1, 0), []);
  const sensors = useMemo(() => {
    const m = new Map<string, Vec3>();
    for (const s of scene.sensors) m.set(s.sensor_id, toScene(s.x_m, s.y_m, 4, origin));
    return m;
  }, [scene, origin]);
  const ridSensor = useMemo(() => {
    const s = scene.sensors.find((x) => x.kind === "rid");
    return s ? toScene(s.x_m, s.y_m, 4, origin) : null;
  }, [scene, origin]);
  const st = useRef({ seq: 0, packets: [] as Packet[] });
  const dummy = useMemo(() => new Object3D(), []);
  const v = useMemo(() => new Vector3(), []);

  useFrame(({ camera, size }) => {
    const im = mesh.current;
    if (!im) return;
    const s = replayStore.getState();
    const t = clockNow(s);
    const now = performance.now() / 1000;
    const budget = packetBudget(uiStore.getState());
    const k = st.current;
    let drone: Vec3 | null = null;
    for (const d of s.detections) {
      if (d.kind === "radar" && d.x !== null && d.y !== null)
        drone = toScene(d.x, d.y, d.alt ?? 0, origin);
      if (d.seq <= k.seq) continue;
      k.seq = d.seq;
      if (d.t_s < t - LIVE_S || k.packets.length >= budget) continue;
      const sensor = d.kind === "rid" ? ridSensor : (sensors.get(d.sensor) ?? null);
      if (!sensor) continue;
      const from =
        d.x !== null && d.y !== null ? toScene(d.x, d.y, d.alt ?? 60, origin) : (drone ?? sensor);
      k.packets.push({ from, sensor, born: d.wall / 1000 });
    }
    const life = PACKET_LEG1_S + PACKET_LEG2_S;
    k.packets = k.packets.filter((p) => now - p.born <= life);
    let n = 0;
    for (const p of k.packets) {
      const at = packetPosition(p.from, p.sensor, CORE_POSITION, now - p.born);
      if (!at || n >= budget) continue;
      v.set(at[0], at[1], at[2]);
      dummy.position.copy(v);
      dummy.scale.setScalar(
        screenScale(camera.position.distanceTo(v), 45, size.height, PACKET_PX) / 2,
      );
      dummy.updateMatrix();
      im.setMatrixAt(n++, dummy.matrix);
    }
    im.count = n;
    im.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={mesh} args={[geom, undefined, PACKET_BUDGET]} frustumCulled={false}>
      <meshBasicMaterial
        color={color("--flash")}
        transparent
        opacity={0.9}
        blending={AdditiveBlending}
        depthWrite={false}
      />
    </instancedMesh>
  );
}
