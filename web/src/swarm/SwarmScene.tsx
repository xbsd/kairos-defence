import { CameraControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import { type Group, Line, LineBasicMaterial, type PerspectiveCamera } from "three";

import type { SwarmResponse } from "../api/messages";
import { swarmStore } from "../state/swarmStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { token } from "../theme/colors";
import { circleLine } from "../three/geom";
import { Ground } from "../three/Ground";
import { Label } from "../three/Label";
import { color } from "../three/palette";
import { assetLabel } from "../three/sceneMath";
import {
  makeEdges,
  makeGlyph,
  makePath,
  queryAt,
  stepFormation,
  stepPath,
  toSwarmScene,
  type Tone,
} from "./swarmLayer";
import { centroidOf, ghostAt } from "./swarmMath";

const GLYPH_PX = 11;
const CAMERA_OFFSET: [number, number, number] = [0, 430, 560]; // ≈ 700 m out, 38° down

/** One formation: a glyph per drone, nearest-neighbor edges and a label at its centroid. */
function Formation(props: { doc: SwarmResponse; ghost: boolean; label: string }) {
  const { doc, ghost } = props;
  const n = (ghost ? doc.match?.positions.length : doc.query.positions.length) ?? 0;
  const tone: Tone = ghost ? "--afterglow" : "--flash";
  const glyphs = useMemo(() => Array.from({ length: n }, () => makeGlyph(tone)), [n, tone]);
  const edges = useMemo(() => makeEdges(n, tone, ghost ? 0.55 : 0.7), [n, tone, ghost]);
  const label = useRef<Group>(null);
  useEffect(
    () => () => {
      edges.geometry.dispose();
      for (const g of glyphs)
        g.traverse((o) => (o as { geometry?: { dispose(): void } }).geometry?.dispose());
    },
    [edges, glyphs],
  );
  useFrame(({ camera, size }) => {
    const s = swarmStore.getState().playhead;
    const pts = ghost ? ghostAt(doc, s) : queryAt(doc, s);
    stepFormation(
      pts,
      glyphs,
      edges,
      label.current,
      camera as PerspectiveCamera,
      size.height,
      ghost ? GLYPH_PX + 3 : GLYPH_PX,
    );
  });
  return (
    <>
      {glyphs.map((g, i) => (
        <primitive key={i} object={g} />
      ))}
      <primitive object={edges} />
      <group ref={label}>
        <Label
          text={props.label}
          position={[0, 0, 0]}
          tone={tone}
          px={13}
          anchorY={ghost ? "top" : "bottom"}
          dyPx={ghost ? -22 : 22}
        />
      </group>
    </>
  );
}

/** Tonight's centroid path, revealed up to the playhead. */
function Path({ doc }: { doc: SwarmResponse }) {
  const line = useMemo(() => makePath(doc), [doc]);
  useEffect(() => () => line.geometry.dispose(), [line]);
  useFrame(() => stepPath(line, doc, swarmStore.getState().playhead));
  return <primitive object={line} />;
}

/** The target asset at the frame's origin: a ground ring and its name. */
function Target({ kind }: { kind: string }) {
  const ring = useMemo(() => {
    const mat = new LineBasicMaterial({
      color: color("--ink-mid"),
      transparent: true,
      opacity: 0.7,
      depthWrite: false,
    });
    return new Line(circleLine(40, 64, 0.5), mat);
  }, []);
  useEffect(() => () => ring.geometry.dispose(), [ring]);
  return (
    <>
      <primitive object={ring} />
      <Label text={`Target: ${assetLabel(kind)}`} position={[0, 2, 0]} tone="--ink-mid" px={12} />
    </>
  );
}

/** Follows tonight's centroid (free orbit and zoom around it); no easing in reduce motion. */
function FollowCamera({ doc }: { doc: SwarmResponse }) {
  const ref = useRef<CameraControls>(null);
  const placed = useRef(false);
  useEffect(() => {
    if (ref.current) ref.current.smoothTime = 0.25;
  }, []);
  useFrame(() => {
    const c = ref.current;
    const at = centroidOf(queryAt(doc, swarmStore.getState().playhead));
    if (!c || !at) return;
    const [x, y, z] = toSwarmScene(at);
    if (!placed.current) {
      placed.current = true;
      void c.setLookAt(
        x + CAMERA_OFFSET[0],
        y + CAMERA_OFFSET[1],
        z + CAMERA_OFFSET[2],
        x,
        y,
        z,
        false,
      );
      return;
    }
    void c.moveTo(x, y, z, !reduceMotion(uiStore.getState()));
  });
  return (
    <CameraControls
      ref={ref}
      makeDefault
      minDistance={120}
      maxDistance={6000}
      maxPolarAngle={(84 * Math.PI) / 180}
    />
  );
}

/**
 * The Swarm view's 3D scene (SPEC §17.9): tonight's drones in flash blue with formation edges, the
 * matched past swarm as an afterglow ghost at its DTW-aligned second, re-centered on tonight's
 * centroid, and the target. Everything moves with the playhead over the recorded seconds.
 */
export function SwarmScene(props: { doc: SwarmResponse; tonight: string; past: string | null }) {
  const background = token("--scope");
  return (
    <div data-testid="swarm-scene" className="absolute inset-0 bg-scope">
      <Canvas
        dpr={[1, 2]}
        gl={{ antialias: true, powerPreference: "high-performance" }}
        camera={{ fov: 45, near: 2, far: 30000, position: CAMERA_OFFSET }}
        aria-hidden="true"
      >
        <color attach="background" args={[background]} />
        <Ground />
        <Target kind={props.doc.query.target.kind} />
        <Path doc={props.doc} />
        {props.doc.match && props.past ? (
          <Formation doc={props.doc} ghost label={props.past} />
        ) : null}
        <Formation doc={props.doc} ghost={false} label={props.tonight} />
        <FollowCamera doc={props.doc} />
      </Canvas>
    </div>
  );
}
