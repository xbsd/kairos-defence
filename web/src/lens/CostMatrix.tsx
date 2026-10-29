import { useEffect, useMemo, useRef } from "react";

import type { DtwMsg } from "../api/messages";
import { token } from "../theme/colors";
import { costRange, decodeCost, pathCells, type Pair } from "./lensMath";
import { costPixels, lensRamp } from "./ramp";

const DRAW_MS = 1000; // the path draws on over 1 s (§17.7)

/**
 * The accumulated DTW cost matrix (≤ 128 × 128 cells) on a canvas: a perceptual ramp from scope
 * glass to afterglow inside the Sakoe-Chiba band (cells outside it stay clear, a faint corridor),
 * and the optimal path drawn on over 1 s with a glowing head; instant in reduce motion.
 */
export function CostMatrix(props: { dtw: DtwMsg; reduce: boolean; height: number }) {
  const { dtw, reduce, height } = props;
  const [n, m] = dtw.shape;
  const ref = useRef<HTMLCanvasElement>(null);
  const cells = useMemo(() => decodeCost(dtw.cost, [n, m]), [dtw.cost, n, m]);
  const pts = useMemo(() => pathCells(dtw.path as Pair[]), [dtw.path]);

  useEffect(() => {
    const c = ref.current;
    const ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    const scale = 4; // crisp cells and a smooth path
    c.width = m * scale;
    c.height = n * scale;
    const [lo, hi] = costRange(cells);
    const base = document.createElement("canvas");
    base.width = m;
    base.height = n;
    const bctx = base.getContext("2d");
    if (bctx && typeof ImageData !== "undefined") {
      bctx.putImageData(new ImageData(costPixels(cells, lo, hi, lensRamp()), m, n), 0, 0);
    }
    const drawUpTo = (u: number) => {
      ctx.clearRect(0, 0, c.width, c.height);
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(base, 0, 0, c.width, c.height);
      const k = Math.max(1, Math.round(u * pts.length));
      ctx.strokeStyle = token("--ink-hi");
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      pts.slice(0, k).forEach(([x, y], idx) => {
        if (idx === 0) ctx.moveTo(x * scale, y * scale);
        else ctx.lineTo(x * scale, y * scale);
      });
      ctx.stroke();
      const head = pts[k - 1];
      if (head && u < 1) {
        ctx.fillStyle = token("--flash");
        ctx.globalAlpha = 0.9;
        ctx.beginPath();
        ctx.arc(head[0] * scale, head[1] * scale, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
      }
    };
    if (reduce || typeof requestAnimationFrame !== "function") {
      drawUpTo(1);
      return;
    }
    const t0 = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const u = Math.min(1, (now - t0) / DRAW_MS);
      drawUpTo(u);
      if (u < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [cells, pts, n, m, reduce]);

  return (
    <figure className="flex min-h-0 flex-col gap-1">
      <canvas
        ref={ref}
        data-testid="cost-matrix"
        data-shape={`${n}x${m}`}
        data-band={dtw.band}
        data-path-length={dtw.path.length}
        aria-label={`Cost matrix, ${n} by ${m} cells, band ${dtw.band}, the optimal path drawn on`}
        role="img"
        className="block w-full rounded-button border border-hairline"
        style={{ height, imageRendering: "pixelated" }}
      />
      <figcaption className="text-12 text-ink-mid">
        Cost matrix: tonight down, the matched flight across; the path is the best alignment
      </figcaption>
    </figure>
  );
}
