// Pure helpers for the live theater (SPEC §17.3, D-109). Scene frame: 1 unit = 1 m, origin =
// installation origin, x_m → x (east), y_m → −z (north is −z), altitude → y. No rotation.
// Bearings are degrees clockwise from north in [0, 360).

export type Vec3 = [number, number, number];
export type Vec2 = [number, number];

export interface Origin {
  x: number;
  y: number;
}

/** Region meters (and altitude) to scene coordinates. */
export function toScene(x_m: number, y_m: number, alt: number, origin: Origin): Vec3 {
  return [x_m - origin.x, alt, -(y_m - origin.y)];
}

export function wrap360(deg: number): number {
  return ((deg % 360) + 360) % 360;
}

/** Bearing from one region-frame point to another (clockwise from north). */
export function bearingDeg(from: Vec2, to: Vec2): number {
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  return wrap360((Math.atan2(dx, dy) * 180) / Math.PI);
}

/** A horizontal unit vector in scene space along a bearing. */
export function bearingVector(deg: number): Vec3 {
  const r = (deg * Math.PI) / 180;
  return [Math.sin(r), 0, -Math.cos(r)];
}

/** three.js rotation about +y that points the local −z axis along a bearing. */
export function bearingToYaw(deg: number): number {
  return (-deg * Math.PI) / 180;
}

/**
 * Radar sweep angle (§17.3): the bearing of the last detection, advanced 360° × rate per second
 * of replay time since it. The beam crosses the drone at each real detection and stands still
 * while the replay is paused (the clock does not move).
 */
export function sweepAngleDeg(
  detBearing: number,
  rateHz: number,
  clock: number,
  detT: number,
): number {
  return wrap360(detBearing + 360 * rateHz * Math.max(0, clock - detT));
}

/** A point on a quadratic arc from a to b that rises `lift` meters above the chord at its middle. */
export function arcPoint(a: Vec3, b: Vec3, t: number, lift: number): Vec3 {
  const u = Math.min(Math.max(t, 0), 1);
  const c: Vec3 = [(a[0] + b[0]) / 2, Math.max(a[1], b[1]) + lift, (a[2] + b[2]) / 2];
  const w0 = (1 - u) * (1 - u);
  const w1 = 2 * (1 - u) * u;
  const w2 = u * u;
  return [
    w0 * a[0] + w1 * c[0] + w2 * b[0],
    w0 * a[1] + w1 * c[1] + w2 * b[1],
    w0 * a[2] + w1 * c[2] + w2 * b[2],
  ];
}

export const PACKET_LEG1_S = 0.9; // detection → detecting sensor
export const PACKET_LEG2_S = 0.6; // sensor → Kairos core

/** Where a data packet is `age` wall seconds after its detection; null once it has arrived. */
export function packetPosition(from: Vec3, sensor: Vec3, core: Vec3, age: number): Vec3 | null {
  if (age < 0 || age > PACKET_LEG1_S + PACKET_LEG2_S) return null;
  if (age <= PACKET_LEG1_S) {
    const lift = 0.15 * Math.hypot(sensor[0] - from[0], sensor[2] - from[2]);
    return arcPoint(from, sensor, age / PACKET_LEG1_S, lift);
  }
  const lift = 0.2 * Math.hypot(core[0] - sensor[0], core[2] - sensor[2]);
  return arcPoint(sensor, core, (age - PACKET_LEG1_S) / PACKET_LEG2_S, lift);
}

export const TRAIL_S = 60;

/** Phosphor trail: 1 at the newest point, 0 for points 60 replay seconds old. */
export function trailAlpha(age_s: number): number {
  return Math.min(1, Math.max(0, 1 - age_s / TRAIL_S));
}

export const RF_RING_M = 300;
export const RF_RING_S = 1.2;

/** RF ring radius: 0 → 300 m over 1.2 s after the detection (null outside that window). */
export function rfRingRadius(age_s: number): number | null {
  if (age_s < 0 || age_s > RF_RING_S) return null;
  return (RF_RING_M * age_s) / RF_RING_S;
}

/** The unknown-track quatrefoil frame (MIL-STD-2525 inspired): four lobes, unit size. */
export function quatrefoil(n = 96, r = 1): Vec2[] {
  const out: Vec2[] = [];
  for (let i = 0; i <= n; i++) {
    const th = (i / n) * 2 * Math.PI;
    const rad = r * (0.72 + 0.28 * Math.cos(4 * th));
    out.push([rad * Math.sin(th), rad * Math.cos(th)]);
  }
  return out;
}

/** World size that appears `px` pixels tall at distance `dist` (perspective camera). */
export function screenScale(dist: number, fovDeg: number, viewportPx: number, px: number): number {
  const h = 2 * dist * Math.tan((fovDeg * Math.PI) / 360);
  return (h * px) / Math.max(1, viewportPx);
}

/** Hatch segments (region meters) inside a polygon: parallel lines `spacing` apart at `angleDeg`. */
export function hatchSegments(poly: Vec2[], spacing: number, angleDeg = 45): [Vec2, Vec2][] {
  if (poly.length < 3) return [];
  const a = (angleDeg * Math.PI) / 180;
  const [c, s] = [Math.cos(a), Math.sin(a)];
  // rotate into a frame where hatch lines are horizontal: v = −x·s + y·c
  const rot = poly.map(([x, y]) => [x * c + y * s, -x * s + y * c] as Vec2);
  const vs = rot.map((p) => p[1]);
  const out: [Vec2, Vec2][] = [];
  const lo = Math.ceil(Math.min(...vs) / spacing) * spacing;
  for (let v = lo; v <= Math.max(...vs); v += spacing) {
    const xs: number[] = [];
    for (let i = 0; i < rot.length; i++) {
      const p = rot[i] as Vec2;
      const q = rot[(i + 1) % rot.length] as Vec2;
      if (p[1] === q[1] || v < Math.min(p[1], q[1]) || v >= Math.max(p[1], q[1])) continue;
      xs.push(p[0] + ((v - p[1]) / (q[1] - p[1])) * (q[0] - p[0]));
    }
    xs.sort((m, n) => m - n);
    for (let i = 0; i + 1 < xs.length; i += 2) {
      const u0 = xs[i] as number;
      const u1 = xs[i + 1] as number;
      out.push([
        [u0 * c - v * s, u0 * s + v * c],
        [u1 * c - v * s, u1 * s + v * c],
      ]);
    }
  }
  return out;
}

/** The mean of a ring's vertices (the closing vertex counted once). */
export function ringCenter(poly: Vec2[]): Vec2 {
  const pts = poly.length > 1 && poly[0]?.[0] === poly.at(-1)?.[0] ? poly.slice(0, -1) : poly;
  const n = Math.max(1, pts.length);
  return [pts.reduce((a, p) => a + p[0], 0) / n, pts.reduce((a, p) => a + p[1], 0) / n];
}

/** The Kairos core: 2.4 km south-east of the origin, 120 m up (D-112). */
export const CORE_POSITION: Vec3 = [2400 * Math.SQRT1_2, 120, 2400 * Math.SQRT1_2];

/** Asset heights by kind, meters (presentation constants, §17.3: 6–20 m). */
export const ASSET_HEIGHT_M: Record<string, number> = {
  hq: 20,
  housing: 9,
  fuel_farm: 12,
  flight_line: 6,
  munitions: 8,
};

export function assetLabel(kind: string): string {
  if (kind === "hq") return "HQ";
  const s = kind.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
