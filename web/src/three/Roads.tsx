import { useMemo } from "react";
import { BufferGeometry, Float32BufferAttribute } from "three";

import type { Scene } from "../api/messages";
import { Label } from "./Label";
import { color } from "./palette";
import { toScene, type Origin, type Vec3 } from "./sceneMath";

function lineGeometry(points: Vec3[]): BufferGeometry {
  const g = new BufferGeometry();
  g.setAttribute("position", new Float32BufferAttribute(points.flat(), 3));
  return g;
}

/** Roads clipped to the scene radius, thin --ink-low lines with their names (§17.3). */
export function Roads({ roads, origin }: { roads: Scene["roads"]; origin: Origin }) {
  const items = useMemo(
    () =>
      roads.flatMap((r) =>
        r.lines.map((line, i) => {
          const pts = line.map(([x, y]) => toScene(x, y, 0.3, origin));
          // name the road at its point nearest the installation
          let best = pts[0] ?? ([0, 0, 0] as Vec3);
          for (const p of pts) if (Math.hypot(p[0], p[2]) < Math.hypot(best[0], best[2])) best = p;
          return { key: `${r.name}-${i}`, name: r.name, geom: lineGeometry(pts), at: best };
        }),
      ),
    [roads, origin],
  );
  const c = color("--ink-low");
  return (
    <group>
      {items.map((it) => (
        <group key={it.key}>
          <line>
            <primitive object={it.geom} attach="geometry" />
            <lineBasicMaterial color={c} transparent opacity={0.85} />
          </line>
          <Label text={it.name} position={[it.at[0], 8, it.at[2]]} px={12} tone="--ink-mid" />
        </group>
      ))}
    </group>
  );
}
