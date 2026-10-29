import { useEffect, useRef } from "react";

import { revealOf } from "../director/engine";
import { useThrottledStore } from "../lib/useThrottledStore";
import { useWidth } from "../lib/useWidth";
import { directorStore } from "../state/directorStore";
import { matchStore } from "../state/matchStore";
import { replayStore } from "../state/replayStore";
import { sceneStore } from "../state/sceneStore";
import { reduceMotion, uiStore } from "../state/uiStore";
import { arcPath, layout } from "./constellation";
import { Panel } from "./Panel";

/** 150 px at 1920 wide, 116 px below (the rail's height budget at 1440 × 900, D-145). */
function railHeight(): number {
  return typeof window !== "undefined" && window.innerWidth < 1536 ? 116 : 150;
}
const DRAW_MS = 1200;

/**
 * Stylized positions of the live region's installations (§17.8). On a new top-3 set, arcs draw
 * from each matched base to the live base with a travelling light (1.2 s), labeled with the
 * match dates; plain arcs in reduce motion.
 */
export function RegionConstellation() {
  const box = useRef<HTMLDivElement>(null);
  const width = useWidth(box, 360);
  const HEIGHT = railHeight();
  const m = useThrottledStore(matchStore, (s) => ({ match: s.match, entrance: s.entrance }), 4);
  const live = useThrottledStore(replayStore, (s) => s.hello?.installation_id ?? null, 2);
  const installations = useThrottledStore(sceneStore, (s) => s.installations, 2);
  const shown = useThrottledStore(directorStore, (d) => revealOf(d.active, d.beat).lens, 4);
  const reduce = useThrottledStore(uiStore, reduceMotion);
  const top = shown ? (m.match?.matches.slice(0, 3) ?? []) : [];
  const c = live ? layout(installations, live, top, width, HEIGHT) : { nodes: [], arcs: [] };
  const byId = new Map(c.nodes.map((n) => [n.id, n]));
  const dates = new Map(c.arcs.map((a) => [a.from, a.label]));
  const svg = useRef<SVGSVGElement>(null);

  // the travelling light: draw each arc on, a dot riding its head (Web Animations, no state)
  useEffect(() => {
    const root = svg.current;
    if (!root || reduce) return;
    const paths = Array.from(root.querySelectorAll<SVGPathElement>("path[data-arc]"));
    const anims: Animation[] = [];
    paths.forEach((p, k) => {
      const len = typeof p.getTotalLength === "function" ? p.getTotalLength() : 0;
      if (!len || typeof p.animate !== "function") return;
      p.style.strokeDasharray = `${len}`;
      anims.push(
        p.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], {
          duration: DRAW_MS,
          delay: k * 120,
          easing: "cubic-bezier(0.65, 0, 0.35, 1)",
          fill: "backwards",
        }),
      );
      const dot = root.querySelector<SVGCircleElement>(`circle[data-light="${p.dataset.arc}"]`);
      if (dot && typeof dot.animate === "function") {
        const frames = Array.from({ length: 13 }, (_, i) => {
          const pt = p.getPointAtLength((i / 12) * len);
          return { transform: `translate(${pt.x}px, ${pt.y}px)`, opacity: i === 12 ? 0 : 1 };
        });
        anims.push(dot.animate(frames, { duration: DRAW_MS, delay: k * 120, fill: "both" }));
      }
    });
    return () => anims.forEach((a) => a.cancel());
  }, [m.entrance, shown, reduce, width]);

  return (
    <Panel
      id="constellation"
      title="Region constellation"
      meta={live ? `Arcs to ${live.charAt(0)}${live.slice(1).toLowerCase()}` : undefined}
    >
      <div ref={box} className="w-full px-1" style={{ height: HEIGHT }} data-testid="constellation">
        <svg
          ref={svg}
          width={width}
          height={HEIGHT}
          viewBox={`0 0 ${width} ${HEIGHT}`}
          role="img"
          aria-label={
            c.arcs.length
              ? `Matched flights from ${c.arcs.map((a) => `${byId.get(a.from)?.name ?? a.from} (${a.label})`).join(", ")} link to ${live ?? "this base"}`
              : "The region's installations; arcs appear when matches arrive"
          }
        >
          {c.arcs.map((a) => {
            const from = byId.get(a.from);
            const to = byId.get(a.to);
            if (!from || !to) return null;
            return (
              <g key={`${m.entrance}-${a.from}`}>
                <path
                  data-arc={a.from}
                  data-testid="constellation-arc"
                  d={arcPath(from, to)}
                  fill="none"
                  stroke="var(--afterglow)"
                  strokeOpacity={0.75}
                  strokeWidth={1.4}
                />
                {reduce ? null : (
                  <circle data-light={a.from} r={3} fill="var(--afterglow)" opacity={0} />
                )}
              </g>
            );
          })}
          {c.nodes.map((n) => (
            <g key={n.id} transform={`translate(${n.x.toFixed(1)} ${n.y.toFixed(1)})`}>
              <circle
                r={n.live ? 5 : 4}
                fill={n.live ? "var(--flash)" : n.matched ? "var(--afterglow)" : "none"}
                stroke={n.live ? "var(--flash)" : n.matched ? "var(--afterglow)" : "var(--ink-mid)"}
                strokeWidth={1.2}
              />
              <text
                x={0}
                y={n.y > HEIGHT - 30 ? -9 : 17}
                textAnchor={n.x > width - 90 ? "end" : n.x < 70 ? "start" : "middle"}
                fontSize={12}
                fill={n.live || n.matched ? "var(--ink-hi)" : "var(--ink-mid)"}
              >
                {/* one line per base: its name and the dates of the matched flights from it */}
                {dates.get(n.id) ? `${n.name}, ${dates.get(n.id)}` : n.name}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </Panel>
  );
}
