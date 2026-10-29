import { useCallback, useMemo, useRef } from "react";

import type { CaseGraph as Graph } from "../api/pages";
import { useWidth } from "../lib/useWidth";
import { layoutGraph, toModel, type ModelNode } from "./graphModel";

const H = 460;

function shape(n: ModelNode, x: number, y: number) {
  const stroke = n.contradiction ? "var(--alert)" : n.member ? "var(--verified)" : `var(${n.tone})`;
  switch (n.kind) {
    case "case":
      return (
        <path
          d={`M ${x} ${y - 14} L ${x + 14} ${y} L ${x} ${y + 14} L ${x - 14} ${y} Z`}
          fill="var(--scope)"
          stroke={stroke}
          strokeWidth={1.6}
        />
      );
    case "incident":
      return (
        <circle
          cx={x}
          cy={y}
          r={11}
          fill={`var(${n.tone})`}
          fillOpacity={0.25}
          stroke={stroke}
          strokeWidth={n.member || n.contradiction ? 2.2 : 1.4}
        />
      );
    case "report":
      return (
        <rect
          x={x - 7}
          y={y - 7}
          width={14}
          height={14}
          rx={2}
          fill="var(--scope)"
          stroke="var(--ink-mid)"
        />
      );
    case "assessment":
      return (
        <rect
          x={x - 9}
          y={y - 9}
          width={18}
          height={18}
          rx={9}
          fill="var(--scope)"
          stroke={n.contradiction ? "var(--alert)" : "var(--ink-hi)"}
          strokeWidth={1.4}
        />
      );
  }
}

/** Nodes and links of two graphs together (the head's and the scrubbed one's), first wins. */
function union(
  a: ReturnType<typeof toModel>,
  b: ReturnType<typeof toModel>,
): ReturnType<typeof toModel> {
  const ids = new Set(a.nodes.map((n) => n.id));
  const links = new Set(a.links.map((l) => `${l.kind}|${String(l.source)}|${String(l.target)}`));
  return {
    nodes: [...a.nodes, ...b.nodes.filter((n) => !ids.has(n.id))],
    links: [
      ...a.links,
      ...b.links.filter((l) => !links.has(`${l.kind}|${String(l.source)}|${String(l.target)}`)),
    ],
  };
}

/**
 * The case as a force-directed graph (§17.9): incidents colored by base, reports, assessments
 * and links; members outlined in verified green, contradictions in alert red. The layout is
 * computed once over the head's graph (plus anything only the scrubbed moment has), so a node
 * keeps its place while you scrub; nodes appearing at this moment fade in over 600 ms.
 */
export function CaseGraph({ graph, head, reduce }: { graph: Graph; head: Graph; reduce: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  const width = useWidth(box, 640);
  const model = useMemo(() => toModel(graph), [graph]);
  const headModel = useMemo(() => toModel(head), [head]);
  const pos = useMemo(
    () => layoutGraph(union(headModel, model), width, H),
    [headModel, model, width],
  );
  const nodeById = new Map(model.nodes.map((n) => [n.id, n]));
  const founder = graph.nodes.find((n) => n.kind === "incident")?.id;
  // a stable callback: React calls it only when a node's element mounts (it first appears)
  const fadeIn = useCallback(
    (el: SVGGElement | null) => {
      if (el && !reduce && typeof el.animate === "function")
        el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 600, easing: "ease-out" });
    },
    [reduce],
  );
  return (
    <div ref={box} className="w-full" data-testid="case-graph" data-as-of={graph.as_of}>
      <svg width={width} height={H} viewBox={`0 0 ${width} ${H}`} aria-hidden="true">
        {model.links.map((l) => {
          const s = typeof l.source === "string" ? l.source : l.source.id;
          const t = typeof l.target === "string" ? l.target : l.target.id;
          const a = pos.get(s);
          const b = pos.get(t);
          if (!a || !b) return null;
          const approved = l.kind === "member_of" && nodeById.get(s)?.member && s !== founder;
          const stroke =
            l.kind === "proposed"
              ? "var(--afterglow)"
              : approved
                ? "var(--verified)"
                : l.kind === "member_of"
                  ? "var(--ink-mid)"
                  : "var(--hairline)";
          return (
            <line
              key={`${l.kind}-${s}-${t}-${l.seq}`}
              data-testid="graph-edge"
              data-kind={l.kind}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={stroke}
              strokeWidth={l.kind === "member_of" || l.kind === "proposed" ? 1.6 : 1}
              strokeDasharray={l.kind === "proposed" ? "4 4" : undefined}
            />
          );
        })}
        {model.nodes.map((n) => {
          const p = pos.get(n.id);
          if (!p) return null;
          return (
            <g
              key={n.id}
              data-testid="graph-node"
              data-kind={n.kind}
              data-id={n.id}
              data-label={n.label}
              ref={fadeIn}
            >
              {shape(n, p.x, p.y)}
              <text
                x={p.x}
                y={p.y + (n.kind === "case" ? 30 : 26)}
                textAnchor="middle"
                fontSize={12}
                fill={n.kind === "assessment" ? "var(--ink-hi)" : "var(--ink-mid)"}
              >
                {n.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
