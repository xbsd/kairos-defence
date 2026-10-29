// Per-frame mutation for the Swarm view's 3D scene (D-147 pattern: three.js objects are built
// once and changed here, from useFrame). Scene frame: the query's target-relative meters, 1 unit
// = 1 m, x east → x, y north → −z, altitude → y (§17.3).
import {
  BufferGeometry,
  CircleGeometry,
  DynamicDrawUsage,
  Float32BufferAttribute,
  type Group,
  Line,
  LineBasicMaterial,
  LineLoop,
  LineSegments,
  Mesh,
  MeshBasicMaterial,
  type Object3D,
  type PerspectiveCamera,
  Vector3,
} from "three";

import type { SwarmResponse } from "../api/messages";
import { color } from "../three/palette";
import { screenScale, type Vec3 } from "../three/sceneMath";
import { centroidOf, dronesAt, nearestEdges, rowAt, type P3 } from "./swarmMath";

export type Tone = "--flash" | "--afterglow";
const tmp = new Vector3();

/** Region-free scene coordinates of a target-relative point. */
export function toSwarmScene(p: P3): Vec3 {
  return [p[0], p[2], -p[1]];
}

/** A drone glyph: a filled disc for tonight, a ring for the matched ghost (both readable without
 * color). Unit radius, facing +z; the caller billboards and scales it. */
export function makeGlyph(tone: Tone): Object3D {
  if (tone === "--flash") {
    const mat = new MeshBasicMaterial({ color: color(tone), transparent: true, depthWrite: false });
    return new Mesh(new CircleGeometry(1, 24), mat);
  }
  const pts: number[] = [];
  for (let i = 0; i < 32; i++) {
    const a = (i / 32) * Math.PI * 2;
    pts.push(Math.cos(a), Math.sin(a), 0);
  }
  const g = new BufferGeometry();
  g.setAttribute("position", new Float32BufferAttribute(pts, 3));
  const mat = new LineBasicMaterial({ color: color(tone), transparent: true, depthWrite: false });
  return new LineLoop(g, mat);
}

/** Line segments for up to `n` formation edges, updated in place. */
export function makeEdges(n: number, tone: Tone, opacity: number): LineSegments {
  const g = new BufferGeometry();
  const attr = new Float32BufferAttribute(new Float32Array(Math.max(1, n) * 6), 3);
  attr.setUsage(DynamicDrawUsage);
  g.setAttribute("position", attr);
  g.setDrawRange(0, 0);
  const mat = new LineBasicMaterial({
    color: color(tone),
    transparent: true,
    opacity,
    depthWrite: false,
  });
  return new LineSegments(g, mat);
}

/** The centroid trail of the query flight (one vertex per described second). */
export function makePath(doc: SwarmResponse): Line {
  const c = doc.query.curves;
  const pts: number[] = [];
  c.t_s.forEach((_, i) => {
    const x = c.centroid_x_rel_m[i];
    const y = c.centroid_y_rel_m[i];
    pts.push(x ?? 0, 2, -(y ?? 0));
  });
  const g = new BufferGeometry();
  g.setAttribute("position", new Float32BufferAttribute(pts, 3));
  g.setDrawRange(0, 0);
  const mat = new LineBasicMaterial({
    color: color("--flash"),
    transparent: true,
    opacity: 0.55,
    depthWrite: false,
  });
  return new Line(g, mat);
}

/** Place the glyphs, the edges and the label anchor for one formation at this frame. */
export function stepFormation(
  pts: readonly (P3 | null)[],
  glyphs: readonly Object3D[],
  edges: LineSegments,
  label: Group | null,
  camera: PerspectiveCamera,
  viewportPx: number,
  px: number,
): void {
  pts.forEach((p, i) => {
    const g = glyphs[i];
    if (!g) return;
    g.visible = p !== null;
    if (!p) return;
    const [x, y, z] = toSwarmScene(p);
    g.position.set(x, y, z);
    g.quaternion.copy(camera.quaternion);
    const d = camera.position.distanceTo(g.getWorldPosition(tmp));
    g.scale.setScalar(screenScale(d, camera.fov ?? 45, viewportPx, px) / 2);
  });
  const pairs = nearestEdges(pts);
  const attr = edges.geometry.getAttribute("position") as Float32BufferAttribute;
  const arr = attr.array as Float32Array;
  let k = 0;
  for (const [i, j] of pairs) {
    const a = pts[i];
    const b = pts[j];
    if (!a || !b || k + 6 > arr.length) continue;
    arr.set([...toSwarmScene(a), ...toSwarmScene(b)], k);
    k += 6;
  }
  attr.needsUpdate = true;
  edges.geometry.setDrawRange(0, k / 3);
  const c = centroidOf(pts);
  if (label) {
    label.visible = c !== null;
    if (c) label.position.set(...toSwarmScene(c));
  }
}

/** Tonight's formation at the playhead. */
export function queryAt(doc: SwarmResponse, s: number): (P3 | null)[] {
  return dronesAt(doc.query, s);
}

/** Seconds of centroid trail behind the swarm, as the live theater's phosphor trail (§17.3). */
export const TRAIL_S = 60;

/** Show the centroid's last `TRAIL_S` described seconds up to the playhead. */
export function stepPath(line: Line, doc: SwarmResponse, s: number): void {
  const t = doc.query.curves.t_s;
  const end = rowAt(t, s);
  const start = Math.max(0, rowAt(t, s - TRAIL_S));
  line.geometry.setDrawRange(start, Math.max(0, end - start + 1));
}
