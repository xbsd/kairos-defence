import { Billboard } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { memo, useMemo, useRef } from "react";
import {
  AdditiveBlending,
  BufferGeometry,
  DynamicDrawUsage,
  Float32BufferAttribute,
  type Group,
  Line,
  LineBasicMaterial,
  LineLoop,
  type Mesh,
  Vector3,
} from "three";

import { clockNow, replayStore } from "../state/replayStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { unitRing } from "./geom";
import { Label } from "./Label";
import { color } from "./palette";
import {
  bearingDeg,
  bearingToYaw,
  quatrefoil,
  screenScale,
  toScene,
  TRAIL_S,
  trailAlpha,
  type Origin,
} from "./sceneMath";

const TRAIL_MAX = 256;
const RID_QUIET_S = 10; // "No Remote ID" when nothing was heard for 10 replay seconds
const GLYPH_PX = 22;
const tmp = new Vector3();

function makeLine(points: number[], name: "--flash" | "--alert", opacity = 1, loop = false) {
  const g = new BufferGeometry();
  g.setAttribute("position", new Float32BufferAttribute(points, 3));
  const m = new LineBasicMaterial({
    color: color(name),
    transparent: true,
    opacity,
    depthWrite: false,
  });
  return loop ? new LineLoop(g, m) : new Line(g, m);
}

/**
 * One live track (§17.3): a constant-screen-size quatrefoil with a heading tick at the latest
 * radar detection, a drop line, a ground ring and a 60 s phosphor trail fading from flash blue to
 * transparent. Every position is a real detection; the glyph eases over ~0.1 s between them.
 */
export const Drone = memo(function Drone({ trackId, origin }: { trackId: string; origin: Origin }) {
  const glyph = useMemo(() => {
    const pts = quatrefoil(96, 0.5).flatMap(([x, y]) => [x, y, 0]);
    return makeLine(pts, "--flash", 1, true);
  }, []);
  const tick = useMemo(() => makeLine([0, 0, 0, 0, 0, -1], "--flash"), []);
  const drop = useMemo(() => makeLine([0, 0, 0, 0, 0, 0], "--flash", 0.45), []);
  const trail = useMemo(() => {
    const g = new BufferGeometry();
    const pos = new Float32BufferAttribute(new Float32Array(TRAIL_MAX * 3), 3);
    const col = new Float32BufferAttribute(new Float32Array(TRAIL_MAX * 4), 4);
    pos.setUsage(DynamicDrawUsage);
    col.setUsage(DynamicDrawUsage);
    g.setAttribute("position", pos);
    g.setAttribute("color", col);
    g.setDrawRange(0, 0);
    const m = new LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      depthWrite: false,
      blending: AdditiveBlending,
    });
    return new Line(g, m);
  }, []);
  const ringGeom = useMemo(() => unitRing(0.86), []);
  const body = useRef<Group>(null);
  const icon = useRef<Group>(null);
  const ring = useRef<Mesh>(null);
  const tag = useRef<Group>(null);
  const shown = useRef<Vector3 | null>(null);

  useFrame(({ camera, size }, dt) => {
    const s = replayStore.getState();
    const pts = s.tracks[trackId];
    const last = pts?.[pts.length - 1];
    const b = body.current;
    if (!b) return;
    b.visible = last !== undefined;
    if (!pts || !last) return;
    const t = clockNow(s);
    const target = new Vector3(...toScene(last.x, last.y, last.alt, origin));
    const reduce = reduceMotion(uiStore.getState());
    if (!shown.current || reduce) shown.current = target.clone();
    else shown.current.lerp(target, 1 - Math.exp(-dt / 0.1));
    const p = shown.current;
    b.position.copy(p);
    const k = screenScale(
      camera.position.distanceTo(b.getWorldPosition(tmp)),
      45,
      size.height,
      GLYPH_PX,
    );
    icon.current?.scale.setScalar(k);
    // heading: the latest feature row of this track, else the last two detections
    const f = s.features[s.features.length - 1];
    const prev = pts[pts.length - 2];
    const hdg =
      f && f.track_id === trackId && f.heading_deg !== null
        ? f.heading_deg
        : prev
          ? bearingDeg([prev.x, prev.y], [last.x, last.y])
          : null;
    tick.visible = hdg !== null;
    if (hdg !== null) {
      tick.rotation.y = bearingToYaw(hdg);
      tick.scale.setScalar(k * 1.1);
    }
    const dpos = drop.geometry.getAttribute("position");
    dpos.setXYZ(1, 0, -p.y, 0);
    dpos.needsUpdate = true;
    if (ring.current) {
      ring.current.position.set(0, -p.y + 0.6, 0);
      ring.current.scale.setScalar(k * 0.45);
    }
    // phosphor trail: the last 60 replay seconds, alpha 1 → 0
    const pa = trail.geometry.getAttribute("position");
    const ca = trail.geometry.getAttribute("color");
    const c = color("--flash");
    let n = 0;
    for (let i = Math.max(0, pts.length - TRAIL_MAX); i < pts.length; i++) {
      const q = pts[i];
      if (!q || t - q.t_s > TRAIL_S || q.t_s > t) continue;
      const [x, y, z] = toScene(q.x, q.y, q.alt, origin);
      pa.setXYZ(n, x - p.x, y - p.y, z - p.z);
      ca.setXYZW(n, c.r, c.g, c.b, trailAlpha(t - q.t_s));
      n++;
    }
    pa.needsUpdate = true;
    ca.needsUpdate = true;
    trail.geometry.setDrawRange(0, n);
    const quiet = !s.rid.some((r) => t - r.t_s >= 0 && t - r.t_s <= RID_QUIET_S);
    if (tag.current) tag.current.visible = quiet;
  });

  return (
    <group ref={body} visible={false}>
      <primitive object={trail} />
      <primitive object={drop} />
      <primitive object={tick} />
      <mesh ref={ring} geometry={ringGeom}>
        <meshBasicMaterial color={color("--flash")} transparent opacity={0.5} depthWrite={false} />
      </mesh>
      <Billboard>
        <group ref={icon}>
          <primitive object={glyph} />
        </group>
      </Billboard>
      <group ref={tag}>
        <Label
          text="No Remote ID"
          position={[0, 0, 0]}
          px={12}
          tone="--alert"
          anchorX="center"
          anchorY="bottom"
          dyPx={28} // above the orbit ring of the trail, so the tag stays legible (D-166)
        />
      </group>
    </group>
  );
});
