// Region constellation layout (SPEC §17.8, D-130): the live region's installations placed by
// their real origins (region meters, north up), scaled into the panel with padding; matched bases
// in another region gather at an "Other regions" node on the panel's edge.
import type { Installation, MatchItem } from "../api/messages";
import { baseName, localDate } from "../lib/format";

export const OTHER = "OTHER";

export interface StarNode {
  id: string;
  name: string;
  x: number;
  y: number;
  live: boolean;
  matched: boolean;
}

export interface Arc {
  from: string;
  to: string;
  /** "Apr 19" (one per matched flight from that base). */
  label: string;
  incidents: string[];
}

export interface Constellation {
  nodes: StarNode[];
  arcs: Arc[];
}

export function layout(
  installations: Installation[],
  liveId: string,
  matches: MatchItem[],
  width: number,
  height: number,
  pad = 26,
): Constellation {
  const live = installations.find((i) => i.installation_id === liveId);
  if (!live) return { nodes: [], arcs: [] };
  const region = installations.filter((i) => i.region_id === live.region_id);
  const xs = region.map((i) => i.origin_x_m);
  const ys = region.map((i) => i.origin_y_m);
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
  const sx = (width - 2 * pad) / Math.max(1, x1 - x0);
  const sy = (height - 2 * pad) / Math.max(1, y1 - y0);
  // stylized: the short panel may stretch east-west up to 2.5 times, never more
  const s = Math.min(sx, sy);
  const kx = Math.min(sx, 2.5 * s);
  const ox = pad + (width - 2 * pad - kx * (x1 - x0)) / 2;
  const oy = pad + (height - 2 * pad - s * (y1 - y0)) / 2;
  const matchedBases = new Set(matches.map((m) => m.installation_id));
  const nodes: StarNode[] = region.map((i) => ({
    id: i.installation_id,
    name: baseName(i.installation_id),
    x: ox + kx * (i.origin_x_m - x0),
    y: oy + s * (y1 - i.origin_y_m), // north up
    live: i.installation_id === liveId,
    matched: matchedBases.has(i.installation_id),
  }));
  const regionIds = new Set(region.map((i) => i.installation_id));
  const others = matches.filter((m) => !regionIds.has(m.installation_id));
  if (others.length)
    nodes.push({
      id: OTHER,
      name: "Other regions",
      x: width - pad / 2,
      y: pad / 2,
      live: false,
      matched: true,
    });
  const byBase = new Map<string, MatchItem[]>();
  for (const m of matches) {
    const key = regionIds.has(m.installation_id) ? m.installation_id : OTHER;
    byBase.set(key, [...(byBase.get(key) ?? []), m]);
  }
  const arcs: Arc[] = [...byBase.entries()].map(([from, ms]) => ({
    from,
    to: liveId,
    label: ms.map((m) => localDate(m.local_start)).join(", "),
    incidents: ms.map((m) => m.incident_id),
  }));
  return { nodes, arcs };
}

/** A gentle quadratic arc between two nodes (SVG path data); a self-arc loops above the node. */
export function arcPath(a: StarNode, b: StarNode): string {
  if (a.id === b.id) {
    return `M ${a.x - 6} ${a.y - 4} C ${a.x - 22} ${a.y - 40}, ${a.x + 22} ${a.y - 40}, ${a.x + 6} ${a.y - 4}`;
  }
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const bend = Math.min(40, len * 0.25);
  const cx = mx - (dy / len) * bend;
  const cy = my + (dx / len) * bend;
  return `M ${a.x.toFixed(1)} ${a.y.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
}
