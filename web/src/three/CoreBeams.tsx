import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import { AdditiveBlending, type InterleavedBufferAttribute } from "three";
import { Line2 } from "three/examples/jsm/lines/Line2.js";
import { LineGeometry } from "three/examples/jsm/lines/LineGeometry.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";

import type { Scene } from "../api/messages";
import { revealOf } from "../director/engine";
import { directorStore } from "../state/directorStore";
import { matchStore } from "../state/matchStore";
import { beamsOn, uiStore } from "../state/uiStore";
import { BEAM_MS, beamGlow, beamTargets } from "./beams";
import { color } from "./palette";
import { arcPoint, CORE_POSITION, type Origin } from "./sceneMath";

const SEGMENTS = 40;

/** One frame of the beams: aim them on a new `match`, then move each beam's head. */
function stepBeams(
  lines: Line2[],
  seen: { current: number },
  scene: Scene,
  origin: Origin,
  size: { width: number; height: number },
): void {
  const ms = matchStore.getState();
  const d = directorStore.getState();
  const on = beamsOn(uiStore.getState()) && revealOf(d.active, d.beat).ghosts;
  const age = performance.now() - ms.matchWall;
  if (!on || !ms.matchWall || age > BEAM_MS) {
    for (const l of lines) l.visible = false;
    return;
  }
  if (seen.current !== ms.matchWall) {
    seen.current = ms.matchWall;
    const targets = beamTargets(scene, origin);
    lines.forEach((l, k) => {
      const to = targets[k];
      l.visible = !!to;
      if (!to) return;
      const lift = 0.18 * Math.hypot(to[0] - CORE_POSITION[0], to[2] - CORE_POSITION[2]);
      const pts: number[] = [];
      for (let i = 0; i <= SEGMENTS; i++)
        pts.push(...arcPoint(CORE_POSITION, to, i / SEGMENTS, lift));
      l.geometry.setPositions(pts);
      l.geometry.setColors(new Array(pts.length).fill(0));
      l.computeLineDistances();
    });
  }
  const head = Math.min(1, age / BEAM_MS);
  const fade = 1 - Math.max(0, (age - BEAM_MS * 0.8) / (BEAM_MS * 0.2));
  const c = color("--afterglow");
  for (const l of lines) {
    if (!l.visible) continue;
    l.material.resolution.set(size.width, size.height);
    const attr = l.geometry.getAttribute("instanceColorStart") as InterleavedBufferAttribute;
    const arr = attr.data.array as Float32Array;
    for (let k = 0; k < SEGMENTS; k++) {
      const v0 = beamGlow(k / SEGMENTS, head) * fade;
      const v1 = beamGlow((k + 1) / SEGMENTS, head) * fade;
      arr.set([c.r * v0, c.g * v0, c.b * v0, c.r * v1, c.g * v1, c.b * v1], k * 6);
    }
    attr.data.needsUpdate = true;
  }
}

/**
 * Core beams (§17.3, D-129): on each `match`, three afterglow beams leave the Kairos core toward
 * where the ghosts are (each past flight at the matched moment) over 1.2 s. Off in reduce motion
 * and Performance mode (they count as particles, §17.11).
 */
export function CoreBeams({ scene, origin }: { scene: Scene; origin: Origin }) {
  const lines = useMemo(
    () =>
      [0, 1, 2].map(() => {
        const g = new LineGeometry();
        g.setPositions(new Array((SEGMENTS + 1) * 3).fill(0));
        g.setColors(new Array((SEGMENTS + 1) * 3).fill(0));
        const mat = new LineMaterial({
          vertexColors: true,
          linewidth: 2,
          transparent: true,
          depthWrite: false,
          blending: AdditiveBlending,
        });
        const l = new Line2(g, mat);
        l.visible = false;
        l.frustumCulled = false;
        return l;
      }),
    [],
  );
  useEffect(
    () => () =>
      lines.forEach((l) => {
        l.geometry.dispose();
        l.material.dispose();
      }),
    [lines],
  );
  const seen = useRef(0);

  useFrame(({ size }) => stepBeams(lines, seen, scene, origin, size));

  return (
    <group>
      {lines.map((l, k) => (
        <primitive key={k} object={l} />
      ))}
    </group>
  );
}
