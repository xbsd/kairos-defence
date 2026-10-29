// Eval charts (SPEC §17.9, D-140), plain SVG inside the §17.1 tokens, following the dataviz
// method: one axis, thin marks, a legend plus direct labels for two series, text in ink tokens,
// a native tooltip (<title>) on every mark and a table view for each chart. The token pair fails
// the validator's lightness band and chroma floor but passes CVD separation (ΔE 17), so series
// also differ by dash and marker shape.
import type { Bin } from "./evalView";

const W = 520;
const H = 240;
const M = { l: 44, r: 112, t: 14, b: 36 };

function Axis(props: {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  xTicks: { v: number; at: number; label: string }[];
  yTicks: { at: number; label: string }[];
  xLabel: string;
}) {
  return (
    <g fontSize={12} fill="var(--ink-mid)">
      {props.yTicks.map((t) => (
        <g key={`y${t.label}`}>
          <line x1={props.x0} x2={props.x1} y1={t.at} y2={t.at} stroke="var(--hairline)" />
          <text x={props.x0 - 6} y={t.at + 4} textAnchor="end">
            {t.label}
          </text>
        </g>
      ))}
      {props.xTicks.map((t) => (
        <text key={`x${t.v}`} x={t.at} y={props.y0 + 16} textAnchor="middle">
          {t.label}
        </text>
      ))}
      <line x1={props.x0} x2={props.x1} y1={props.y0} y2={props.y0} stroke="var(--ink-low)" />
      <text x={(props.x0 + props.x1) / 2} y={H - 4} textAnchor="middle">
        {props.xLabel}
      </text>
    </g>
  );
}

