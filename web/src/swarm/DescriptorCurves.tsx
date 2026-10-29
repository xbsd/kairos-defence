// The Swarm view's descriptor curves (SPEC §14, §17.9, D-160), following the dataviz method as the
// Eval charts do (D-140): small multiples on one axis each, 2 px lines, a legend plus direct
// labels for the two series, the match also dashed (the §17.1 pair fails the lightness and chroma
// checks but passes CVD separation, ΔE 21), text in ink tokens, a crosshair tooltip, and a table
// view (SwarmTable). The match's curve is drawn on tonight's seconds through the DTW path.
import { useMemo, useRef, useState } from "react";

import type { SwarmResponse } from "../api/messages";
import { tPlus } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { useSize } from "../lib/useWidth";
import { swarmStore } from "../state/swarmStore";
import { extent, resampleAligned } from "./swarmMath";

const M = { l: 42, r: 46, t: 8, b: 6 };
const H_MIN = 96;
const H_MAX = 180;
const CHROME_PX = 170; // legend, three chart titles, the closing line and the gaps
type Vals = readonly (number | null)[];

function pathOf(
  xs: readonly number[],
  ys: Vals,
  X: (t: number) => number,
  Y: (v: number) => number,
) {
  let d = "";
  let pen = false;
  ys.forEach((v, i) => {
    const t = xs[i];
    if (v === null || t === undefined || !Number.isFinite(v)) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${X(t).toFixed(1)},${Y(v).toFixed(1)}`;
    pen = true;
  });
  return d;
}

function bandOf(
  xs: readonly number[],
  lo: Vals,
  hi: Vals,
  X: (t: number) => number,
  Y: (v: number) => number,
) {
  const top: string[] = [];
  const bottom: string[] = [];
  xs.forEach((t, i) => {
    const a = lo[i];
    const b = hi[i];
    if (a === null || a === undefined || b === null || b === undefined) return;
    top.push(`${X(t).toFixed(1)},${Y(b).toFixed(1)}`);
    bottom.unshift(`${X(t).toFixed(1)},${Y(a).toFixed(1)}`);
  });
  return top.length ? `M${top.join("L")}L${bottom.join("L")}Z` : "";
}

/** "Golf · May 3" → "Golf": a direct label names the base; the legend gives the date. */
function short(name: string): string {
  return name.split(" · ")[0] ?? name;
}

function lastValue(ys: Vals): number | null {
  for (let i = ys.length - 1; i >= 0; i--) {
    const v = ys[i];
    if (v !== null && v !== undefined && Number.isFinite(v)) return v;
  }
  return null;
}

function fmt(v: number | null | undefined, unit: string): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  return `${Math.abs(v) < 10 ? v.toFixed(1) : Math.round(v)} ${unit}`;
}

/** The playhead (≤ 10 redraws a second, §17.11). */
function Playhead(props: { X: (t: number) => number; H: number }) {
  const s = useThrottledStore(swarmStore, (st) => st.playhead, 10);
  const x = props.X(s);
  return <line x1={x} x2={x} y1={M.t} y2={props.H - M.b} stroke="var(--ink-hi)" strokeWidth={1} />;
}

interface ChartProps {
  id: string;
  title: string;
  unit: string;
  xs: readonly number[];
  tonight: Vals;
  match: Vals | null;
  band?: { tonight: [Vals, Vals]; match: [Vals, Vals] | null };
  names: [string, string | null];
  width: number;
  height: number;
}

function Chart(p: ChartProps) {
  const [hover, setHover] = useState<number | null>(null);
  const H = p.height;
  const t0 = p.xs[0] ?? 0;
  const t1 = p.xs[p.xs.length - 1] ?? 1;
  const all = [
    p.tonight,
    ...(p.match ? [p.match] : []),
    ...(p.band ? [...p.band.tonight] : []),
    ...(p.band?.match ? [...p.band.match] : []),
  ];
  const [lo, hi] = extent(...all);
  const w = Math.max(160, p.width);
  const X = (t: number) => M.l + ((t - t0) / Math.max(1, t1 - t0)) * (w - M.l - M.r);
  const Y = (v: number) => H - M.b - ((v - lo) / (hi - lo)) * (H - M.t - M.b);
  const tonightD = pathOf(p.xs, p.tonight, X, Y);
  const matchD = p.match ? pathOf(p.xs, p.match, X, Y) : "";
  const bandD = p.band ? bandOf(p.xs, p.band.tonight[0], p.band.tonight[1], X, Y) : "";
  const yA = lastValue(p.tonight);
  const yB = p.match ? lastValue(p.match) : null;
  let la = yA === null ? null : Y(yA);
  let lb = yB === null ? null : Y(yB);
  if (la !== null && lb !== null && Math.abs(la - lb) < 13) {
    const mid = (la + lb) / 2;
    [la, lb] = la <= lb ? [mid - 7, mid + 7] : [mid + 7, mid - 7];
  }
  const rowAtX = (px: number): number => {
    const t = t0 + ((px - M.l) / Math.max(1, w - M.l - M.r)) * (t1 - t0);
    let best = 0;
    p.xs.forEach((s, i) => {
      if (Math.abs(s - t) < Math.abs((p.xs[best] ?? 0) - t)) best = i;
    });
    return best;
  };
  const h = hover === null ? null : hover;
  const label = `${p.title} (${p.unit}): ${p.names[0]} from ${fmt(lo, p.unit)} to ${fmt(hi, p.unit)}${
    p.names[1] ? `; ${p.names[1]} drawn dashed on the same seconds through the DTW alignment` : ""
  }`;
  return (
    <figure className="relative flex flex-col" data-testid={`swarm-curve-${p.id}`}>
      <figcaption className="flex items-baseline justify-between px-1 text-12 text-ink-mid">
        <span className="font-bold">{p.title}</span>
        <span>{p.unit}</span>
      </figcaption>
      <svg
        width={w}
        height={H}
        viewBox={`0 0 ${w} ${H}`}
        role="img"
        aria-label={label}
        className="cursor-crosshair"
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setHover(rowAtX(e.clientX - r.left));
        }}
        onPointerLeave={() => setHover(null)}
        onClick={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          const t = p.xs[rowAtX(e.clientX - r.left)];
          if (t !== undefined) swarmStore.getState().setPlayhead(t);
        }}
      >
        <title>{label}</title>
        <g fontSize={11} fill="var(--ink-mid)">
          {[lo, hi].map((v, i) => (
            <g key={i}>
              <line x1={M.l} x2={w - M.r} y1={Y(v)} y2={Y(v)} stroke="var(--hairline)" />
              <text x={M.l - 5} y={Y(v) + 4} textAnchor="end">
                {Math.abs(v) < 10 ? v.toFixed(1) : Math.round(v)}
              </text>
            </g>
          ))}
        </g>
        {bandD ? <path d={bandD} fill="var(--flash)" fillOpacity={0.14} stroke="none" /> : null}
        {p.band?.match
          ? p.band.match.map((ys, i) => (
              <path
                key={i}
                d={pathOf(p.xs, ys, X, Y)}
                fill="none"
                stroke="var(--afterglow)"
                strokeWidth={1}
                strokeOpacity={0.6}
                strokeDasharray="2 3"
              />
            ))
          : null}
        {matchD ? (
          <path
            d={matchD}
            fill="none"
            stroke="var(--afterglow)"
            strokeWidth={2}
            strokeDasharray="5 4"
            data-testid="swarm-curve-match"
          />
        ) : null}
        <path d={tonightD} fill="none" stroke="var(--flash)" strokeWidth={2} />
        <g fontSize={11} fill="var(--ink-hi)">
          {la !== null ? (
            <text x={w - M.r + 6} y={la + 4}>
              {short(p.names[0])}
            </text>
          ) : null}
          {lb !== null && p.names[1] ? (
            <text x={w - M.r + 6} y={lb + 4}>
              {short(p.names[1])}
            </text>
          ) : null}
        </g>
        <Playhead X={X} H={H} />
        {h !== null && p.xs[h] !== undefined ? (
          <line
            x1={X(p.xs[h] as number)}
            x2={X(p.xs[h] as number)}
            y1={M.t}
            y2={H - M.b}
            stroke="var(--ink-mid)"
            strokeDasharray="1 3"
          />
        ) : null}
      </svg>
      {h !== null && p.xs[h] !== undefined ? (
        <div
          role="tooltip"
          className="pointer-events-none absolute top-5 rounded-button border border-hairline bg-scope px-2 py-1 text-12 whitespace-nowrap text-ink-hi"
          style={{ left: Math.min(w - 170, Math.max(0, X(p.xs[h] as number) + 8)) }}
        >
          {tPlus(p.xs[h])} · {p.names[0]} {fmt(p.tonight[h], p.unit)}
          {p.match && p.names[1] ? ` · ${p.names[1]} ${fmt(p.match[h], p.unit)}` : ""}
        </div>
      ) : null}
    </figure>
  );
}

/**
 * Spread, pair-distance quartiles and rotation rate for tonight (flash, solid) and the match
 * (afterglow, dashed), the match on tonight's seconds through `aligned`; click a chart to move the
 * playhead there.
 */
export function DescriptorCurves(props: { doc: SwarmResponse; names: [string, string | null] }) {
  const ref = useRef<HTMLDivElement>(null);
  const size = useSize(ref, { width: 420, height: 0 });
  const width = size.width;
  const height = Math.round(Math.min(H_MAX, Math.max(H_MIN, (size.height - CHROME_PX) / 3)));
  const { doc } = props;
  const q = doc.query.curves;
  const m = doc.match?.curves ?? null;
  const al = doc.aligned;
  const series = useMemo(() => {
    const r = (v: Vals | undefined) => (m && v ? resampleAligned(v, al) : null);
    return {
      spread: r(m?.spread_m),
      q25: r(m?.pd_q25_m),
      q50: r(m?.pd_q50_m),
      q75: r(m?.pd_q75_m),
      rot: r(m?.rot_rate_dps),
    };
  }, [m, al]);
  return (
    <div ref={ref} className="flex h-full flex-col gap-2" data-testid="swarm-curves">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 px-1 text-12 text-ink-mid" aria-label="Legend">
        <li className="flex items-center gap-1.5">
          <svg width={22} height={8} aria-hidden="true">
            <line x1={0} x2={22} y1={4} y2={4} stroke="var(--flash)" strokeWidth={2} />
          </svg>
          {props.names[0]} (tonight&apos;s swarm)
        </li>
        {props.names[1] ? (
          <li className="flex items-center gap-1.5">
            <svg width={22} height={8} aria-hidden="true">
              <line
                x1={0}
                x2={22}
                y1={4}
                y2={4}
                stroke="var(--afterglow)"
                strokeWidth={2}
                strokeDasharray="5 4"
              />
            </svg>
            {props.names[1]}, aligned by DTW
          </li>
        ) : null}
      </ul>
      <Chart
        id="spread"
        title="Spread"
        unit="m"
        xs={q.t_s}
        tonight={q.spread_m}
        match={series.spread}
        names={props.names}
        width={width}
        height={height}
      />
      <Chart
        id="pairs"
        title="Pair distances (median, quartile band)"
        unit="m"
        xs={q.t_s}
        tonight={q.pd_q50_m}
        match={series.q50}
        band={{
          tonight: [q.pd_q25_m, q.pd_q75_m],
          match: series.q25 && series.q75 ? [series.q25, series.q75] : null,
        }}
        names={props.names}
        width={width}
        height={height}
      />
      <Chart
        id="rotation"
        title="Rotation rate"
        unit="°/s"
        xs={q.t_s}
        tonight={q.rot_rate_dps}
        match={series.rot}
        names={props.names}
        width={width}
        height={height}
      />
      <p className="px-1 text-12 text-ink-mid">
        {tPlus(q.t_s[0])} to {tPlus(q.t_s[q.t_s.length - 1])} after first radar contact. Click a
        chart to move the playhead.
      </p>
    </div>
  );
}
