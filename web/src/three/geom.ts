// Small geometry builders shared by the theater components.
import {
  AdditiveBlending,
  BufferGeometry,
  Float32BufferAttribute,
  MeshBasicMaterial,
  RingGeometry,
} from "three";

import { color } from "./palette";

/** A horizontal circle (xz plane) of radius `r` as a line strip. */
export function circleLine(r: number, n = 128, y = 0): BufferGeometry {
  const pts: number[] = [];
  for (let i = 0; i <= n; i++) {
    const a = (i / n) * Math.PI * 2;
    pts.push(r * Math.cos(a), y, r * Math.sin(a));
  }
  const g = new BufferGeometry();
  g.setAttribute("position", new Float32BufferAttribute(pts, 3));
  return g;
}

/**
 * A flat sector (xz plane) from bearing 0 back to −`widthDeg` (it trails a clockwise beam whose
 * leading edge points along local −z), with RGBA vertex colors fading to transparent behind.
 */
export function sweepWedge(radius: number, widthDeg: number, n = 24, alpha = 0.32): BufferGeometry {
  const pos: number[] = [];
  const col: number[] = [];
  const c = color("--flash");
  for (let i = 0; i < n; i++) {
    const b0 = (-(i / n) * widthDeg * Math.PI) / 180;
    const b1 = (-((i + 1) / n) * widthDeg * Math.PI) / 180;
    const a0 = alpha * (1 - i / n);
    const a1 = alpha * (1 - (i + 1) / n);
    pos.push(
      0,
      0,
      0,
      radius * Math.sin(b1),
      0,
      -radius * Math.cos(b1),
      radius * Math.sin(b0),
      0,
      -radius * Math.cos(b0),
    );
    col.push(c.r, c.g, c.b, a0 * 0.4, c.r, c.g, c.b, a1, c.r, c.g, c.b, a0);
  }
  const g = new BufferGeometry();
  g.setAttribute("position", new Float32BufferAttribute(pos, 3));
  g.setAttribute("color", new Float32BufferAttribute(col, 4));
  return g;
}

/** A thin flat unit ring (xz plane) to scale to any radius. */
export function unitRing(inner = 0.965): RingGeometry {
  const g = new RingGeometry(inner, 1, 96);
  g.rotateX(-Math.PI / 2);
  return g;
}

export function glowMaterial(
  name: "--flash" | "--afterglow" | "--alert",
  opacity = 1,
): MeshBasicMaterial {
  return new MeshBasicMaterial({
    color: color(name),
    transparent: true,
    opacity,
    blending: AdditiveBlending,
    depthWrite: false,
  });
}