/** Recall@5 and top 3 for probers against seconds of flight (two series, one axis). */
export function RecallChart({ series }: { series: { t: number; r5: number; top3: number }[] }) {
  if (!series.length) return <p className="text-13 text-ink-mid">No recall rows in this report.</p>;
  const t0 = Math.min(...series.map((s) => s.t));
  const t1 = Math.max(...series.map((s) => s.t));
  const x = (t: number) => M.l + ((t - t0) / Math.max(1, t1 - t0)) * (W - M.l - M.r);
  const y = (v: number) => H - M.b - v * (H - M.t - M.b);
  const line = (k: "r5" | "top3") =>
    series.map((s) => `${x(s.t).toFixed(1)},${y(s[k]).toFixed(1)}`).join(" ");
  const last = series[series.length - 1] as { t: number; r5: number; top3: number };
  const close = Math.abs(last.r5 - last.top3) < 0.06;
  return (
    <figure className="flex flex-col gap-2" data-testid="chart-recall">
      <ul className="flex gap-4 text-12 text-ink-mid" aria-label="Legend">
        <li className="flex items-center gap-1.5">
          <svg width={22} height={8} aria-hidden="true">
            <line x1={0} x2={22} y1={4} y2={4} stroke="var(--afterglow)" strokeWidth={2} />
          </svg>
          Recall@5
        </li>
        <li className="flex items-center gap-1.5">
          <svg width={22} height={8} aria-hidden="true">
            <line
              x1={0}
              x2={22}
              y1={4}
              y2={4}
              stroke="var(--ink-mid)"
              strokeWidth={2}
              strokeDasharray="5 3"
            />
          </svg>
          True actor in the top 3
        </li>
      </ul>
      <svg
        width="100%"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Recall against seconds of flight, probers"
      >
        <Axis
          x0={M.l}
          x1={W - M.r}
          y0={H - M.b}
          y1={M.t}
          xTicks={series.map((s) => ({ v: s.t, at: x(s.t), label: `${s.t}` }))}
          yTicks={[0, 0.5, 1].map((v) => ({ at: y(v), label: v.toFixed(1) }))}
          xLabel="Seconds of flight since first radar contact"
        />
        <polyline
          points={line("top3")}
          fill="none"
          stroke="var(--ink-mid)"
          strokeWidth={2}
          strokeDasharray="5 3"
        />
        <polyline points={line("r5")} fill="none" stroke="var(--afterglow)" strokeWidth={2} />
        {series.map((s) => (
          <g key={s.t}>
            <rect
              x={x(s.t) - 4}
              y={y(s.top3) - 4}
              width={8}
              height={8}
              fill="var(--scope)"
              stroke="var(--ink-mid)"
              strokeWidth={2}
            >
              <title>{`T = ${s.t} s: top 3 ${s.top3.toFixed(2)}`}</title>
            </rect>
            <circle
              cx={x(s.t)}
              cy={y(s.r5)}
              r={4.5}
              fill="var(--afterglow)"
              stroke="var(--scope)"
              strokeWidth={2}
            >
              <title>{`T = ${s.t} s: Recall@5 ${s.r5.toFixed(2)}`}</title>
            </circle>
          </g>
        ))}
        <text
          x={x(last.t) + 10}
          y={y(last.r5) + (close ? -4 : 4)}
          fontSize={12}
          fill="var(--ink-hi)"
        >
          Recall@5 {last.r5.toFixed(2)}
        </text>
        <text
          x={x(last.t) + 10}
          y={y(last.top3) + (close ? 12 : 4)}
          fontSize={12}
          fill="var(--ink-mid)"
        >
          Top 3 {last.top3.toFixed(2)}
        </text>
      </svg>
      <details className="text-12 text-ink-mid">
        <summary className="cursor-pointer">Table</summary>
        <table className="mt-1 text-left">
          <thead>
            <tr>
              <th scope="col" className="pr-4">
                T (s)
              </th>
              <th scope="col" className="pr-4">
                Recall@5
              </th>
              <th scope="col">Top 3</th>
            </tr>
          </thead>
          <tbody className="font-mono text-ink-hi">
            {series.map((s) => (
              <tr key={s.t}>
                <td className="pr-4">{s.t}</td>
                <td className="pr-4">{s.r5.toFixed(3)}</td>
                <td>{s.top3.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

/** DTW against Euclidean: Recall@5 at T = 120 s for the same candidates (one measure, two bars). */
export function LiftChart({
  dtw,
  euclid,
  lift,
}: {
  dtw: number | null;
  euclid: number | null;
  lift: number | null;
}) {
  if (dtw === null || euclid === null)
    return <p className="text-13 text-ink-mid">This report has no baseline comparison.</p>;
  const rows: [string, number, string][] = [
    ["DTW and fusion", dtw, "var(--afterglow)"],
    ["Euclidean order", euclid, "var(--ink-mid)"],
  ];
  const bw = 280;
  return (
    <figure className="flex flex-col gap-2" data-testid="chart-lift">
      <svg
        width="100%"
        viewBox="0 0 460 110"
        role="img"
        aria-label={`Recall@5 at T = 120 s: DTW ${dtw.toFixed(2)}, Euclidean ${euclid.toFixed(2)}`}
      >
        {rows.map(([name, v, c], i) => (
          <g key={name} transform={`translate(0 ${10 + i * 44})`}>
            <text x={0} y={18} fontSize={13} fill="var(--ink-hi)">
              {name}
            </text>
            <rect x={130} y={4} width={bw} height={20} rx={4} fill="var(--hairline)" />
            <rect x={130} y={4} width={Math.max(4, v * bw)} height={20} rx={4} fill={c}>
              <title>{`${name}: Recall@5 ${v.toFixed(3)}`}</title>
            </rect>
            <text x={130 + bw + 8} y={19} fontSize={13} fill="var(--ink-hi)" className="font-mono">
              {v.toFixed(2)}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="text-13 text-ink-mid">
        Recall@5 at T = 120 s on the same candidates; lift{" "}
        {lift === null ? "–" : `${lift >= 0 ? "+" : "−"}${Math.abs(lift).toFixed(2)}`}.
      </figcaption>
    </figure>
  );
}

/** Forecast error at T = 90 s (probers), binned, with the median, P80 and the target. */
export function ErrorHistogram(props: {
  bins: Bin[];
  median: number | null;
  p80: number | null;
  target: number | null;
}) {
  const { bins, median, p80, target } = props;
  if (!bins.length)
    return <p className="text-13 text-ink-mid">No forecast errors in this report.</p>;
  const top = Math.max(...bins.map((b) => b.n));
  const xMax = Math.max((bins[bins.length - 1] as Bin).hi, target ?? 0);
  const x = (v: number) => M.l + (v / xMax) * (W - M.l - M.r);
  const y = (n: number) => H - M.b - (n / Math.max(1, top)) * (H - M.t - M.b);
  const rules: [string, number | null, string][] = [
    ["Median", median, "var(--ink-hi)"],
    ["P80", p80, "var(--ink-mid)"],
    ["Target", target, "var(--verified)"],
  ];
  const step = xMax > 2000 ? 500 : 200;
  return (
    <figure className="flex flex-col gap-2" data-testid="chart-forecast">
      {/* the rules' key: values in ink, a short sample of each line beside them (dataviz) */}
      <ul className="flex flex-wrap gap-4 text-12 text-ink-mid" aria-label="Lines">
        {rules.map(([name, v, c]) =>
          v === null ? null : (
            <li key={name} className="flex items-center gap-1.5">
              <svg width={14} height={12} aria-hidden="true">
                <line
                  x1={7}
                  x2={7}
                  y1={0}
                  y2={12}
                  stroke={c}
                  strokeWidth={2}
                  strokeDasharray={name === "Target" ? "3 2" : undefined}
                />
              </svg>
              {name} <span className="font-mono text-ink-hi">{Math.round(v)} m</span>
            </li>
          ),
        )}
      </ul>
      <svg
        width="100%"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Forecast error at T = 90 s: median ${median?.toFixed(0) ?? "–"} m`}
      >
        <Axis
          x0={M.l}
          x1={W - M.r}
          y0={H - M.b}
          y1={M.t}
          xTicks={Array.from({ length: Math.floor(xMax / step) + 1 }, (_, i) => ({
            v: i * step,
            at: x(i * step),
            label: `${i * step}`,
          }))}
          yTicks={[0, Math.ceil(top / 2), top].map((n) => ({ at: y(n), label: `${n}` }))}
          xLabel="Distance from the predicted center to the true recovery point, m"
        />
        {bins.map((b) => (
          <rect
            key={b.lo}
            x={x(b.lo) + 1}
            y={y(b.n)}
            width={Math.max(1, x(b.hi) - x(b.lo) - 2)}
            height={H - M.b - y(b.n)}
            rx={2}
            fill="var(--bone)"
            fillOpacity={0.75}
          >
            <title>{`${b.lo}–${b.hi} m: ${b.n} quer${b.n === 1 ? "y" : "ies"}`}</title>
          </rect>
        ))}
        {rules.map(([name, v, c]) =>
          v === null ? null : (
            <g key={name}>
              <line
                x1={x(v)}
                x2={x(v)}
                y1={M.t}
                y2={H - M.b}
                stroke={c}
                strokeWidth={1.5}
                strokeDasharray={name === "Target" ? "4 3" : undefined}
              />
              <title>{`${name}: ${Math.round(v)} m`}</title>
            </g>
          ),
        )}
      </svg>
      <details className="text-12 text-ink-mid">
        <summary className="cursor-pointer">Table</summary>
        <table className="mt-1 text-left">
          <thead>
            <tr>
              <th scope="col" className="pr-4">
                Error (m)
              </th>
              <th scope="col">Queries</th>
            </tr>
          </thead>
          <tbody className="font-mono text-ink-hi">
            {bins.map((b) => (
              <tr key={b.lo}>
                <td className="pr-4">
                  {b.lo}–{b.hi}
                </td>
                <td>{b.n}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
