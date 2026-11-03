import type { TraceDetail } from "../api/messages";
import { lensRamp } from "../lens/ramp";
import { valueAt } from "./workbenchMachine";

const W = 320;
const H = 132;
const PAD = 6;

function points(curve: (number | null)[], lo: number, hi: number, y0: number, h: number): string {
  const n = curve.length;
  const span = hi - lo || 1;
  return curve
    .map((v, k) => {
      if (v === null) return null;
      const x = PAD + (n > 1 ? (k / (n - 1)) * (W - 2 * PAD) : 0);
      const y = y0 + h - ((v - lo) / span) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter((p) => p !== null)
    .join(" ");
}

/** Tonight's curve above the candidate's, each aligned pair of samples joined along the warping
 * path (§17.7's connectors, from the trace's path: indices into the full n × m matrix). */
export function TraceCurves(props: {
  query: (number | null)[];
  detail: TraceDetail;
  n: number;
  m: number;
  label: string;
}) {
  const vals = [...props.query, ...props.detail.curve].filter((v): v is number => v !== null);
  const lo = vals.length ? Math.min(...vals) : 0;
  const hi = vals.length ? Math.max(...vals) : 1;
  const top = PAD;
  const band = (H - 4 * PAD) / 2;
  const bottom = top + band + 2 * PAD;
  const qf = (i: number) => (props.n > 1 ? i / (props.n - 1) : 0);
  const cf = (j: number) => (props.m > 1 ? j / (props.m - 1) : 0);
  const X = (f: number) => PAD + f * (W - 2 * PAD);
  const span = hi - lo || 1;
  const Y = (v: number, y0: number) => y0 + band - ((v - lo) / span) * band;
  const links = props.detail.path.flatMap(([i = 0, j = 0], k) => {
    const vq = valueAt(props.query, qf(i));
    const vc = valueAt(props.detail.curve, cf(j));
    if (vq === null || vc === null) return [];
    return [{ k, x1: X(qf(i)), y1: Y(vq, top), x2: X(cf(j)), y2: Y(vc, bottom) }];
  });
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full"
      role="img"
      aria-label={props.label}
      data-testid="workbench-curves"
    >
      {links.map((l) => (
        <line
          key={l.k}
          x1={l.x1}
          y1={l.y1}
          x2={l.x2}
          y2={l.y2}
          className="stroke-ink-low"
          strokeWidth={0.6}
        />
      ))}
      <polyline
        points={points(props.query, lo, hi, top, band)}
        className="fill-none stroke-flash"
        strokeWidth={1.6}
      />
      <polyline
        points={points(props.detail.curve, lo, hi, bottom, band)}
        className="fill-none stroke-afterglow"
        strokeWidth={1.6}
      />
    </svg>
  );
}

/** The accumulated cost matrix as a 12 × 12 thumbnail (block minimum, from the trace) with the
 * warping path drawn on it. The path is the full-matrix alignment with relaxed ends, so no band
 * is drawn (D-069, D-189). */
export function CostThumb(props: { detail: TraceDetail; n: number; m: number; label: string }) {
  const cells = props.detail.cost;
  const k = cells.length || 1;
  const vals = cells.flat().filter((v): v is number => v !== null);
  const lo = vals.length ? Math.min(...vals) : 0;
  const hi = vals.length ? Math.max(...vals) : 1;
  const ramp = lensRamp();
  const size = 120;
  const c = size / k;
  const path = props.detail.path
    .map(([i, j]) => {
      const x = ((j ?? 0) / Math.max(1, props.m - 1)) * size;
      const y = ((i ?? 0) / Math.max(1, props.n - 1)) * size;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="h-auto w-full max-w-[9rem]"
      role="img"
      aria-label={props.label}
      data-testid="workbench-cost"
    >
      {cells.map((row, r) =>
        row.map((v, col) => {
          const t = v === null ? 1 : (v - lo) / (hi - lo || 1);
          const [R, G, B] = ramp(Math.sqrt(Math.min(1, Math.max(0, t))));
          return (
            <rect
              key={`${r}:${col}`}
              x={col * c}
              y={r * c}
              width={c + 0.2}
              height={c + 0.2}
              fill={v === null ? "transparent" : `rgb(${R} ${G} ${B})`}
            />
          );
        }),
      )}
      <polyline
        points={path}
        className="fill-none stroke-flash"
        strokeWidth={1.6}
        data-testid="workbench-path"
      />
    </svg>
  );
}
