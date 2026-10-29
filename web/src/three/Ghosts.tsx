import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import { AdditiveBlending, type InterleavedBufferAttribute } from "three";
import { Line2 } from "three/examples/jsm/lines/Line2.js";
import { LineGeometry } from "three/examples/jsm/lines/LineGeometry.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";

import type { Scene } from "../api/messages";
import { revealOf } from "../director/engine";
import { useThrottledStore } from "../lib/useThrottledStore";
import { useThrottledStores } from "../lib/useThrottledStores";
import { directorStore } from "../state/directorStore";
import { ghostStore } from "../state/ghostStore";
import { matchStore } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import type { StoreApi } from "zustand/vanilla";
import { currentGhosts, useGhostLoader, type GhostSpec } from "./ghostLayer";
import { dissolveAlpha } from "./ghostMath";
import { Label } from "./Label";
import { color } from "./palette";
import { toScene, type Origin } from "./sceneMath";

const STORES = [matchStore, ghostStore, replayStore] as unknown as StoreApi<unknown>[];

/** One frame of a ghost: its dissolve (once) and its hover brightness. */
function stepGhost(
  line: Line2,
  spec: GhostSpec,
  index: number,
  size: { width: number; height: number },
  st: { born: { current: number }; done: { current: boolean }; lastBright: { current: number } },
): void {
  line.material.resolution.set(size.width, size.height);
  if (st.born.current === 0) st.born.current = performance.now();
  const reduce = reduceMotion(uiStore.getState());
  const hovered = matchStore.getState().hovered;
  const bright = hovered === null ? 0.75 : hovered === spec.track ? 1 : 0.35;
  const age = performance.now() - st.born.current;
  if (st.done.current && bright === st.lastBright.current) return;
  const attr = line.geometry.getAttribute("instanceColorStart") as InterleavedBufferAttribute;
  const arr = attr.data.array as Float32Array;
  const c = color("--afterglow");
  const nSeg = spec.points.length - 1;
  let finished = true;
  for (let k = 0; k < nSeg; k++) {
    // reduce motion: a plain fade, no per-segment dissolve
    const a = reduce ? Math.min(1, Math.max(0, age / 600)) : dissolveAlpha(k, index, age);
    if (a < 1) finished = false;
    const v = a * bright;
    // instanceColorStart / End interleave: [r g b (start) r g b (end)] per segment
    arr.set([c.r * v, c.g * v, c.b * v, c.r * v, c.g * v, c.b * v], k * 6);
  }
  attr.data.needsUpdate = true;
  st.done.current = finished;
  st.lastBright.current = bright;
}

function Ghost({ spec, index, origin }: { spec: GhostSpec; index: number; origin: Origin }) {
  const line = useMemo(() => {
    const pos = spec.points.flatMap((p) => toScene(p.x, p.y, p.alt, origin));
    const geom = new LineGeometry();
    geom.setPositions(pos);
    geom.setColors(new Array(pos.length).fill(0));
    const mat = new LineMaterial({
      vertexColors: true,
      linewidth: 2,
      transparent: true,
      depthWrite: false,
      blending: AdditiveBlending,
    });
    return new Line2(geom, mat);
  }, [spec, origin]);
  useEffect(
    () => () => {
      line.geometry.dispose();
      line.material.dispose();
    },
    [line],
  );
  const born = useRef(0);
  const done = useRef(false);
  const lastBright = useRef(-1);
  // a new line starts dark: let the next frames color it (the dissolve keeps its start time)
  useEffect(() => {
    done.current = false;
  }, [line]);

  useFrame(({ size }) => stepGhost(line, spec, index, size, { born, done, lastBright }));

  const end = spec.points[spec.points.length - 1];
  const at = end ? toScene(end.x, end.y, end.alt, origin) : null;
  return (
    <group>
      <primitive object={line} />
      {at ? (
        // the recovery points sit together: stack the labels so they never overprint
        <Label
          text={spec.label}
          position={[at[0], at[1] + 6, at[2]]}
          px={12}
          tone="--afterglow"
          anchorX="left"
          dxPx={10}
          dyPx={6 + 16 * index}
        />
      ) : null}
    </group>
  );
}

/**
 * Afterglow ghosts (§17.3): the current top 3's past flights in tonight's target frame,
 * dissolving in over 1.2 s, 150 ms apart; the hovered match's ghost brightens. Shown once
 * tonight's target is a named asset (D-128).
 */
export function Ghosts({ scene, origin }: { scene: Scene; origin: Origin }) {
  useGhostLoader();
  const g = useThrottledStores(STORES, () => currentGhosts(scene), 4);
  const shown = useThrottledStore(directorStore, (d) => revealOf(d.active, d.beat).ghosts, 4);
  if (!shown) return null;
  const target = g.key.split("|")[0];
  return (
    <group>
      {g.ghosts.map((spec, i) => (
        <Ghost key={`${target}:${spec.track}`} spec={spec} index={i} origin={origin} />
      ))}
    </group>
  );
}
