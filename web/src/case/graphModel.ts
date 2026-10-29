// The Case board's graph (SPEC §17.9, D-138): the API's nodes and edges as drawable items, and a
// deterministic d3-force layout (seeded start positions, a fixed random source, 300 synchronous
// ticks), so the same graph always lands in the same place.
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY } from "d3";
import type { SimulationLinkDatum, SimulationNodeDatum } from "d3";

import type { CaseGraph, GraphEdge, GraphNode } from "../api/pages";
import type { ColorToken } from "../theme/colors";

/** Base tones, assigned by base id in sorted order (tokens only, D-021). */
export const BASE_TONES: ColorToken[] = ["--afterglow", "--bone", "--flash", "--ink-hi"];

export interface ModelNode extends SimulationNodeDatum {
  id: string;
  kind: GraphNode["kind"];
  label: string;
  tone: ColorToken;
  member: boolean;
  contradiction: boolean;
  base: string | null;
  recorded_at: string | null;
}

export interface ModelLink extends SimulationLinkDatum<ModelNode> {
  source: string | ModelNode;
  target: string | ModelNode;
  kind: GraphEdge["kind"];
  seq: number;
}

export function baseTones(nodes: GraphNode[]): Record<string, ColorToken> {
  const bases = [...new Set(nodes.map((n) => n.base).filter((b): b is string => !!b))].sort();
  return Object.fromEntries(
    bases.map((b, i) => [b, BASE_TONES[i % BASE_TONES.length] as ColorToken]),
  );
}

function label(n: GraphNode): string {
  switch (n.kind) {
    case "case":
      return `${n.id} (${n.status ?? "?"})`;
    case "incident":
      return n.id;
    case "report":
      return n.id;
    case "assessment":
      return n.label ?? "assessment";
  }
}

export function toModel(g: CaseGraph): { nodes: ModelNode[]; links: ModelLink[] } {
  const tones = baseTones(g.nodes);
  const nodes = g.nodes.map<ModelNode>((n) => ({
    id: n.id,
    kind: n.kind,
    label: label(n),
    tone:
      n.kind === "incident" && n.base
        ? (tones[n.base] ?? "--ink-hi")
        : n.kind === "case"
          ? "--ink-hi"
          : "--ink-mid",
    member: n.member === true,
    contradiction: n.contradiction === true,
    base: n.base ?? null,
    recorded_at: n.recorded_at,
  }));
  const ids = new Set(nodes.map((n) => n.id));
  const links = g.edges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map<ModelLink>((e) => ({ source: e.source, target: e.target, kind: e.kind, seq: e.seq }));
  return { nodes, links };
}

/** A small linear congruential generator in [0, 1): d3's random source, seeded (rule 4). */
export function lcg(seed = 42): () => number {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

const RING: Record<GraphNode["kind"], number> = {
  case: 0,
  incident: 0.42,
  report: 0.8,
  assessment: 0.68,
};
const PHASE: Record<GraphNode["kind"], number> = {
  case: 0,
  incident: 0.2,
  report: 1.4,
  assessment: 2.6,
};

/**
 * Positions for every node in a `width` × `height` box. Nodes already placed (`prev`) start where
 * they were, so a rescrub moves little; new ones start on a ring by kind and index.
 */
export function layoutGraph(
  m: { nodes: ModelNode[]; links: ModelLink[] },
  width: number,
  height: number,
  prev: Map<string, { x: number; y: number }> = new Map(),
): Map<string, { x: number; y: number }> {
  const cx = width / 2;
  const cy = height / 2;
  const R = Math.min(width, height) / 2;
  const byKind: Record<string, number> = {};
  const nodes = m.nodes.map((n) => {
    const k = (byKind[n.kind] = (byKind[n.kind] ?? 0) + 1) - 1;
    const p = prev.get(n.id);
    const a = PHASE[n.kind] + k * 0.9;
    return {
      ...n,
      x: p?.x ?? cx + RING[n.kind] * R * Math.cos(a),
      y: p?.y ?? cy + RING[n.kind] * R * Math.sin(a),
      ...(n.kind === "case" ? { fx: cx, fy: cy } : {}),
    };
  });
  const links = m.links.map((l) => ({ ...l }));
  const sim = forceSimulation(nodes)
    .randomSource(lcg(7))
    .force(
      "link",
      forceLink<ModelNode, ModelLink>(links)
        .id((d) => d.id)
        .distance((l) => (l.kind === "member_of" || l.kind === "proposed" ? R * 0.62 : R * 0.42))
        .strength(0.6),
    )
    .force("charge", forceManyBody().strength(-520))
    .force("collide", forceCollide(58))
    .force("x", forceX(cx).strength(0.04))
    .force("y", forceY(cy).strength(0.06))
    .stop();
  for (let i = 0; i < 300; i++) sim.tick();
  const pad = 40;
  return new Map(
    nodes.map((n) => [
      n.id,
      {
        x: Math.min(width - pad, Math.max(pad, n.x ?? cx)),
        y: Math.min(height - pad, Math.max(pad, n.y ?? cy)),
      },
    ]),
  );
}
