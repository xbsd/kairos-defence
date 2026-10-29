import { useEffect, useMemo, useRef } from "react";

import type { DtwMsg } from "../api/messages";
import type { LensMode } from "../state/matchStore";
import { lensScale, morphConnectors, easeInOut, valueRange, type Pair } from "./lensMath";

const MORPH_MS = 1200; // --dur-cinema
const FADE_MS = 240; // --dur-panel

function polyline(values: readonly number[], x: (k: number) => number, y: (v: number) => number) {
  return values.map((v, k) => `${x(k).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
}

/**
 * Tonight's window (flash) above the matched segment (afterglow) on one time scale, with the
 * connectors: "Same time" joins equal sample indices, "Warped" follows the DTW path. A mode
 * change moves every connector's lower end over 1.2 s (a cross-fade in reduce motion), driven by
 * requestAnimationFrame writing the line attributes, never React state per frame (§17.7, §17.11).
 */
export function LensCurves(props: {
  dtw: DtwMsg;
  mode: LensMode;
  reduce: boolean;
  width: number;
  height: number;
}) {
  const { dtw, mode, reduce, width, height } = props;
  const n = dtw.query.length;
  const m = dtw.candidate.length;
  const geo = useMemo(() => {
    const x = lensScale(n, m, width, 10);
    const [lo, hi] = valueRange(dtw.query, dtw.candidate);
    const band = (height - 28) / 2;
    const yq = (v: number) => 6 + (1 - (v - lo) / (hi - lo)) * (band - 6);
    const yc = (v: number) => height - 22 - (1 - (v - lo) / (hi - lo)) * (band - 6);
    const cs = morphConnectors(dtw.path as Pair[], dtw.overlap);
    return { x, yq, yc, cs };
  }, [dtw, n, m, width, height]);

  const lines = useRef<(SVGLineElement | null)[]>([]);
  const group = useRef<SVGGElement>(null);
  const t = useRef(mode === "warped" ? 1 : 0);

  // place every connector at progress p (0 = same time, 1 = warped)
  const place = (p: number) => {
    const e = easeInOut(p);
    geo.cs.forEach((c, k) => {
      const el = lines.current[k];
      if (!el) return;
      const j = c.j0 + (c.j1 - c.j0) * e;
      const jIdx = Math.min(m - 1, Math.max(0, Math.round(j)));
      const lo = Math.floor(Math.min(m - 1, Math.max(0, j)));
      const hi = Math.min(m - 1, lo + 1);
      const f = j - lo;
      const v = (dtw.candidate[lo] ?? 0) * (1 - f) + (dtw.candidate[hi] ?? 0) * f;
      el.setAttribute("x2", geo.x(j).toFixed(1));
      el.setAttribute("y2", geo.yc(Number.isFinite(v) ? v : (dtw.candidate[jIdx] ?? 0)).toFixed(1));
      // a query sample with no same-time partner shows only as the morph reaches it
      el.setAttribute("opacity", c.same ? "1" : e.toFixed(2));
    });
  };

  useEffect(() => {
    const target = mode === "warped" ? 1 : 0;
    if (reduce || typeof requestAnimationFrame !== "function") {
      const changed = t.current !== target;
      t.current = target;
      place(target);
      const g = group.current;
      if (reduce && changed && g && typeof g.animate === "function")
        g.animate([{ opacity: 0 }, { opacity: 1 }], { duration: FADE_MS, easing: "ease-out" });
      return;
    }
    const from = t.current;
    if (from === target) {
      place(target);
      return;
    }
    const t0 = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const u = Math.min(1, (now - t0) / MORPH_MS);
      t.current = from + (target - from) * u;
      place(t.current);
      if (u < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
    // place depends on geo (in deps through dtw/size)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, reduce, geo]);

  const { x, yq, yc, cs } = geo;
  const warped = mode === "warped";
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Tonight's window above the matched flight, connectors in ${
        warped ? "warped" : "same-time"
      } mode`}
      data-testid="lens-curves"
      data-mode={mode}
    >
      <g ref={group} stroke="var(--ink-mid)" strokeWidth={0.8} strokeOpacity={0.55}>
        {cs.map((c, k) => (
          <line
            key={`${c.i}-${c.j1}-${k}`}
            ref={(el) => {
              lines.current[k] = el;
            }}
            data-testid="lens-connector"
            data-i={c.i}
            data-j={warped ? c.j1 : c.j0}
            data-shown={warped || c.same ? "true" : "false"}
            x1={x(c.i)}
            y1={yq(dtw.query[c.i] ?? 0)}
            x2={x(warped ? c.j1 : c.j0)}
            y2={yc(dtw.candidate[Math.min(m - 1, warped ? c.j1 : c.j0)] ?? 0)}
          />
        ))}
      </g>
      <polyline
        points={polyline(dtw.query, x, yq)}
        fill="none"
        stroke="var(--flash)"
        strokeWidth={1.8}
      />
      <polyline
        points={polyline(dtw.candidate, x, yc)}
        fill="none"
        stroke="var(--afterglow)"
        strokeWidth={1.8}
      />
      <text x={10} y={height - 4} fill="var(--ink-mid)" fontSize={12}>
        Tonight above, the matched flight below, on one time scale
      </text>
    </svg>
  );
}
