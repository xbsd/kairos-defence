import { useEffect, useRef } from "react";

import { overlayStore } from "../state/overlayStore";

/**
 * The thin bone beam from the report's zone-road span to that road's in-zone segment in the
 * theater (§17.8): the span's rectangle and the projected road point, both read every frame
 * (requestAnimationFrame writes the line, never React state). Hidden when either end is missing.
 */
export function RecallBeam() {
  const svg = useRef<SVGSVGElement>(null);
  const line = useRef<SVGLineElement>(null);
  const dot = useRef<SVGCircleElement>(null);
  useEffect(() => {
    if (typeof requestAnimationFrame !== "function") return;
    let raf = 0;
    const frame = () => {
      raf = requestAnimationFrame(frame);
      const s = svg.current;
      const l = line.current;
      const d = dot.current;
      if (!s || !l || !d) return;
      const o = overlayStore.getState();
      const span = document.querySelector<HTMLElement>(
        '[data-testid="clue-road"][data-zone="true"]',
      );
      const on = o.road.on && !o.collapsed && span !== null;
      s.style.display = on ? "" : "none";
      s.dataset.on = on ? "true" : "false";
      if (!on || !span) return;
      const box = s.getBoundingClientRect();
      const r = span.getBoundingClientRect();
      const x1 = r.right - box.left;
      const y1 = r.top + r.height / 2 - box.top;
      l.setAttribute("x1", x1.toFixed(1));
      l.setAttribute("y1", y1.toFixed(1));
      l.setAttribute("x2", o.road.x.toFixed(1));
      l.setAttribute("y2", o.road.y.toFixed(1));
      d.setAttribute("cx", o.road.x.toFixed(1));
      d.setAttribute("cy", o.road.y.toFixed(1));
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);
  return (
    <svg
      ref={svg}
      aria-hidden="true"
      data-testid="recall-beam"
      className="pointer-events-none absolute inset-0 z-[15] h-full w-full"
      style={{ display: "none" }}
    >
      <line ref={line} stroke="var(--bone)" strokeWidth={1.6} strokeDasharray="3 3" />
      <circle ref={dot} r={5} fill="none" stroke="var(--bone)" strokeWidth={1.6} />
    </svg>
  );
}
