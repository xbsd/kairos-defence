import { Edges } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import { AdditiveBlending, type Group, type Mesh, type MeshBasicMaterial } from "three";

import { replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { Label } from "./Label";
import { color } from "./palette";
import { CORE_POSITION } from "./sceneMath";

const DEG_PER_INGEST = 4;
const PULSE_MS = 450;

/**
 * The Kairos core (§17.3, D-012): a ringed octahedron that turns a few degrees with each real
 * `ingest` batch and pulses when it arrives. When nothing is written, it is perfectly still.
 */
export function Core() {
  const spin = useRef<Group>(null);
  const glow = useRef<Mesh>(null);
  const shown = useRef(0);
  useFrame((_, dt) => {
    const s = replayStore.getState();
    const target = (s.ingestCount * DEG_PER_INGEST * Math.PI) / 180;
    const reduce = reduceMotion(uiStore.getState());
    shown.current = reduce
      ? target
      : shown.current + (target - shown.current) * (1 - Math.exp(-dt / 0.2));
    if (spin.current) spin.current.rotation.y = shown.current;
    const g = glow.current;
    if (g) {
      const age = performance.now() - s.ingestWall;
      const p = s.ingestCount > 0 ? Math.exp(-Math.max(0, age) / PULSE_MS) : 0;
      (g.material as MeshBasicMaterial).opacity = 0.06 + 0.45 * p;
      g.scale.setScalar(70 * (1 + (reduce ? 0 : 0.25 * p)));
    }
  });
  const flash = color("--flash");
  return (
    <group position={CORE_POSITION}>
      <group ref={spin}>
        <mesh>
          <octahedronGeometry args={[70, 0]} />
          <meshBasicMaterial color={flash} transparent opacity={0.08} depthWrite={false} />
          <Edges color={flash} lineWidth={1.2} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[110, 1.2, 6, 96]} />
          <meshBasicMaterial color={flash} transparent opacity={0.7} />
        </mesh>
        <mesh rotation={[Math.PI / 2.6, 0.4, 0]}>
          <torusGeometry args={[140, 0.9, 6, 96]} />
          <meshBasicMaterial color={flash} transparent opacity={0.45} />
        </mesh>
      </group>
      <mesh ref={glow}>
        <sphereGeometry args={[1, 24, 16]} />
        <meshBasicMaterial
          color={flash}
          transparent
          opacity={0.06}
          blending={AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      <Label
        text="Kairos core: DuckDB and LanceDB"
        position={[0, -95, 0]}
        px={13}
        tone="--ink-hi"
        anchorY="top"
      />
    </group>
  );
}
