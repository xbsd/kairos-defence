import { Grid } from "@react-three/drei";
import { useLayoutEffect, useRef } from "react";
import type { Mesh, Material } from "three";

import { mix } from "./palette";

const CELL = mix("--scope", "--flash", 0.06);
const SECTION = mix("--scope", "--flash", 0.16);

/** Scope-glass ground with a fine grid: 50 m cells, 500 m sections, fading beyond 6 km (§17.3). */
export function Ground() {
  const ref = useRef<Mesh>(null);
  useLayoutEffect(() => {
    // drei's grid writes depth: lines lying on the ground (fence, roads, rings) then lose the depth
    // test against it far from the camera and show as dashes
    const m = ref.current?.material as Material | undefined;
    if (m) m.depthWrite = false;
  }, []);
  return (
    <Grid
      ref={ref}
      position={[0, -0.5, 0]}
      renderOrder={-1}
      args={[12000, 12000]}
      cellSize={50}
      cellThickness={0.6}
      cellColor={CELL}
      sectionSize={500}
      sectionThickness={1}
      sectionColor={SECTION}
      infiniteGrid
      fadeDistance={6000}
      fadeStrength={1.5}
      followCamera={false}
    />
  );
}
