import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import { type Mesh, type MeshBasicMaterial } from "three";
import { Line2 } from "three/examples/jsm/lines/Line2.js";
import { LineGeometry } from "three/examples/jsm/lines/LineGeometry.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";

import type { ForecastMsg, Scene } from "../api/messages";
import { revealOf } from "../director/engine";
import { useThrottledStore } from "../lib/useThrottledStore";
import { directorStore } from "../state/directorStore";
import { matchStore } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { zoneLabel, zoneRoads } from "./forecastLayer";
import { Label } from "./Label";
import { color } from "./palette";
import { toScene, type Origin } from "./sceneMath";

const PATH_ALT_M = 25;
const PULSE_S = 1.6;
const DASH_FLOW_MS = 60; // dash offset in meters per second of playback

function dashedLine(points: number[], dash: number, gap: number, width = 2): Line2 {
  const g = new LineGeometry();
  g.setPositions(points);
  const m = new LineMaterial({
    color: color("--bone").getHex(),
    linewidth: width,
    dashed: true,
    dashSize: dash,
    gapSize: gap,
    transparent: true,
    opacity: 0.95,
    depthWrite: false,
  });
  const l = new Line2(g, m);
  l.computeLineDistances();
  return l;
}

/** Playback seconds advance only while the replay plays (D-133): motion tied to a live forecast. */
function playingDt(dt: number): number {
  const c = replayStore.getState().clock;
  if (!c?.playing || reduceMotion(uiStore.getState())) return 0;
  return dt;
}

/** One frame: the path's dash flows, the road's dots move, the zone pulses (only while playing). */
function stepForecast(
  all: Line2[],
  roads: Line2[],
  disc: Mesh | null,
  phase: { current: number },
  size: { width: number; height: number },
  dt: number,
): void {
  const live = playingDt(dt);
  phase.current += live;
  for (const l of all) l.material.resolution.set(size.width, size.height);
  const path = all[0];
  if (path) path.material.dashOffset -= DASH_FLOW_MS * live;
  for (const r of roads) r.material.dashOffset -= 20 * live; // the road's slowly moving dots
  const m = disc?.material as MeshBasicMaterial | undefined;
  if (m) m.opacity = 0.07 + 0.07 * (0.5 + 0.5 * Math.cos((2 * Math.PI * phase.current) / PULSE_S));
}

function ForecastShapes({ f, scene, origin }: { f: ForecastMsg; scene: Scene; origin: Origin }) {
  const path = useMemo(
    () =>
      dashedLine(
        f.path.flatMap(([x, y]) => toScene(x, y, PATH_ALT_M, origin)),
        22,
        26,
      ),
    [f, origin],
  );
  const ring = useMemo(() => {
    const pts: number[] = [];
    for (let i = 0; i <= 96; i++) {
      const a = (i / 96) * Math.PI * 2;
      pts.push(
        ...toScene(
          f.center_x_m + f.radius_m * Math.cos(a),
          f.center_y_m + f.radius_m * Math.sin(a),
          1,
          origin,
        ),
      );
    }
    return dashedLine(pts, 18, 22, 1.5);
  }, [f, origin]);
  const roads = useMemo(
    () =>
      zoneRoads(f, scene).flatMap((r) =>
        r.parts.map((p) =>
          dashedLine(
            p.flatMap(([x, y]) => toScene(x, y, 1.5, origin)),
            6,
            14,
            3,
          ),
        ),
      ),
    [f, scene, origin],
  );
  useEffect(
    () => () => {
      for (const l of [path, ring, ...roads]) {
        l.geometry.dispose();
        l.material.dispose();
      }
    },
    [path, ring, roads],
  );
  const disc = useRef<Mesh>(null);
  const phase = useRef(0);
  useFrame(({ size }, dt) =>
    stepForecast([path, ring, ...roads], roads, disc.current, phase, size, dt),
  );
  const [cx, , cz] = toScene(f.center_x_m, f.center_y_m, 0, origin);
  const label = zoneLabel(f, scene);
  return (
    <group>
      <primitive object={path} />
      <primitive object={ring} />
      {roads.map((r, i) => (
        <primitive key={i} object={r} />
      ))}
      <mesh ref={disc} position={[cx, 0.8, cz]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[f.radius_m, 96]} />
        <meshBasicMaterial color={color("--bone")} transparent opacity={0.1} depthWrite={false} />
      </mesh>
      {label ? (
        // east of the zone, reading away from it: clear of the ghost labels and the report overlay
        <Label
          text={label}
          position={[cx + f.radius_m, 30, cz]}
          px={13}
          tone="--bone"
          anchorX="left"
          anchorY="middle"
          dxPx={12}
        />
      ) : null}
    </group>
  );
}

/**
 * The forecast (§13, §17.3): the dotted bone exit path with a slow flowing dash, the recovery
 * zone as a ground disc with a 1.6 s pulse and its computed label, and each zone road's in-zone
 * segment turned bone with slowly moving dots. Motion runs only while the replay plays.
 */
export function Forecast({ scene, origin }: { scene: Scene; origin: Origin }) {
  const f = useThrottledStore(matchStore, (s) => s.forecast, 4);
  const shown = useThrottledStore(directorStore, (d) => revealOf(d.active, d.beat).forecast, 4);
  if (!f || !shown) return null;
  return <ForecastShapes f={f} scene={scene} origin={origin} />;
}
